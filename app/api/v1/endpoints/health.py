from fastapi import APIRouter, Depends
from datetime import datetime
import logging

from schemas import HealthResponse
from dependencies import get_settings, get_redis_client, get_prometheus_client
from config import Settings
from clients import AsyncRedisClient, AsyncPrometheusClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


# Health check endpoint
@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
    redis_client: AsyncRedisClient = Depends(get_redis_client),
    prometheus_client: AsyncPrometheusClient = Depends(get_prometheus_client),
) -> HealthResponse:
    components = {}
    overall_status = "healthy"
    
   # Check Redis
    try:
        if redis_client and redis_client.redis:
            await redis_client.redis.ping()
            components["redis"] = "healthy"
        else:
            components["redis"] = "disconnected"
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        components["redis"] = "unhealthy"
        overall_status = "unhealthy"
    
    # Check Prometheus
    try:
        if prometheus_client and prometheus_client.session:
            await prometheus_client.query("up")
            components["prometheus"] = "healthy"
        else:
            components["prometheus"] = "disconnected"
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Prometheus health check failed: {e}")
        components["prometheus"] = "unhealthy"
        overall_status = "unhealthy"
    
    components["collector"] = "initialized"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.app.api_version,
        components=components
    )
