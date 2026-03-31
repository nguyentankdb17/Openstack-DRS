"""
FastAPI application factory and entry point.
Implements app factory pattern with lifespan management.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Optional
import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import pandas as pd

from config import get_settings
from middleware import setup_middleware
from dependencies import cleanup_clients, reset_dependencies, get_decision_engine
from api.v1.router import router as api_v1_router
from utils.logger import setup_logger

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


# Setup logging
settings = get_settings()
logger = setup_logger(__name__, level=settings.app.log_level)


def _schedule_analytics_task():
    """
    Synchronous wrapper for background scheduler to call async function.
    APScheduler runs in thread pool, so we need asyncio.run() to execute async code.
    """
    try:
        asyncio.run(calculate_cluster_imbalance_task())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            # If we're already in an event loop, try to get the running loop
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(calculate_cluster_imbalance_task())
            except RuntimeError:
                logger.error(f"Cannot schedule async task: {e}")
        else:
            logger.error(f"Error in sync wrapper: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in sync wrapper: {e}")


async def calculate_cluster_imbalance_task():
    """
    Background task to execute DRS decision cycle every 5 minutes.
    
    Workflow:
    1. Check if migration events occurred in last 5 minutes
    2. If events exist → Skip decision
    3. If no events → Calculate current CII
    4. If current CII > threshold → Recommend migration
    5. If current CII ≤ threshold → Predict future CII
    6. If predicted CII > threshold → Recommend proactive migration
    """
    try:
        logger.debug("Triggered 5-minute DRS decision cycle...")
        
        decision_engine = await get_decision_engine()
        decision_result = await decision_engine.execute_decision_cycle()
        
        if decision_result:
            decision = decision_result.get("decision")
            reason = decision_result.get("reason", "")
            
            logger.info(
                f"Decision Cycle Complete - Decision: {decision} | {reason}"
            )
            
            # If migration is recommended, log detailed information
            if decision == "migrate":
                problematic_hosts = decision_result.get("problematic_hosts", [])
                logger.warning(f"⚠ MIGRATION RECOMMENDED")
                logger.warning(f"  Reason: {decision_result.get('migration_reason', 'Unknown')}")
                logger.warning(f"  Current CII: {decision_result.get('current_cii', 'N/A')}")
                logger.warning(f"  Predicted CII: {decision_result.get('predicted_cii', 'N/A')}")
                logger.warning(f"  Hosts to migrate from: {problematic_hosts}")
                
                # TODO: Trigger actual live migration workflow here
                # - Contact OpenStack to identify VMs on these hosts
                # - Execute live migration to less-loaded hosts
        else:
            logger.warning("Decision cycle returned no result")
            
    except Exception as e:
        logger.error(f"DRS decision cycle failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup/shutdown management."""
    logger.info("=" * 50)
    logger.info(f"OpenstackDRS Metrics API Starting")
    logger.info(f"Environment: {settings.app.environment}")
    logger.info("=" * 50)
    
    try:
        logger.info("Dependencies will be initialized on first request (lazy loading)")
        
        # Setup scheduler for background tasks
        if settings.app.enable_scheduler:
            try:
                
                scheduler = BackgroundScheduler()
                scheduler.start()
                app.state.scheduler = scheduler
                
                # Schedule cluster imbalance calculation every 5 minutes
                scheduler.add_job(
                    _schedule_analytics_task,
                    trigger=IntervalTrigger(minutes=5),
                    id="cluster_imbalance_calculation",
                    name="Cluster Imbalance Index Calculation",
                    replace_existing=True,
                )
                
                logger.info("Cluster imbalance calculation scheduled - every 5 minutes")
                logger.info(f"Scheduler started - background tasks enabled")
            except ImportError:
                logger.warning("APScheduler not installed - background collection disabled")
        
        logger.info("Startup completed successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    # Yield to application runtime
    yield
    
    # Shutdown logic
    logger.info("=" * 50)
    logger.info("OpenstackDRS Metrics API Shutting Down")
    logger.info("=" * 50)
    
    try:
        # Stop scheduler
        if hasattr(app.state, "scheduler"):
            try:
                app.state.scheduler.shutdown()
                logger.info("Scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")
        
        # Cleanup all client connections
        await cleanup_clients()
        
        logger.info("Shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"Shutdown failed: {e}", exc_info=True)


def create_app() -> FastAPI:    
    # Create FastAPI app with lifespan
    app = FastAPI(
        title=settings.app.api_title,
        description="Prometheus metrics collection and querying via Redis Stream",
        version=settings.app.api_version,
        lifespan=lifespan,
        docs_url=f"{settings.app.api_prefix}/docs",
        openapi_url=f"{settings.app.api_prefix}/openapi.json",
        redoc_url=f"{settings.app.api_prefix}/redoc",
    )
    
    # Setup middleware (CORS, compression, logging, error handling)
    setup_middleware(app)
    
    # Include routers with prefix
    app.include_router(
        api_v1_router,
        prefix=settings.app.api_prefix,
    )
    
    # Root endpoint - redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "OpenstackDRS Metrics API",
            "version": settings.app.api_version,
            "docs": f"{settings.app.api_prefix}/docs",
            "status": "running",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # API status endpoint
    @app.get(f"{settings.app.api_prefix}/status", tags=["Status"])
    async def api_status():
        """Get API status"""
        return {
            "status": "operational",
            "environment": settings.app.environment,
            "version": settings.app.api_version,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    logger.info("FastAPI application created successfully")
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    # Development server
    logger.info(f"Starting development server on 0.0.0.0:8000")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.environment == "development",
        log_level=settings.app.log_level.lower(),
    )
