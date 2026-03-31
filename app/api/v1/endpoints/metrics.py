"""Metrics query endpoints"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

from schemas import MetricResponse, MetricTableResponse
from services import MetricsReaderService
from clients import AsyncRedisClient
from dependencies import get_redis_client
from exceptions import MetricsNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


async def get_reader_service(redis_client: AsyncRedisClient = Depends(get_redis_client)) -> MetricsReaderService:
    """Get reader service dependency."""
    return MetricsReaderService(redis_client)


@router.get("/latest", response_model=List[Dict])
async def get_latest_metrics(
    count: int = Query(10, ge=1, le=5000, description="Number of metrics to return"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """Get the latest N metrics."""
    try:
        metrics = await reader.read_latest(count)
        logger.info(f"Retrieved {len(metrics)} latest metrics")
        return metrics
    except MetricsNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving latest metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table", response_model=List[Dict])
async def get_metrics_table(
    count: int = Query(10, ge=1, le=5000, description="Number of metrics to return"),
    item_id_field: str = Query("metric_name", description="Field to use as item ID"),
    value_field: str = Query("value", description="Field to use as value"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """Get metrics in table format."""
    try:
        metrics = await reader.read_latest_as_table(count, item_id_field, value_field)
        logger.info(f"Retrieved {len(metrics)} metrics in table format")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving metrics table: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-host/{host_id}", response_model=List[Dict])
async def get_metrics_by_host(
    host_id: str,
    count: int = Query(100, ge=1, le=5000, description="Number of metrics to return"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """
    Get metrics for a specific host.
    
    Args:
        host_id: Host identifier (e.g., "10.10.10.137:9100")
        count: Number of metrics to return
    
    Returns:
        Filtered metrics for host
    """
    try:
        metrics = await reader.get_metrics_by_host(host_id, count)
        logger.info(f"Retrieved {len(metrics)} metrics for host {host_id}")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving metrics for host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-name/{metric_name}", response_model=List[Dict])
async def get_metrics_by_name(
    metric_name: str,
    count: int = Query(100, ge=1, le=5000, description="Number of metrics to return"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """
    Get metrics by name.
    
    Args:
        metric_name: Metric name to filter by
        count: Number of metrics to return
    
    Returns:
        Filtered metrics
    """
    try:
        metrics = await reader.get_metrics_by_name(metric_name, count)
        logger.info(f"Retrieved {len(metrics)} metrics named {metric_name}")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving metrics by name {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/range", response_model=List[Dict])
async def get_metrics_range(
    start_hours_ago: int = Query(1, ge=1, le=30, description="Hours to look back"),
    item_id_field: str = Query("metric_name", description="Field for item ID"),
    value_field: str = Query("value", description="Field for values"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """
    Get metrics within a time range.
    
    Args:
        start_hours_ago: Number of hours to look back
        item_id_field: Field to pivot on
        value_field: Field to display
    
    Returns:
        Metrics in time range
    """
    try:
        end = datetime.utcnow()
        start = end - timedelta(hours=start_hours_ago)
        
        metrics = await reader.read_by_time_range_as_table(start, end, item_id_field, value_field)
        logger.info(f"Retrieved {len(metrics)} metrics in {start_hours_ago}h range")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving metrics range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/joined", response_model=List[Dict])
async def get_joined_metrics(
    count: int = Query(100, ge=1, le=5000, description="Number of metrics to return"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """
    Get metrics joined with running VMs information.
    
    Args:
        count: Number of metrics to return
    
    Returns:
        Joined metrics with running_vm count
    """
    try:
        metrics = await reader.join_metrics_latest(count)
        logger.info(f"Retrieved {len(metrics)} joined metrics")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving joined metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/joined/range", response_model=List[Dict])
async def get_joined_metrics_range(
    start_hours_ago: int = Query(1, ge=1, le=30, description="Hours to look back"),
    metric_names: Optional[str] = Query(None, description="Comma-separated metric names"),
    reader: MetricsReaderService = Depends(get_reader_service),
) -> List[Dict]:
    """
    Get joined metrics within a time range.
    
    Args:
        start_hours_ago: Hours to look back
        metric_names: Comma-separated metric names to filter (optional)
    
    Returns:
        Joined metrics in time range
    """
    try:
        end = datetime.utcnow()
        start = end - timedelta(hours=start_hours_ago)
        
        metric_list = None
        if metric_names:
            metric_list = [m.strip() for m in metric_names.split(",")]
        
        metrics = await reader.join_metrics_with_running_vms(metric_list, start, end)
        logger.info(f"Retrieved {len(metrics)} joined metrics in {start_hours_ago}h range")
        return metrics
    except Exception as e:
        logger.error(f"Error retrieving joined metrics range: {e}")
        raise HTTPException(status_code=500, detail=str(e))
