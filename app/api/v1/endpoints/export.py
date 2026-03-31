"""Data export endpoints (DataFrame, JSON)"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from services import MetricsReaderService
from clients import AsyncRedisClient
from dependencies import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])


async def get_reader_service(redis_client: AsyncRedisClient = Depends(get_redis_client)) -> MetricsReaderService:
    """Get reader service dependency."""
    return MetricsReaderService(redis_client)


@router.post("/dataframe/{host_id}")
async def export_metrics_dataframe(
    host_id: str,
    count: int = Query(100, ge=1, le=5000, description="Number of metrics to export"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> Dict[str, Any]:
    """
    Export metrics for a specific compute node with running VMs count.
    
    Returns DataFrame with columns: item_id, timestamp, target, running_vm
    
    Args:
        host_id: Compute node IP address (e.g., "10.10.10.10")
        count: Number of metrics to export
    
    Returns:
        JSON with metrics data and metadata
    """
    try:
        df = await reader.export_to_dataframe(count=count, host_id=host_id)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No metrics found for host {host_id}")
        
        logger.info(f"Exporting {len(df)} metrics as DataFrame for host {host_id}")
        
        return {
            "success": True,
            "host_id": host_id,
            "count": len(df),
            "data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DataFrame export failed for host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/joined-dataframe")
async def export_joined_dataframe(
    start_hours_ago: int = Query(1, ge=1, le=30, description="Hours to look back"),
    metric_names: Optional[str] = Query(None, description="Comma-separated metric names"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> Dict[str, Any]:
    """
    Export joined metrics (with running VMs) as pandas DataFrame (returned as JSON).
    
    Args:
        start_hours_ago: Hours to look back
        metric_names: Comma-separated metric names to include
    
    Returns:
        DataFrame as JSON with metadata
    """
    try:
        end = datetime.utcnow()
        start = end - timedelta(hours=start_hours_ago)
        
        # Parse metric names filter
        metric_list = None
        if metric_names:
            metric_list = [m.strip() for m in metric_names.split(",")]
        
        df = await reader.join_and_export_dataframe(metric_list, start, end)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No metrics found to export")
        
        logger.info(f"Exporting {len(df)} joined metrics as DataFrame")
        
        return {
            "success": True,
            "count": len(df),
            "data": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "time_range": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Joined DataFrame export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/redis-summary")
async def debug_redis_summary(
    count: int = Query(100, ge=1, le=1000, description="Number of recent metrics to check"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> Dict[str, Any]:
    """
    Debug endpoint to check what metrics are in Redis.
    
    Args:
        count: Number of recent metrics to analyze
    
    Returns:
        Summary of metrics by type and host
    """
    try:
        all_metrics = await reader.read_latest(count=count)
        
        # Analyze metrics
        by_metric_type = {}
        by_host = {}
        
        for metric in all_metrics:
            metric_type = metric.get("metric_name", "unknown")
            host_id = metric.get("host_id", "unknown")
            value = metric.get("value", "unknown")
            
            # Group by metric type
            if metric_type not in by_metric_type:
                by_metric_type[metric_type] = 0
            by_metric_type[metric_type] += 1
            
            # Group by host
            if host_id not in by_host:
                by_host[host_id] = {}
            if metric_type not in by_host[host_id]:
                by_host[host_id][metric_type] = 0
            by_host[host_id][metric_type] += 1
        
        # Get running_vm specific info
        running_vms = [m for m in all_metrics if m.get("metric_name") == "running_vm"]
        
        return {
            "success": True,
            "total_metrics": len(all_metrics),
            "metrics_by_type": by_metric_type,
            "metrics_by_host": by_host,
            "running_vm_count": len(running_vms),
            "running_vm_values": [
                {
                    "host": m.get("host_id"),
                    "value": m.get("value"),
                    "timestamp": m.get("timestamp")
                }
                for m in running_vms[:10]
            ],
            "sample_metrics": [
                {
                    "metric_name": m.get("metric_name"),
                    "host_id": m.get("host_id"),
                    "value": m.get("value"),
                    "timestamp": m.get("timestamp")
                }
                for m in all_metrics[:5]
            ]
        }
    
    except Exception as e:
        logger.error(f"Debug summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
