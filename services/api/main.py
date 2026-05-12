"""
DRS API Service
Provides RESTful API endpoints and scheduler for resource management
"""
from contextlib import asynccontextmanager
import os
import sys
from fastapi import FastAPI
import uvicorn

# Add parent directories to path for imports
if __package__ in {None, ""}:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.api.monitor import router as monitor_router
from app.api.inventory import router as inventory_router
from app.api.constraints import router as constraints_router
from app.api.cycle_history import router as cycle_history_router
from app.api.configuration import router as configuration_router
from app.api.plan import router as plan_router
from app.api.webhook import router as webhook_router
from app.db.postgres import initialize_database
from app.middleware import setup_middleware
from app.core import settings
from app.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    setup_logging(settings.app.log_level)
    logger.info(f"[API Service] Starting on 0.0.0.0:8000")
    
    # Initialize database
    initialize_database()
    logger.info("[API Service] Database initialized")
    
    yield


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="OpenStack DRS API",
        description="Dynamic Resource Scheduler for OpenStack",
        version="1.0.0",
        lifespan=lifespan
    )
    
    setup_logging(settings.app.log_level)
    setup_middleware(app)
    
    # Include API routers
    app.include_router(monitor_router, prefix="/api/v1", tags=["Monitor"])
    app.include_router(inventory_router, prefix="/api/v1", tags=["Inventory"])
    app.include_router(constraints_router, prefix="/api/v1", tags=["Constraints"])
    app.include_router(cycle_history_router, prefix="/api/v1", tags=["History"])
    app.include_router(configuration_router, prefix="/api/v1", tags=["Configuration"])
    app.include_router(plan_router, prefix="/api/v1", tags=["Plan"])
    app.include_router(webhook_router, prefix="/api/v1", tags=["Webhook"])
    
    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint"""
        return {"status": "healthy", "service": "drs-api"}
    
    return app


app = create_app()


if __name__ == "__main__":
    setup_logging(settings.app.log_level)
    logger.info(f"Starting DRS API Service on 0.0.0.0:8000")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.environment == "development",
        log_level="info",
    )
