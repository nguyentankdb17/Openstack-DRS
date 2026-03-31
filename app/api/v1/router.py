from fastapi import APIRouter

from .endpoints import health, metrics, collector, export, streams, predict, scoring, analytics

router = APIRouter()

# Include all endpoint routers
router.include_router(health.router)
router.include_router(metrics.router)
router.include_router(collector.router)
router.include_router(export.router)
router.include_router(streams.router)
router.include_router(predict.router)
router.include_router(scoring.router)
router.include_router(analytics.router)

__all__ = ["router"]
