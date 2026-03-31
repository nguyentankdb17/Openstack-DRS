"""Analytics endpoints for cluster analysis"""

from fastapi import APIRouter, Depends, HTTPException
import logging

from services.analytic.analytic_service import AnalyticService
from dependencies import get_analytic_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/cluster-imbalance")
async def trigger_cluster_imbalance_calculation(
    analytic: AnalyticService = Depends(get_analytic_service),
):
    """
    Trigger cluster imbalance index calculation.
    
    Queries Prometheus for current metrics and calculates CII.
    
    Args:
        analytic: AnalyticService instance (injected)
    
    Returns:
        Result with CII and cluster statistics
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        result = await analytic.calculate_cluster_imbalance()
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail="Failed to calculate cluster imbalance - no metrics available"
            )
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        logger.error(f"Cluster imbalance calculation endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Calculation failed: {str(e)}"
        )


@router.get("/metrics-summary")
async def get_metrics_summary(
    analytic: AnalyticService = Depends(get_analytic_service),
):
    """
    Get summary of current cluster metrics.
    
    Returns aggregate statistics for CPU, memory, and swap usage.
    
    Args:
        analytic: AnalyticService instance (injected)
    
    Returns:
        Metrics summary by host and aggregate statistics
        
    Raises:
        HTTPException: If query fails
    """
    try:
        result = await analytic.get_metrics_summary()
        
        if result is None:
            raise HTTPException(
                status_code=503,
                detail="Failed to retrieve metrics summary - Prometheus unavailable"
            )
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        logger.error(f"Metrics summary endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/health")
async def analytics_health(
    analytic: AnalyticService = Depends(get_analytic_service),
):
    """
    Check if analytics service is operational.
    
    Returns:
        Status object with service health information
    """
    try:
        return {
            "status": "healthy",
            "service": "analytics",
            "message": "Analytics service is ready"
        }
    except Exception as e:
        logger.error(f"Analytics health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "analytics",
            "error": str(e)
        }
