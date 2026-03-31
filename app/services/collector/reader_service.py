"""
Metrics reader service - async querying and formatting of metrics from Redis.
Handles reading, filtering, formatting, and exporting metrics data.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio
import pandas as pd

from clients.redis_client import AsyncRedisClient
from exceptions import MetricsNotFoundError, DataExportError


logger = logging.getLogger(__name__)


class MetricsReaderService:
    """Service for reading, filtering, and exporting metrics from Redis Stream."""
    
    def __init__(self, redis_client: AsyncRedisClient):
        """Initialize with Redis client."""
        self.redis = redis_client
        logger.info("MetricsReaderService initialized")
    
    async def read_latest(self, count: int = 10) -> List[Dict]:
        """Read the latest N metrics from stream (newest first)."""
        try:
            entries = await self.redis.xrevrange(start="+", end="-", count=count)
            
            metrics = []
            for entry_id, data in entries:
                metric = {
                    "entry_id": entry_id,
                    **data
                }
                metrics.append(metric)
            
            logger.info(f"Read {len(metrics)} latest metrics")
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to read latest metrics: {e}")
            raise MetricsNotFoundError(str(e))
    
    async def read_latest_as_table(
        self,
        count: int = 10,
        item_id_field: str = "metric_name",
        value_field: str = "value",
        host_id: Optional[str] = None
    ) -> List[Dict]:
        try:
            metrics = await self.read_latest(count)
            
            # Filter by host_id if provided
            if host_id:
                metrics = [m for m in metrics if m.get("host_id") == host_id]
            
            # Transform to table format
            table_data = []
            for metric in metrics:
                table_row = {
                    "host": metric.get("host_id", "unknown"),
                    "item_id": metric.get(item_id_field, "unknown"),
                    "timestamp": datetime.fromtimestamp(int(metric.get("timestamp", 0))).isoformat(),
                    value_field: float(metric.get("value", 0)),
                }
                table_data.append(table_row)
            
            return table_data
        
        except Exception as e:
            logger.error(f"Failed to read metrics as table: {e}")
            raise
    
    async def get_metrics_for_host_with_running_vms(
        self,
        host_id: str,
        count: int = 100
    ) -> List[Dict]:
        """
        Get metrics for a specific host and join with running VMs count.
        
        Returns format: {item_id, timestamp, target, running_vm}
        
        Args:
            host_id: Host/node IP address (e.g., "10.10.10.10")
            count: Number of metrics to retrieve
        
        Returns:
            List of metrics with running_vm joined
        """
        try:
            logger.info(f"Getting metrics for host {host_id} with running VMs")
            
            # Get latest metrics (more than requested to have enough after filtering)
            all_metrics = await self.read_latest(count=max(count * 5, 1000))
            
            # Separate CPU/Memory/Swap metrics from running_vm metrics
            host_cpu_memory_swap = []
            running_vm_by_timestamp = {}
            
            for m in all_metrics:
                if m.get("host_id") == host_id:
                    metric_name = m.get("metric_name", "")
                    
                    if metric_name == "running_vm":
                        # Index running_vm by timestamp for quick lookup
                        timestamp_key = int(m.get("timestamp", 0))
                        running_vm_by_timestamp[timestamp_key] = int(float(m.get("value", 0)))
                        logger.debug(f"Found running_vm={m.get('value')} for timestamp {timestamp_key}")
                    else:
                        host_cpu_memory_swap.append(m)
            
            if not host_cpu_memory_swap:
                logger.warning(f"No CPU/Memory/Swap metrics found for host {host_id}")
                return []
            
            # If no running_vm metrics found, use most recent running_vm value from all metrics
            if not running_vm_by_timestamp:
                logger.warning(f"No running_vm metrics found for host {host_id}, searching in all metrics")
                for m in all_metrics:
                    if m.get("metric_name") == "running_vm":
                        timestamp_key = int(m.get("timestamp", 0))
                        running_vm_by_timestamp[timestamp_key] = int(float(m.get("value", 0)))
                        logger.debug(f"Found running_vm={m.get('value')} for timestamp {timestamp_key} (from any host)")
            
            # Format metrics and join with running_vm
            result = []
            for metric in host_cpu_memory_swap:
                metric_timestamp = int(metric.get("timestamp", 0))
                metric_name = metric.get("metric_name")
                
                # Try to find running_vm for exact timestamp, or use most recent
                running_vm_count = 0
                if metric_timestamp in running_vm_by_timestamp:
                    running_vm_count = running_vm_by_timestamp[metric_timestamp]
                else:
                    # If no exact match, use most recent running_vm value
                    if running_vm_by_timestamp:
                        running_vm_count = running_vm_by_timestamp[max(running_vm_by_timestamp.keys())]
                        logger.debug(f"No exact timestamp match for running_vm, using most recent: {running_vm_count}")
                
                # Format metric data
                formatted = {
                    "item_id": metric_name,
                    "timestamp": datetime.fromtimestamp(metric_timestamp).isoformat() if metric_timestamp else datetime.utcnow().isoformat(),
                    "target": float(metric.get("value", 0)),
                    "running_vm": running_vm_count
                }
                result.append(formatted)
            
            logger.info(f"Formatted {len(result)} metrics for host {host_id} with running_vm joined")
            return result[:count]
        
        except Exception as e:
            logger.error(f"Failed to get metrics with running VMs: {e}", exc_info=True)
            raise
    
    async def get_metrics_by_name(self, metric_name: str, count: int = 100) -> List[Dict]:
        try:
            metrics = await self.read_latest(count=max(count * 2, 1000))
            
            filtered = [m for m in metrics if m.get("metric_name") == metric_name]
            logger.info(f"Read {len(filtered)} metrics for name {metric_name}")
            
            return filtered[:count]
        
        except Exception as e:
            logger.error(f"Failed to read metrics by name: {e}")
            raise
    
    async def read_by_time_range_as_table(
        self,
        start: datetime,
        end: datetime,
        item_id_field: str = "metric_name",
        value_field: str = "value"
    ) -> List[Dict]:
        try:
            # For now, read all and filter client-side
            # In production, could use Redis time-based ranges
            all_metrics = await self.read_latest(count=5000)
            
            # Filter by timestamp
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())
            
            filtered = [
                m for m in all_metrics
                if start_ts <= int(m.get("timestamp", 0)) <= end_ts
            ]
            
            # Format as table
            table_data = []
            for metric in filtered:
                table_row = {
                    "host": metric.get("host_id", "unknown"),
                    "item_id": metric.get(item_id_field, "unknown"),
                    "timestamp": datetime.fromtimestamp(int(metric.get("timestamp", 0))).isoformat(),
                    value_field: float(metric.get("value", 0)),
                }
                table_data.append(table_row)
            
            logger.info(f"Read {len(table_data)} metrics in time range")
            return table_data
        
        except Exception as e:
            logger.error(f"Failed to read time range: {e}")
            raise
    
    async def join_metrics_latest(self, count: int = 100) -> List[Dict]:
        try:
            metrics = await self.read_latest(count=count * 2)
            
            # Group by host and merge running_vm count
            host_metrics = {}
            for m in metrics:
                host_id = m.get("host_id")
                if not host_id:
                    continue
                
                if host_id not in host_metrics:
                    host_metrics[host_id] = {"host_id": host_id, "metrics": []}
                
                # If this is a running_vm metric, extract the count
                if m.get("metric_name") == "running_vm":
                    host_metrics[host_id]["running_vm"] = int(m.get("value", 0))
                else:
                    host_metrics[host_id]["metrics"].append(m)
            
            # Flatten back to list
            result = []
            for host_data in host_metrics.values():
                for metric in host_data.get("metrics", []):
                    metric["running_vm"] = host_data.get("running_vm")
                    result.append(metric)
            
            logger.info(f"Joined {len(result)} metrics with running VM info")
            return result[:count]
        
        except Exception as e:
            logger.error(f"Failed to join metrics: {e}")
            raise
    
    async def join_metrics_with_running_vms(
        self,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        try:
            # Use time range query
            if start_time and end_time:
                metrics = await self.read_by_time_range_as_table(
                    start_time, end_time, "metric_name", "value"
                )
            else:
                metrics = await self.read_latest(count=5000)
            
            # Filter by metric names if provided
            if metric_names:
                metrics = [m for m in metrics if m.get("metric_name") in metric_names]
            
            # Join with running VMs
            result = await self.join_metrics_latest(len(metrics))
            
            logger.info(f"Joined {len(result)} metrics with time range filter")
            return result
        
        except Exception as e:
            logger.error(f"Failed to join metrics with time range: {e}")
            raise
    
    async def export_to_dataframe(
        self,
        count: int = 100,
        host_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Export metrics as DataFrame with running_vm joined.
        
        Format: item_id, timestamp, target, running_vm
        
        Args:
            count: Number of metrics to export
            host_id: Specific host to export for (required)
        
        Returns:
            pandas DataFrame
        """
        try:
            if not host_id:
                raise ValueError("host_id is required for export")
            
            metrics = await self.get_metrics_for_host_with_running_vms(host_id, count)
            
            if not metrics:
                logger.warning(f"No metrics to export for host {host_id}")
                return pd.DataFrame()
            
            df = pd.DataFrame(metrics)
            logger.info(f"Exported {len(df)} metrics to DataFrame for host {host_id}")
            return df
        
        except Exception as e:
            logger.error(f"Failed to export to DataFrame: {e}")
            raise DataExportError(str(e))
    
    async def join_and_export_dataframe(
        self,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        try:
            metrics = await self.join_metrics_with_running_vms(
                metric_names, start_time, end_time
            )
            
            if not metrics:
                logger.warning("No metrics to export")
                return pd.DataFrame()
            
            df = pd.DataFrame(metrics)
            logger.info(f"Exported {len(df)} joined metrics to DataFrame")
            return df
        
        except Exception as e:
            logger.error(f"Failed to export joined metrics to DataFrame: {e}")
            raise DataExportError(str(e))
    
    async def get_stream_info(self) -> Dict:
        """
        Get Redis Stream information.
        
        Returns:
            Dictionary with stream metadata
        """
        try:
            info = await self.redis.xinfo_stream()
            length = await self.redis.xlen()
            
            # Get first and last entries
            first_entries = await self.redis.xrange(count=1)
            last_entries = await self.redis.xrange(start="-", end="+", count=1)
            
            first_id = first_entries[0][0] if first_entries else None
            last_id = last_entries[0][0] if last_entries else None
            
            result = {
                "stream_key": self.redis.config.stream_key,
                "length": length,
                "first_entry": first_id,
                "last_entry": last_id,
                "first_timestamp": datetime.fromtimestamp(int(first_id.split('-')[0]) / 1000).isoformat() if first_id else None,
                "last_timestamp": datetime.fromtimestamp(int(last_id.split('-')[0]) / 1000).isoformat() if last_id else None,
                "consumer_groups": info.get("groups", 0) if isinstance(info, dict) else 0,
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to get stream info: {e}")
            raise
