"""Dependency injection: FastAPI Depends with singletons."""

from typing import Optional
from functools import lru_cache
import logging

from fastapi import Depends
from config import Settings, get_settings as get_settings_instance
from clients.redis_client import AsyncRedisClient
from clients.prometheus_client import AsyncPrometheusClient
from services.prediction.predictor_service import PredictorService
from services.scoring.cluster_imbalance import ScoringService
from services.analytic.analytic_service import AnalyticService
from services.migration_detector import MigrationEventDetector
from services.decision.decision_engine import DecisionEngine
from utils.logger import get_logger


logger = get_logger(__name__)

# Module-level singletons (lazily initialized)
_redis_client: Optional[AsyncRedisClient] = None
_prometheus_client: Optional[AsyncPrometheusClient] = None
_predictor_service: Optional[PredictorService] = None
_scoring_service: Optional[ScoringService] = None
_analytic_service: Optional[AnalyticService] = None
_migration_detector: Optional[MigrationEventDetector] = None
_decision_engine: Optional[DecisionEngine] = None
_settings: Optional[Settings] = None


async def get_settings() -> Settings:
    """Get Settings singleton instance."""
    global _settings
    if _settings is None:
        _settings = get_settings_instance()
        logger.info(f"Settings loaded. Environment: {_settings.app.environment}")
    return _settings


async def get_redis_client(settings: Settings = Depends(get_settings)) -> AsyncRedisClient:
    """Get AsyncRedisClient singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = AsyncRedisClient(settings.redis)
        try:
            await _redis_client.connect()
            logger.info("Redis client initialized and connected")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            _redis_client = None
            raise
    return _redis_client


async def get_prometheus_client(settings: Settings = Depends(get_settings)) -> AsyncPrometheusClient:
    """
    Get Prometheus client singleton.
    Connection is created once and reused.
    
    Args:
        settings: Application settings
    
    Returns:
        AsyncPrometheusClient instance
    """
    global _prometheus_client
    if _prometheus_client is None:
        _prometheus_client = AsyncPrometheusClient(settings.prometheus)
        try:
            await _prometheus_client.connect()
            logger.info("Prometheus client initialized and connected")
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus client: {e}")
            _prometheus_client = None
            raise
    return _prometheus_client


async def cleanup_clients():
    """Close all client connections during shutdown."""
    global _redis_client, _prometheus_client
    
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis client closed")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None
    
    if _prometheus_client:
        try:
            await _prometheus_client.close()
            logger.info("Prometheus client closed")
        except Exception as e:
            logger.error(f"Error closing Prometheus client: {e}")
        finally:
            _prometheus_client = None


async def reset_dependencies():
    """Reset dependency singletons (for testing)."""
    global _redis_client, _prometheus_client, _settings, _predictor_service, _scoring_service, _analytic_service, _migration_detector, _decision_engine
    
    await cleanup_clients()
    _settings = None
    _predictor_service = None
    _scoring_service = None
    _analytic_service = None
    _migration_detector = None
    _decision_engine = None
    logger.info("All dependencies reset")


def get_predictor_service() -> PredictorService:
    """Get PredictorService singleton."""
    global _predictor_service
    if _predictor_service is None:
        _predictor_service = PredictorService()
        logger.info("PredictorService initialized")
    return _predictor_service


def get_scoring_service() -> ScoringService:
    """Get ScoringService singleton."""
    global _scoring_service
    if _scoring_service is None:
        _scoring_service = ScoringService()
        logger.info("ScoringService initialized")
    return _scoring_service


async def get_analytic_service(settings: Settings = Depends(get_settings)) -> AnalyticService:
    """Get AnalyticService singleton."""
    global _analytic_service
    if _analytic_service is None:
        prometheus = await get_prometheus_client()
        scoring = get_scoring_service()
        
        # Include predictor service if prediction is enabled
        predictor = None
        if settings.app.enable_prediction:
            predictor = get_predictor_service()
        
        _analytic_service = AnalyticService(
            prometheus_client=prometheus,
            scoring_service=scoring,
            predictor_service=predictor
        )
        logger.info(
            f"AnalyticService initialized "
            f"(prediction: {'enabled' if settings.app.enable_prediction else 'disabled'})"
        )
    return _analytic_service


async def get_migration_detector(settings: Settings = Depends(get_settings)) -> MigrationEventDetector:
    """Get MigrationEventDetector singleton."""
    global _migration_detector
    if _migration_detector is None:
        _migration_detector = MigrationEventDetector(settings.openstack)
        logger.info("MigrationEventDetector initialized")
    return _migration_detector


async def get_decision_engine(
    analytic_service: AnalyticService = Depends(get_analytic_service),
    migration_detector: MigrationEventDetector = Depends(get_migration_detector),
    settings: Settings = Depends(get_settings)
) -> DecisionEngine:
    """Get DecisionEngine singleton."""
    global _decision_engine
    if _decision_engine is None:
        scoring = get_scoring_service()
        _decision_engine = DecisionEngine(
            analytic_service=analytic_service,
            scoring_service=scoring,
            migration_detector=migration_detector,
            settings=settings
        )
        logger.info("DecisionEngine initialized")
    return _decision_engine
