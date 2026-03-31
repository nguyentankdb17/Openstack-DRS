"""Analytic service for cluster analysis and metrics calculation"""

import logging
import pandas as pd
from typing import Dict, Optional
from datetime import datetime

from clients.prometheus_client import AsyncPrometheusClient
from services.scoring.cluster_imbalance import ScoringService

logger = logging.getLogger(__name__)


# PromQL queries for cluster metrics
CPU_USAGE_QUERY = '''
avg_over_time(
  (100 - avg by (instance, job) (irate(node_cpu_seconds_total{job=~".*-node-exporter",mode="idle"}[5m])) * 100)[5m:1m]
)
'''

MEMORY_USAGE_QUERY = '''
avg_over_time(
  (
    (node_memory_MemTotal_bytes{job=~".*-node-exporter"} - (node_memory_MemFree_bytes{job=~".*-node-exporter"} + node_memory_Buffers_bytes{job=~".*-node-exporter"} + node_memory_Cached_bytes{job=~".*-node-exporter"})) 
    / 
    node_memory_MemTotal_bytes{job=~".*-node-exporter"} * 100
  )[5m:1m]
)
'''

SWAP_USAGE_QUERY = '''
avg_over_time(
  ((node_memory_SwapTotal_bytes{job=~".*-node-exporter"} - node_memory_SwapFree_bytes{job=~".*-node-exporter"}) 
  / 
  node_memory_SwapTotal_bytes{job=~".*-node-exporter"} * 100)[5m:1m]
)
'''


class AnalyticService:
    """Service for cluster analytics and metrics calculation"""
    
    def __init__(self, prometheus_client: AsyncPrometheusClient, scoring_service: ScoringService):
        """
        Initialize analytic service with dependencies.
        
        Args:
            prometheus_client: Prometheus client for querying metrics
            scoring_service: Scoring service for calculating imbalance index
        """
        self.prometheus_client = prometheus_client
        self.scoring_service = scoring_service
        logger.info("AnalyticService initialized")
    
    async def query_cluster_metrics(self) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Query Prometheus for cluster metrics and aggregate by host.
        
        Returns:
            Dict mapping host_id to {cpu_usage, memory_usage, swap_usage} percentages
        """
        try:
            logger.info("Querying Prometheus for cluster metrics...")
            
            # Query all three metrics
            cpu_results = await self.prometheus_client.query(CPU_USAGE_QUERY)
            memory_results = await self.prometheus_client.query(MEMORY_USAGE_QUERY)
            swap_results = await self.prometheus_client.query(SWAP_USAGE_QUERY)
            
            logger.info(
                f"Prometheus results - CPU: {len(cpu_results)}, "
                f"Memory: {len(memory_results)}, Swap: {len(swap_results)}"
            )
            
            # Aggregate metrics by host (instance label)
            metrics_by_host: Dict[str, Dict[str, float]] = {}
            
            # Parse CPU metrics
            for result in cpu_results:
                instance = result.get("metric", {}).get("instance", "unknown")
                value = float(result.get("value", [0, 0])[1])
                
                if instance not in metrics_by_host:
                    metrics_by_host[instance] = {}
                metrics_by_host[instance]["cpu_usage"] = value
            
            # Parse Memory metrics
            for result in memory_results:
                instance = result.get("metric", {}).get("instance", "unknown")
                value = float(result.get("value", [0, 0])[1])
                
                if instance not in metrics_by_host:
                    metrics_by_host[instance] = {}
                metrics_by_host[instance]["memory_usage"] = value
            
            # Parse Swap metrics
            for result in swap_results:
                instance = result.get("metric", {}).get("instance", "unknown")
                value = float(result.get("value", [0, 0])[1])
                
                if instance not in metrics_by_host:
                    metrics_by_host[instance] = {}
                metrics_by_host[instance]["swap_usage"] = value
            
            logger.info(f"Aggregated metrics for {len(metrics_by_host)} hosts")
            return metrics_by_host
        
        except Exception as e:
            logger.error(f"Failed to query cluster metrics: {e}")
            return None
    
    async def calculate_cluster_imbalance(self) -> Optional[Dict]:
        """
        Calculate cluster imbalance index from current metrics.
        
        Queries Prometheus, aggregates metrics, and calculates CII
        using scoring service with weighted metrics (CPU 50%, Memory 30%, Swap 20%).
        
        Returns:
            Dict with CII and cluster statistics, or None if calculation fails
        """
        try:
            logger.info("Starting cluster imbalance calculation...")
            
            # Query metrics
            metrics_by_host = await self.query_cluster_metrics()
            
            if not metrics_by_host:
                logger.warning("No metrics available for cluster imbalance calculation")
                return None
            
            # Convert to DataFrame
            dataframe_data = []
            for host_id, metrics in metrics_by_host.items():
                dataframe_data.append({
                    "host_id": host_id,
                    "cpu_usage": metrics.get("cpu_usage", 0.0),
                    "memory_usage": metrics.get("memory_usage", 0.0),
                    "swap_usage": metrics.get("swap_usage", 0.0),
                })
            
            df = pd.DataFrame(dataframe_data)
            
            # Calculate cluster imbalance index
            result = await self.scoring_service.score_cluster_from_dataframe(
                df=df,
                cpu_col="cpu_usage",
                mem_col="memory_usage",
                swap_col="swap_usage",
                weights={"cpu": 0.5, "memory": 0.3, "swap": 0.2}
            )
            
            cii = result.get("cii", 0.0)
            host_count = result.get("host_count", 0)
            
            logger.info(
                f"✓ Cluster Imbalance Index: {cii:.4f} (hosts: {host_count})"
            )
            logger.debug(f"Host metrics: {result.get('metrics', {})}")
            
            # Add timestamp and additional metadata
            result["timestamp"] = datetime.utcnow().isoformat()
            
            return result
        
        except Exception as e:
            logger.error(f"Cluster imbalance calculation failed: {e}", exc_info=True)
            return None
    
    async def get_metrics_summary(self) -> Optional[Dict]:
        """
        Get summary of current cluster metrics without scoring.
        
        Returns:
            Dict with host metrics summary or None if query fails
        """
        try:
            metrics_by_host = await self.query_cluster_metrics()
            
            if not metrics_by_host:
                return None
            
            # Calculate aggregate statistics
            all_cpu = [m.get("cpu_usage", 0) for m in metrics_by_host.values()]
            all_memory = [m.get("memory_usage", 0) for m in metrics_by_host.values()]
            all_swap = [m.get("swap_usage", 0) for m in metrics_by_host.values()]
            
            summary = {
                "host_count": len(metrics_by_host),
                "timestamp": datetime.utcnow().isoformat(),
                "cpu": {
                    "avg": sum(all_cpu) / len(all_cpu) if all_cpu else 0,
                    "min": min(all_cpu) if all_cpu else 0,
                    "max": max(all_cpu) if all_cpu else 0,
                },
                "memory": {
                    "avg": sum(all_memory) / len(all_memory) if all_memory else 0,
                    "min": min(all_memory) if all_memory else 0,
                    "max": max(all_memory) if all_memory else 0,
                },
                "swap": {
                    "avg": sum(all_swap) / len(all_swap) if all_swap else 0,
                    "min": min(all_swap) if all_swap else 0,
                    "max": max(all_swap) if all_swap else 0,
                },
                "hosts": metrics_by_host,
            }
            
            return summary
        
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return None
