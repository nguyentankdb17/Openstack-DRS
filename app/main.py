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
from app.middleware import setup_middleware
from app.core import settings
from app.scheduler.monitor_job import start_scheduler, stop_scheduler
from app.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.app.log_level)

    # Startup
    scheduler = start_scheduler()
    logger.info("Scheduler started")

    yield

    # Shutdown
    stop_scheduler(scheduler)
    logger.info("Scheduler stopped")

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    setup_middleware(app)
    app.include_router(monitor_router, prefix="/api/v1")
    return app

app = create_app()

if __name__ == "__main__":
    logger.info(f"Starting development server on 0.0.0.0:8000")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.environment == "development",
        log_level=settings.app.log_level.lower(),
    )