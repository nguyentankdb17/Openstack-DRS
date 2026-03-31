import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from clients.prometheus_client import AsyncPrometheusClient
from clients.redis_client import AsyncRedisClient
from exceptions import PrometheusConnectionError, RedisConnectionError
from utils.constants import (
    METRIC_TYPE_MEMORY,
    METRIC_TYPE_CPU,
    METRIC_TYPE_SWAP,
    METRIC_TYPE_RUNNING_VM,
)


logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Data class for metric information"""
    metric_name: str
    host_id: str
    value: float
    timestamp: int
    labels: Dict[str, str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for Redis storage"""
        return {
            "metric_name": self.metric_name,
            "host_id": self.host_id,
            "value": float(self.value),
            "timestamp": str(self.timestamp),
            "labels": json.dumps(self.labels) if isinstance(self.labels, dict) else self.labels,
        }


class MetricsCollectorService:
    """Service for collecting metrics from Prometheus to Redis."""
    
    def __init__(self, prometheus_client: AsyncPrometheusClient, redis_client: AsyncRedisClient):
        """Initialize with Prometheus and Redis clients."""
        self.prometheus = prometheus_client
        self.redis = redis_client
        logger.info("MetricsCollectorService initialized")
    
    async def collect_cpu_usage_instant(self) -> List[MetricData]:
        """
        Collect CPU usage percentage metrics from Prometheus (instant query, all instances).
        
        Query: 100 - avg by (instance, job) (irate(node_cpu_seconds_total{job="compute-node-exporter",mode="idle"}[5m])) * 100
        
        Returns:
            List of MetricData for CPU metrics
        """
        query = '100 - avg by (instance, job) (irate(node_cpu_seconds_total{job="compute-node-exporter",mode="idle"}[5m])) * 100'
        return await self._query_instant_metrics(query, METRIC_TYPE_CPU)
    
    async def collect_memory_usage_instant(self) -> List[MetricData]:
        """
        Collect memory usage percentage metrics from Prometheus (instant query, all instances).
        
        Query: (node_memory_MemTotal_bytes - (node_memory_MemFree_bytes + node_memory_Buffers_bytes + node_memory_Cached_bytes)) / node_memory_MemTotal_bytes * 100
        
        Returns:
            List of MetricData for memory metrics
        """
        query = '(node_memory_MemTotal_bytes{job="compute-node-exporter"} - (node_memory_MemFree_bytes{job="compute-node-exporter"} + node_memory_Buffers_bytes{job="compute-node-exporter"} + node_memory_Cached_bytes{job="compute-node-exporter"})) / node_memory_MemTotal_bytes{job="compute-node-exporter"} * 100'
        return await self._query_instant_metrics(query, METRIC_TYPE_MEMORY)
    
    async def collect_swap_usage_instant(self) -> List[MetricData]:
        """
        Collect swap usage percentage metrics from Prometheus (instant query, all instances).
        
        Query: ((node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes) / node_memory_SwapTotal_bytes) * 100
        
        Returns:
            List of MetricData for swap metrics
        """
        query = '((node_memory_SwapTotal_bytes{job="compute-node-exporter"} - node_memory_SwapFree_bytes{job="compute-node-exporter"}) / node_memory_SwapTotal_bytes{job="compute-node-exporter"}) * 100'
        return await self._query_instant_metrics(query, METRIC_TYPE_SWAP)
    
    async def collect_running_vms_instant(self) -> List[MetricData]:
        """
        Collect running VMs count metrics from Prometheus (instant query, all instances).
        
        Query: count by (instance) (libvirt_domain_info_state{job="libvirt-exporter"} == 1)
        
        Returns:
            List of MetricData for running VMs count (one per instance)
        """
        query = 'count by (instance) (libvirt_domain_info_state{job="libvirt-exporter"} == 1)'
        return await self._query_instant_metrics(query, METRIC_TYPE_RUNNING_VM)
    
    async def collect_all_metrics(self) -> Dict[str, List[MetricData]]:
        """
        Collect all metric types from Prometheus and store in Redis.
        
        Returns:
            Dictionary mapping metric type to list of MetricData
        """
        logger.info("Starting to collect all metrics from Prometheus")
        
        results = {}
        
        # Collect all metric types
        try:
            results[METRIC_TYPE_CPU] = await self.collect_cpu_usage_instant()
            logger.info(f"Collected {len(results[METRIC_TYPE_CPU])} CPU metrics")
        except Exception as e:
            logger.error(f"Failed to collect CPU metrics: {e}")
            results[METRIC_TYPE_CPU] = []
        
        try:
            results[METRIC_TYPE_MEMORY] = await self.collect_memory_usage_instant()
            logger.info(f"Collected {len(results[METRIC_TYPE_MEMORY])} memory metrics")
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")
            results[METRIC_TYPE_MEMORY] = []
        
        try:
            results[METRIC_TYPE_SWAP] = await self.collect_swap_usage_instant()
            logger.info(f"Collected {len(results[METRIC_TYPE_SWAP])} swap metrics")
        except Exception as e:
            logger.error(f"Failed to collect swap metrics: {e}")
            results[METRIC_TYPE_SWAP] = []
        
        try:
            results[METRIC_TYPE_RUNNING_VM] = await self.collect_running_vms_instant()
            logger.info(f"Collected {len(results[METRIC_TYPE_RUNNING_VM])} running VM metrics")
        except Exception as e:
            logger.error(f"Failed to collect running VM metrics: {e}")
            results[METRIC_TYPE_RUNNING_VM] = []
        
        # Store all metrics in Redis
        all_metrics = []
        for metric_list in results.values():
            all_metrics.extend(metric_list)
        
        if all_metrics:
            try:
                metric_dicts = [m.to_dict() for m in all_metrics]
                await self.redis.xadd_batch(metric_dicts)
                logger.info(f"Stored {len(all_metrics)} total metrics in Redis")
            except Exception as e:
                logger.error(f"Failed to store metrics in Redis: {e}")
        
        return results
    
    # ========== Compatibility methods for collector endpoints ==========
    
    async def collect_cpu_usage_percentage(
        self,
        instance: str,
        start: int,
        end: int,
        step: str = "15s"
    ) -> List[MetricData]:
        """Compatibility method for collector endpoints."""
        return await self.collect_cpu_usage_instant()
    
    async def collect_memory_usage_percentage(
        self,
        instance: str,
        start: int,
        end: int,
        step: str = "15s"
    ) -> List[MetricData]:
        """Compatibility method for collector endpoints."""
        return await self.collect_memory_usage_instant()
    
    async def collect_swap_usage_percentage(
        self,
        instance: str,
        start: int,
        end: int,
        step: str = "15s"
    ) -> List[MetricData]:
        """Compatibility method for collector endpoints."""
        return await self.collect_swap_usage_instant()
    
    async def collect_running_vms(
        self,
        instance: str,
        start: int,
        end: int,
        step: str = "15s"
    ) -> List[MetricData]:
        """Compatibility method for collector endpoints (note: ignores instance/start/end/step params)."""
        return await self.collect_running_vms_instant()
    
    async def collect_all_metrics_for_instance(
        self,
        instance: str,
        start: int,
        end: int,
        step: str = "15s"
    ) -> Dict[str, List[MetricData]]:
        """Compatibility method - collects all metric types (ignores instance parameter, uses instant query)."""
        logger.info(f"Collecting all metrics for instance: {instance} (using instant query)")
        
        results = {}
        try:
            results[METRIC_TYPE_CPU] = await self.collect_cpu_usage_instant()
        except Exception as e:
            logger.error(f"Failed to collect CPU metrics: {e}")
            results[METRIC_TYPE_CPU] = []
        
        try:
            results[METRIC_TYPE_MEMORY] = await self.collect_memory_usage_instant()
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")
            results[METRIC_TYPE_MEMORY] = []
        
        try:
            results[METRIC_TYPE_SWAP] = await self.collect_swap_usage_instant()
        except Exception as e:
            logger.error(f"Failed to collect swap metrics: {e}")
            results[METRIC_TYPE_SWAP] = []
        
        try:
            results[METRIC_TYPE_RUNNING_VM] = await self.collect_running_vms_instant()
        except Exception as e:
            logger.error(f"Failed to collect running VM metrics: {e}")
            results[METRIC_TYPE_RUNNING_VM] = []
        
        return results
    
    async def collect_all_metrics_all_instances(
        self,
        start: int,
        end: int,
        step: str = "15s"
    ) -> Dict[str, Dict[str, List[MetricData]]]:
        """Compatibility method - returns all metrics grouped by host_id (ignores start/end/step)."""
        logger.info("Collecting all metrics from all instances (using instant query)")
        
        all_results = await self.collect_all_metrics()
        
        # Reformat to match old API: {host_id: {metric_type: [...]}}
        # Group by host_id
        by_instance = {}
        for metric_type, metrics_list in all_results.items():
            for metric in metrics_list:
                host = metric.host_id
                if host not in by_instance:
                    by_instance[host] = {}
                if metric_type not in by_instance[host]:
                    by_instance[host][metric_type] = []
                by_instance[host][metric_type].append(metric)
        
        return by_instance
    
    async def _query_instant_metrics(self, query: str, metric_type: str) -> List[MetricData]:
        """
        Query Prometheus for instant metrics and convert to MetricData format.
        
        Args:
            query: PromQL query string
            metric_type: Type of metric (cpu, memory, swap, running_vm)
        
        Returns:
            List of MetricData objects
        """
        try:
            logger.debug(f"Querying Prometheus with query: {query}")
            results = await self.prometheus.query(query)
            logger.debug(f"Query returned {len(results)} series")
            
            metrics = []
            current_timestamp = int(datetime.utcnow().timestamp())
            
            for result in results:
                try:
                    labels = result.get("metric", {})
                    instance = labels.get("instance", "")
                    
                    # Extract value and timestamp
                    value_data = result.get("value", [None, None])
                    timestamp = int(float(value_data[0])) if value_data[0] else current_timestamp
                    value = float(value_data[1]) if value_data[1] else None
                    
                    if value is not None and instance:
                        # Extract IP from instance (e.g., "10.10.10.10:9100" -> "10.10.10.10")
                        ip = instance.split(':')[0] if ':' in instance else instance
                        
                        metric = MetricData(
                            metric_name=metric_type,
                            host_id=ip,
                            value=value,
                            timestamp=timestamp,
                            labels=labels
                        )
                        metrics.append(metric)
                        logger.debug(f"Parsed metric: {metric_type}={value} for {ip}")
                
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to parse metric result: {e}")
                    continue
            
            logger.info(f"Extracted {len(metrics)} {metric_type} metrics from Prometheus")
            return metrics
        
        except PrometheusConnectionError as e:
            logger.error(f"Prometheus connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to query metrics from Prometheus: {e}")
            raise
