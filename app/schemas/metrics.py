"""Pydantic schemas for metrics-related requests and responses"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from datetime import datetime


class MetricResponse(BaseModel):
    """Response model for individual metric"""
    entry_id: str = Field(..., description="Redis Stream entry ID")
    metric_name: str = Field(..., description="Name of the metric (e.g., 'memory_usage')")
    host_id: str = Field(..., description="Host/instance identifier")
    value: float = Field(..., description="Metric value")
    timestamp: int = Field(..., description="Unix timestamp")
    labels: Dict[str, str] = Field(default_factory=dict, description="Prometheus labels")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry_id": "1234567890000-0",
                "metric_name": "memory_usage",
                "host_id": "10.10.10.137:9100",
                "value": 75.5,
                "timestamp": 1234567890,
                "labels": {"job": "compute-node-exporter"}
            }
        }


class MetricTableResponse(BaseModel):
    """Response model for metrics in table format"""
    item_id: str = Field(..., description="Item identifier (typically metric_name)")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
    target: float = Field(..., description="Target value (metric value)")
    running_vm: Optional[int] = Field(None, description="Number of running VMs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "memory_usage",
                "timestamp": "2026-03-26T10:30:00",
                "target": 75.5,
                "running_vm": 5
            }
        }


class MetricQueryParams(BaseModel):
    """Query parameters for metrics endpoints"""
    count: int = Field(default=10, ge=1, le=5000, description="Number of metrics to return")
    item_id_field: str = Field(default="metric_name", description="Field to use as item ID")
    value_field: str = Field(default="target", description="Field to use as value")
    start_hours_ago: int = Field(default=1, ge=1, le=30, description="Hours to look back")
    metric_names: Optional[str] = Field(None, description="Comma-separated metric names to filter")
    
    class Config:
        json_schema_extra = {
            "example": {
                "count": 100,
                "item_id_field": "metric_name",
                "value_field": "target",
                "start_hours_ago": 1,
                "metric_names": "memory_usage,cpu_usage"
            }
        }


class StreamInfoResponse(BaseModel):
    """Response model for Redis Stream information"""
    stream_key: str = Field(..., description="Stream key name")
    length: int = Field(..., description="Number of entries in stream")
    first_entry: Optional[str] = Field(None, description="First entry ID")
    last_entry: Optional[str] = Field(None, description="Last entry ID")
    consumer_groups: int = Field(0, description="Number of consumer groups")
    first_timestamp: Optional[datetime] = Field(None, description="Timestamp of first entry")
    last_timestamp: Optional[datetime] = Field(None, description="Timestamp of last entry")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stream_key": "metrics:stream",
                "length": 1000,
                "first_entry": "1234567890000-0",
                "last_entry": "1234567999000-0",
                "consumer_groups": 1,
                "first_timestamp": "2026-03-26T00:00:00",
                "last_timestamp": "2026-03-26T10:30:00"
            }
        }


class ExportRequest(BaseModel):
    """Request model for data export"""
    count: int = Field(default=100, ge=1, le=5000, description="Number of records to export")
    item_id_field: str = Field(default="metric_name", description="Field to use as item ID in CSV")
    value_field: str = Field(default="target", description="Field to use as value in CSV")
    start_hours_ago: int = Field(default=1, ge=1, le=30, description="Hours to look back")
    metric_names: Optional[str] = Field(None, description="Comma-separated metric names to filter")


class CollectorResponse(BaseModel):
    """Response model for collector operations"""
    success: bool = Field(..., description="Whether operation succeeded")
    entry_count: int = Field(default=0, description="Number of metrics collected")
    metric_type: Optional[str] = Field(None, description="Type of metric collected")
    instance: Optional[str] = Field(None, description="Instance that was collected")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "entry_count": 50,
                "metric_type": "memory",
                "instance": "10.10.10.137:9100",
                "timestamp": "2026-03-26T10:30:00"
            }
        }


class CollectorBatchResponse(BaseModel):
    """Response model for batch collection operations"""
    success: bool = Field(..., description="Whether operation succeeded")
    total_entries: int = Field(default=0, description="Total metrics collected")
    instances_count: int = Field(default=0, description="Number of instances")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_entries": 500,
                "instances_count": 5,
                "timestamp": "2026-03-26T10:30:00"
            }
        }


class InstancesListResponse(BaseModel):
    """Response model for available instances"""
    instances: List[str] = Field(default_factory=list, description="List of instance identifiers")
    count: int = Field(default=0, description="Number of instances")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "instances": ["10.10.10.137:9100", "10.10.10.138:9100"],
                "count": 2,
                "timestamp": "2026-03-26T10:30:00"
            }
        }


class PredictionRequest(BaseModel):
    """Request model for metric prediction"""
    data: List[float] = Field(..., description="Historical metric values", min_items=1)
    prediction_length: int = Field(default=60, ge=1, le=1000, description="Number of future values to predict")
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [65.2, 68.5, 71.3, 75.1, 73.8, 69.4],
                "prediction_length": 60
            }
        }


class PredictionValueResponse(BaseModel):
    """Individual prediction value with quantiles"""
    timestamp: int = Field(..., description="Prediction timestamp index")
    p10: float = Field(..., description="10th percentile (lower bound)")
    p50: float = Field(..., description="50th percentile (median/point estimate)")
    p90: float = Field(..., description="90th percentile (upper bound)")


class PredictionResponse(BaseModel):
    """Response model for metric predictions"""
    success: bool = Field(True, description="Whether prediction succeeded")
    predictions: List[PredictionValueResponse] = Field(..., description="List of predictions")
    prediction_length: int = Field(..., description="Number of predictions")
    quantiles: List[float] = Field(default=[0.1, 0.5, 0.9], description="Quantile levels used")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Prediction timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "predictions": [
                    {
                        "timestamp": 1,
                        "p10": 68.2,
                        "p50": 72.5,
                        "p90": 76.8
                    },
                    {
                        "timestamp": 2,
                        "p10": 69.1,
                        "p50": 73.1,
                        "p90": 77.2
                    }
                ],
                "prediction_length": 60,
                "quantiles": [0.1, 0.5, 0.9],
                "timestamp": "2026-03-26T10:30:00"
            }
        }


class ClusterImbalanceRequest(BaseModel):
    """Request model for calculating cluster imbalance index"""
    metrics: Dict[str, float] = Field(..., description="Host metrics as key-value pairs (host_id: value)")
    weights: Optional[Dict[str, float]] = Field(None, description="Optional custom weights for metric calculation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "metrics": {
                    "10.10.10.137:9100": 65.2,
                    "10.10.10.138:9100": 72.5,
                    "10.10.10.139:9100": 68.1
                },
                "weights": {"cpu": 0.5, "memory": 0.3, "swap": 0.2}
            }
        }


class HostImbalanceInfo(BaseModel):
    """Information about a single host's imbalance"""
    host_id: str = Field(..., description="Host identifier")
    usage: float = Field(..., description="Host resource usage value")
    deviation: float = Field(..., description="Deviation from cluster mean")
    percentile: float = Field(..., description="Percentile ranking among hosts")


class ClusterImbalanceResponse(BaseModel):
    """Response model for cluster imbalance index calculation"""
    success: bool = Field(True, description="Whether calculation succeeded")
    cluster_imbalance_index: float = Field(..., description="CII value (lower is better)")
    host_count: int = Field(..., description="Number of hosts in cluster")
    mean_usage: float = Field(..., description="Mean resource usage across cluster")
    std_deviation: float = Field(..., description="Standard deviation of resource usage")
    min_usage: float = Field(..., description="Minimum resource usage")
    max_usage: float = Field(..., description="Maximum resource usage")
    usage_range: float = Field(..., description="Difference between max and min")
    host_details: List[HostImbalanceInfo] = Field(default_factory=list, description="Details for each host")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "cluster_imbalance_index": 3.25,
                "host_count": 3,
                "mean_usage": 68.6,
                "std_deviation": 3.25,
                "min_usage": 65.2,
                "max_usage": 72.5,
                "usage_range": 7.3,
                "host_details": [
                    {
                        "host_id": "10.10.10.137:9100",
                        "usage": 65.2,
                        "deviation": -3.4,
                        "percentile": 0.0
                    },
                    {
                        "host_id": "10.10.10.138:9100",
                        "usage": 72.5,
                        "deviation": 3.9,
                        "percentile": 100.0
                    }
                ],
                "timestamp": "2026-03-26T10:30:00"
            }
        }


class DataframeScoringScoringRequest(BaseModel):
    """Request model for scoring from DataFrame"""
    dataframe_data: List[Dict[str, float]] = Field(..., description="List of records with metrics")
    cpu_column: str = Field(default="cpu_usage", description="Column name for CPU usage")
    memory_column: str = Field(default="memory_usage", description="Column name for memory usage")
    swap_column: str = Field(default="swap_usage", description="Column name for swap usage")
    weights: Optional[Dict[str, float]] = Field(None, description="Custom weights for calculation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "dataframe_data": [
                    {"host_id": "host1", "cpu_usage": 45.2, "memory_usage": 72.5, "swap_usage": 10.2},
                    {"host_id": "host2", "cpu_usage": 52.1, "memory_usage": 68.3, "swap_usage": 8.5}
                ],
                "cpu_column": "cpu_usage",
                "memory_column": "memory_usage",
                "swap_column": "swap_usage"
            }
        }


class ProblematicHostsResponse(BaseModel):
    """Response model for identifying problematic hosts"""
    success: bool = Field(True, description="Whether operation succeeded")
    problematic_hosts: List[str] = Field(default_factory=list, description="List of problematic host IDs")
    count: int = Field(0, description="Number of problematic hosts")
    threshold_value: float = Field(..., description="Threshold value used")
    threshold_percentile: float = Field(..., description="Percentile threshold used")
    total_hosts: int = Field(..., description="Total number of hosts checked")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "problematic_hosts": ["10.10.10.138:9100", "10.10.10.140:9100"],
                "count": 2,
                "threshold_value": 70.5,
                "threshold_percentile": 75.0,
                "total_hosts": 5,
                "timestamp": "2026-03-26T10:30:00"
            }
        }
