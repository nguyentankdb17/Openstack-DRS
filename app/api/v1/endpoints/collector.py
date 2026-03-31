"""Metrics collector management endpoints"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

from schemas import CollectorResponse, CollectorBatchResponse, InstancesListResponse
from services import MetricsCollectorService
from clients import AsyncPrometheusClient, AsyncRedisClient
from dependencies import get_prometheus_client, get_redis_client
from config import CollectorConfig, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collector", tags=["Collector"])


async def get_collector_service(
    prometheus: AsyncPrometheusClient = Depends(get_prometheus_client),
    redis: AsyncRedisClient = Depends(get_redis_client),
) -> MetricsCollectorService:
    """Get collector service dependency."""
    return MetricsCollectorService(prometheus, redis)


@router.post("/manual", response_model=CollectorResponse)
async def trigger_manual_collection(
    instances: Optional[list[str]] = Query(None, description="Instances IPs to collect from (e.g. 10.10.10.137)"),
    metric_type: str = Query("memory", pattern="^(memory|cpu|swap|running_vm)$", description="Type of metric"),
    collector: MetricsCollectorService = Depends(get_collector_service),
) -> CollectorResponse:
    """Trigger manual metric collection from one or more instances."""
    try:
        collector_config = get_settings().collector
        # Use provided instances or default from config
        inst_list = instances if instances else collector_config.instance
        
        end = datetime.utcnow()
        start = end - timedelta(minutes=collector_config.lookback_minutes)
        
        total_entries = 0
        collected_instances = []
        
        # Collect metrics from each instance
        for base_inst in inst_list:
            # Add port if not present
            if ':' not in base_inst:
                # For running_vm, use port 9177; for others use 9100
                port = "9177" if metric_type == "running_vm" else "9100"
                inst = f"{base_inst}:{port}"
            else:
                # If port provided, replace with correct port for metric type
                if metric_type == "running_vm":
                    inst = base_inst.rsplit(':', 1)[0] + ":9177"
                else:
                    inst = base_inst
            
            collected_instances.append(inst)
            logger.info(f"Starting manual collection for instance: {inst}, metric type: {metric_type}")
            
            try:
                if metric_type == "memory":
                    entries = await collector.collect_memory_usage_percentage(
                        inst, int(start.timestamp()), int(end.timestamp()), collector_config.query_step
                    )
                elif metric_type == "cpu":
                    entries = await collector.collect_cpu_usage_percentage(
                        inst, int(start.timestamp()), int(end.timestamp()), collector_config.query_step
                    )
                elif metric_type == "swap":
                    entries = await collector.collect_swap_usage_percentage(
                        inst, int(start.timestamp()), int(end.timestamp()), collector_config.query_step
                    )
                else:  # running_vm
                    entries = await collector.collect_running_vms(
                        inst, int(start.timestamp()), int(end.timestamp()), collector_config.query_step
                    )
                
                total_entries += len(entries)
                logger.info(f"Collection for {inst}: {len(entries)} metrics collected")
            
            except Exception as e:
                logger.error(f"Collection failed for {inst}: {e}")
                raise
        
        logger.info(f"Manual collection completed: {total_entries} metrics from {len(inst_list)} instances")
        return CollectorResponse(
            success=True,
            entry_count=total_entries,
            metric_type=metric_type,
            instance=",".join(collected_instances),
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Manual collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/all-instances", response_model=CollectorBatchResponse)
async def collect_all_instances(
    start_minutes_ago: int = Query(5, ge=1, le=240, description="Minutes to look back"),
    collector: MetricsCollectorService = Depends(get_collector_service),
) -> CollectorBatchResponse:
    try:
        collector_config = get_settings().collector
        
        end = datetime.utcnow()
        start = end - timedelta(minutes=start_minutes_ago)
        
        all_results = await collector.collect_all_metrics_all_instances(
            int(start.timestamp()), int(end.timestamp()), collector_config.query_step
        )
        
        total = sum(
            sum(len(metrics) for metrics in inst_metrics.values())
            for inst_metrics in all_results.values()
        )
        
        logger.info(f"Batch collection completed: {total} metrics from {len(all_results)} instances")
        return CollectorBatchResponse(
            success=True,
            total_entries=total,
            instances_count=len(all_results),
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Batch collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instance/{instance_id}", response_model=CollectorBatchResponse)
async def collect_for_instance(
    instance_id: str,
    start_minutes_ago: int = Query(5, ge=1, le=240, description="Minutes to look back"),
    collector: MetricsCollectorService = Depends(get_collector_service),
) -> CollectorBatchResponse:
    """
    Collect all metrics for a specific instance.
    
    Args:
        instance_id: Instance IP address (e.g., 10.10.10.137)
        start_minutes_ago: Lookback window in minutes
    
    Returns:
        Collection result
    """
    try:
        collector_config = get_settings().collector
        
        end = datetime.utcnow()
        start = end - timedelta(minutes=start_minutes_ago)
        
        # Instance format is {ip}:9100 for node-exporter metrics
        inst = instance_id if ':' in instance_id else instance_id + ":9100"
        
        results = await collector.collect_all_metrics_for_instance(
            inst, int(start.timestamp()), int(end.timestamp()), collector_config.query_step
        )
        
        total = sum(len(metrics) for metrics in results.values())
        
        metrics_by_type = {k: len(v) for k, v in results.items()}
        logger.info(f"Instance collection completed for {instance_id}: {total} metrics")
        
        return CollectorBatchResponse(
            success=True,
            total_entries=total,
            instances_count=1,
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Instance collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances", response_model=InstancesListResponse)
async def get_available_instances(
    prometheus: AsyncPrometheusClient = Depends(get_prometheus_client),
) -> InstancesListResponse:
    """
    Get list of all available instances.
    
    Returns:
        List of instance identifiers
    """
    try:
        instances = await prometheus.get_all_instances()
        logger.info(f"Retrieved {len(instances)} available instances")
        
        return InstancesListResponse(
            instances=instances,
            count=len(instances),
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Failed to get instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))
