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
    
    # Cluster Imbalance Index thresholds
    cii_threshold_current: float = 0.5  # Threshold for current metrics CII
    cii_threshold_predicted: float = 0.5  # Threshold for predicted metrics CII
    
    # Prediction settings
    prediction_lookback_hours: int = 0.5  # 30 minutes historical data for prediction
    prediction_horizon_minutes: int = 5  # Predict next 5 minutes
    
    # Problematic hosts identification
    problematic_hosts_percentile: float = 75.0  # Top 25% threshold
    
    class Config:
        env_prefix = "APP_"
        case_sensitive = False


class OpenStackConfig(BaseSettings):
    """OpenStack connection settings"""
    auth_url: str = os.getenv("OPENSTACK_AUTH_URL", "http://localhost:5000/v3")
    username: str = os.getenv("OPENSTACK_USERNAME", "admin")
    password: str = os.getenv("OPENSTACK_PASSWORD", "admin")
    project_name: str = os.getenv("OPENSTACK_PROJECT_NAME", "admin")
    project_domain_id: str = os.getenv("OPENSTACK_PROJECT_DOMAIN_ID", "default")
    user_domain_id: str = os.getenv("OPENSTACK_USER_DOMAIN_ID", "default")
    region_name: Optional[str] = os.getenv("OPENSTACK_REGION_NAME", "RegionOne")
    timeout: int = 30
    
    # Migration detection settings
    migration_check_minutes: int = 5  # Check for events in last N minutes
    event_types: list[str] = ["compute.instance.live.migration.pre.start", 
                               "compute.instance.create.start", 
                               "compute.instance.delete.start"]
    
    class Config:
        env_prefix = "OPENSTACK_"
        case_sensitive = False


class Settings(BaseSettings):
    """Root settings combining all config sections"""
    prometheus: PrometheusConfig = PrometheusConfig()
    redis: RedisConfig = RedisConfig()
    collector: CollectorConfig = CollectorConfig()
    app: AppConfig = AppConfig()
    openstack: OpenStackConfig = OpenStackConfig()
    
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
