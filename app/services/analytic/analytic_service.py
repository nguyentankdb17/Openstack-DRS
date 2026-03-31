"""Analytic service for cluster analysis and metrics calculation"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from clients.prometheus_client import AsyncPrometheusClient
from services.scoring.cluster_imbalance import ScoringService
from services.prediction.predictor_service import PredictorService

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
    
    def __init__(
        self,
        prometheus_client: AsyncPrometheusClient,
        scoring_service: ScoringService,
        predictor_service: Optional[PredictorService] = None
    ):
        """
        Initialize analytic service with dependencies.
        
        Args:
            prometheus_client: Prometheus client for querying metrics
            scoring_service: Scoring service for calculating imbalance index
            predictor_service: Optional predictor service for time-series forecasting
        """
        self.prometheus_client = prometheus_client
        self.scoring_service = scoring_service
        self.predictor_service = predictor_service
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
    
    async def query_historical_metrics(
        self,
        lookback_hours: float = 0.5
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Query historical metrics from Prometheus for prediction input.
        
        Returns metrics as time-series DataFrames per metric type.
        
        Args:
            lookback_hours: How far back to query (default 30 minutes)
        
        Returns:
            Dict mapping metric names to time-series DataFrames:
            {
                "cpu": DataFrame with columns [timestamp, instance, value],
                "memory": DataFrame,
                "swap": DataFrame
            }
            or None if query fails
        """
        try:
            logger.info(f"Querying historical metrics (lookback: {lookback_hours}h)...")
            
            # Build range queries
            lookback_str = f"{int(lookback_hours * 60)}m"
            
            # Modified queries for range queries (with [start:step] syntax)
            cpu_range_query = f'(100 - avg by (instance, job) (irate(node_cpu_seconds_total{{job=~".*-node-exporter",mode="idle"}}[5m])))[{lookback_str}:1m]'
            memory_range_query = f'((node_memory_MemTotal_bytes{{job=~".*-node-exporter"}} - (node_memory_MemFree_bytes{{job=~".*-node-exporter"}} + node_memory_Buffers_bytes{{job=~".*-node-exporter"}} + node_memory_Cached_bytes{{job=~".*-node-exporter"}})) / node_memory_MemTotal_bytes{{job=~".*-node-exporter"}} * 100)[{lookback_str}:1m]'
            swap_range_query = f'((node_memory_SwapTotal_bytes{{job=~".*-node-exporter"}} - node_memory_SwapFree_bytes{{job=~".*-node-exporter"}}) / node_memory_SwapTotal_bytes{{job=~".*-node-exporter"}} * 100)[{lookback_str}:1m]'
            
            # Query all three metrics
            cpu_results = await self.prometheus_client.query(cpu_range_query)
            memory_results = await self.prometheus_client.query(memory_range_query)
            swap_results = await self.prometheus_client.query(swap_range_query)
            
            logger.info(
                f"Historical query results - CPU: {len(cpu_results)}, "
                f"Memory: {len(memory_results)}, Swap: {len(swap_results)}"
            )
            
            # Convert to DataFrames
            def convert_to_dataframe(results):
                """Convert Prometheus time-series results to DataFrame."""
                data = []
                for result in results:
                    instance = result.get("metric", {}).get("instance", "unknown")
                    values = result.get("values", [])
                    for timestamp, value in values:
                        try:
                            data.append({
                                "timestamp": datetime.fromtimestamp(float(timestamp)),
                                "instance": instance,
                                "value": float(value)
                            })
                        except (ValueError, TypeError):
                            continue
                
                if not data:
                    return None
                
                df = pd.DataFrame(data)
                df = df.sort_values("timestamp")
                return df
            
            cpu_df = convert_to_dataframe(cpu_results)
            memory_df = convert_to_dataframe(memory_results)
            swap_df = convert_to_dataframe(swap_results)
            
            if not any([cpu_df is not None, memory_df is not None, swap_df is not None]):
                logger.warning("No historical metrics available")
                return None
            
            result = {}
            if cpu_df is not None:
                result["cpu"] = cpu_df
            if memory_df is not None:
                result["memory"] = memory_df
            if swap_df is not None:
                result["swap"] = swap_df
            
            logger.info(f"Retrieved {len(result)} metric types with historical data")
            return result
        
        except Exception as e:
            logger.error(f"Failed to query historical metrics: {e}", exc_info=True)
            return None
    
    async def predict_future_metrics(
        self,
        lookback_hours: float = 0.5,
        prediction_horizon_minutes: int = 5
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Predict future metrics using Chronos based on historical data.
        
        Args:
            lookback_hours: Historical data lookback (default 30 minutes)
            prediction_horizon_minutes: Minutes to predict into future (default 5)
        
        Returns:
            Dict mapping metric names to predicted DataFrames with quantiles
            or None if prediction fails
        """
        if not self.predictor_service:
            logger.warning("PredictorService not initialized - cannot predict")
            return None
        
        try:
            logger.info(
                f"Predicting metrics ({prediction_horizon_minutes}min ahead, "
                f"using {lookback_hours}h history)..."
            )
            
            # Query historical metrics
            historical = await self.query_historical_metrics(lookback_hours)
            
            if not historical:
                logger.warning("No historical data for prediction")
                return None
            
            # Convert 5 minutes to 60 data points (assuming 1-minute step from query)
            # But Chronos might need different format
            # Let's convert to time-series format expected by Chronos
            
            predicted_result = {}
            
            for metric_name, df in historical.items():
                try:
                    if df is None or df.empty:
                        continue
                    
                    # Group by instance and predict for each host
                    for instance in df["instance"].unique():
                        instance_data = df[df["instance"] == instance].copy()
                        
                        if instance_data.empty or len(instance_data) < 3:
                            logger.debug(f"Skipping {metric_name}/{instance} - insufficient data")
                            continue
                        
                        # Sort by timestamp
                        instance_data = instance_data.sort_values("timestamp")
                        
                        # Create DataFrame for Chronos (requires timestamps as index)
                        instance_data_chrono = instance_data.set_index("timestamp")[["value"]]
                        
                        try:
                            # Predict using Chronos
                            pred_df = self.predictor_service.predict_metrics(
                                metric_history=instance_data_chrono,
                                length=prediction_horizon_minutes  # 5 minute prediction
                            )
                            
                            if pred_df is not None and not pred_df.empty:
                                # Store predictions with instance info
                                if metric_name not in predicted_result:
                                    predicted_result[metric_name] = {}
                                predicted_result[metric_name][instance] = pred_df
                                logger.debug(f"Predicted {len(pred_df)} steps for {metric_name}/{instance}")
                        
                        except Exception as e:
                            logger.warning(f"Prediction failed for {metric_name}/{instance}: {e}")
                            continue
                    
                except Exception as e:
                    logger.warning(f"Error processing {metric_name}: {e}")
                    continue
            
            if predicted_result:
                logger.info(f"✓ Generated predictions for {len(predicted_result)} metric types")
                return predicted_result
            else:
                logger.warning("No predictions generated")
                return None
        
        except Exception as e:
            logger.error(f"Metrics prediction failed: {e}", exc_info=True)
            return None
    
    async def calculate_predicted_imbalance(
        self,
        lookback_hours: float = 0.5,
        prediction_horizon_minutes: int = 5
    ) -> Optional[Dict]:
        """
        Calculate cluster imbalance index based on predicted metrics.
        
        1. Query historical metrics (last 30 minutes)
        2. Predict metrics for next 5 minutes using Chronos
        3. Calculate CII from predicted metrics
        
        Args:
            lookback_hours: Historical data lookback for prediction
            prediction_horizon_minutes: Minutes to predict ahead
        
        Returns:
            Dict with predicted CII and problematic hosts, or None if fails
        """
        if not self.predictor_service:
            logger.warning("PredictorService not initialized - cannot calculate predicted imbalance")
            return None
        
        try:
            logger.info("Starting predicted cluster imbalance calculation...")
            
            # Predict future metrics
            predictions = await self.predict_future_metrics(
                lookback_hours=lookback_hours,
                prediction_horizon_minutes=prediction_horizon_minutes
            )
            
            if not predictions:
                logger.warning("No predictions available for imbalance calculation")
                return None
            
            # Extract latest predicted values per metric per instance
            # Use median (0.5 quantile) as most likely prediction
            predicted_metrics_by_host = {}
            
            for metric_name, instance_predictions in predictions.items():
                for instance, pred_df in instance_predictions.items():
                    if pred_df is None or pred_df.empty:
                        continue
                    
                    if instance not in predicted_metrics_by_host:
                        predicted_metrics_by_host[instance] = {}
                    
                    # Get the last predicted value (most recent prediction)
                    # Chronos returns quantile columns like "0.1", "0.5", "0.9"
                    if "0.5" in pred_df.columns:
                        last_predicted = pred_df["0.5"].iloc[-1]
                    else:
                        # Fallback to first numeric column
                        last_predicted = pred_df.iloc[-1, 0]
                    
                    predicted_metrics_by_host[instance][f"{metric_name}_predicted"] = float(last_predicted)
            
            if not predicted_metrics_by_host:
                logger.warning("No predicted data extracted from predictions")
                return None
            
            # Build DataFrame for scoring
            dataframe_data = []
            for host_id, metrics in predicted_metrics_by_host.items():
                dataframe_data.append({
                    "host_id": host_id,
                    "cpu_usage": metrics.get("cpu_predicted", 0.0),
                    "memory_usage": metrics.get("memory_predicted", 0.0),
                    "swap_usage": metrics.get("swap_predicted", 0.0),
                })
            
            df = pd.DataFrame(dataframe_data)
            
            # Calculate predicted CII
            result = await self.scoring_service.score_cluster_from_dataframe(
                df=df,
                cpu_col="cpu_usage",
                mem_col="memory_usage",
                swap_col="swap_usage",
                weights={"cpu": 0.5, "memory": 0.3, "swap": 0.2}
            )
            
            predicted_cii = result.get("cii", 0.0)
            host_count = result.get("host_count", 0)
            
            logger.info(
                f"✓ Predicted Cluster Imbalance Index: {predicted_cii:.4f} "
                f"(hosts: {host_count})"
            )
            
            # Add metadata
            result["prediction_horizon"] = prediction_horizon_minutes
            result["timestamp"] = datetime.utcnow().isoformat()
            result["metrics_type"] = "predicted"
            
            return result
        
        except Exception as e:
            logger.error(f"Predicted imbalance calculation failed: {e}", exc_info=True)
            return None
