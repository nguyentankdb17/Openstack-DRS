from pydantic_settings import BaseSettings
from typing import Optional
import logging
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


class PrometheusConfig(BaseSettings):
    """Prometheus connection settings"""
    url: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    username: Optional[str] = os.getenv("PROMETHEUS_USERNAME")
    password: Optional[str] = os.getenv("PROMETHEUS_PASSWORD")
    timeout: int = 30
    
    class Config:
        env_prefix = "PROMETHEUS_"
        case_sensitive = False


class RedisConfig(BaseSettings):
    """Redis connection settings"""
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = 6379
    db: int = os.getenv("REDIS_DB", 0)
    password: Optional[str] = os.getenv("REDIS_PASSWORD")
    stream_key: str = os.getenv("REDIS_STREAM_KEY", "metrics:stream")
    consumer_group: str = os.getenv("REDIS_CONSUMER_GROUP", "metrics_group")
    consumer_name: str = os.getenv("REDIS_CONSUMER_NAME", "metrics_consumer")
    
    class Config:
        env_prefix = "REDIS_"
        case_sensitive = False


class CollectorConfig(BaseSettings):
    """Metrics collector settings"""
    instance: list[str] = ["10.10.10.137", "10.10.10.138", "10.10.10.143"]
    collection_interval_minutes: int = 5
    query_step: str = "15s"
    lookback_minutes: int = 5
    
    class Config:
        env_prefix = "COLLECTOR_"
        case_sensitive = False


class AppConfig(BaseSettings):
    """Application-level settings"""
    environment: str = "development"
    log_level: str = "INFO"
    api_title: str = "OpenstackDRS Metrics API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # Enable/disable features
    enable_scheduler: bool = True
    enable_prediction: bool = False
    
    # Async settings
    use_async: bool = True
    
    class Config:
        env_prefix = "APP_"
        case_sensitive = False


class Settings(BaseSettings):
    """Root settings combining all config sections"""
    prometheus: PrometheusConfig = PrometheusConfig()
    redis: RedisConfig = RedisConfig()
    collector: CollectorConfig = CollectorConfig()
    app: AppConfig = AppConfig()
    
    class Config:
        case_sensitive = False
        env_nested_delimiter = "__"


def get_settings() -> Settings:
    """Singleton pattern: returns or creates Settings instance"""
    return Settings()


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)
