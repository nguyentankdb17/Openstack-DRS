from contextlib import asynccontextmanager
import os
import sys
from fastapi import FastAPI
import uvicorn

if __package__ in {None, ""}:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
from app.scheduler.monitor_job import shutdown_monitor_scheduler, start_monitor_scheduler
from app.middleware import setup_middleware
from app.core import settings
from app.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app.log_level)
    initialize_database()
    await start_monitor_scheduler()

    try:
        yield
    finally:
        await shutdown_monitor_scheduler()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # app = FastAPI()
    setup_logging(settings.app.log_level)
    setup_middleware(app)
    app.include_router(monitor_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(constraints_router, prefix="/api/v1")
    app.include_router(cycle_history_router, prefix="/api/v1")
    app.include_router(configuration_router, prefix="/api/v1")
    app.include_router(plan_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")
    return app

app = create_app()

if __name__ == "__main__":
    logger.info(f"Starting development server on 0.0.0.0:8000")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.environment == "development",
        log_level="debug",
    )
