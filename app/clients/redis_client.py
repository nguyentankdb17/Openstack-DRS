"""
Async Redis client wrapper for Redis Stream operations.
Uses redis[asyncio] for non-blocking I/O operations.
"""

import redis.asyncio as aioredis
from redis.exceptions import (
    ResponseError as RedisResponseError,
    AuthenticationError,
    ConnectionError as RedisConnectionErrorType,
)
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from exceptions import RedisConnectionError
from config import RedisConfig


logger = logging.getLogger(__name__)


class AsyncRedisClient:
    """Async Redis Stream operations client."""
    
    def __init__(self, config: RedisConfig):
        """Initialize with RedisConfig."""
        self.config = config
        self.redis: Optional[aioredis.Redis] = None
    
    def _deserialize_labels(self, data: Dict) -> None:
        """
        Deserialize JSON labels in-place.
        
        Args:
            data: Dictionary that may contain 'labels' field
        """
        if 'labels' not in data:
            return
        
        try:
            if isinstance(data['labels'], str):
                data['labels'] = json.loads(data['labels'])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to deserialize labels: {e}. Keeping as string.")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """
        Connect to Redis with proper credential handling.
        
        Uses direct Redis constructor to properly handle passwords with 
        special characters and provides better connection pool management.
        """
        try:
            logger.info("Connecting to Redis...")
            logger.debug(f"Connection details: {self.config.host}:{self.config.port}/DB{self.config.db} (password: {'yes' if self.config.password else 'no'})")
            
            # Validate configuration
            if not self.config.host:
                raise ValueError("Redis host not configured")
            
            # Create Redis client directly with explicit parameters
            # This approach properly handles passwords with special characters
            self.redis = aioredis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password if self.config.password else None,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=10,
                socket_keepalive=True,
                retry_on_timeout=True,
                max_connections=50,
            )
            
            # Test connection with timeout
            try:
                await self.redis.ping()
            except AuthenticationError as auth_err:
                logger.error(f"Redis authentication failed: {auth_err}")
                raise RedisConnectionError(f"Redis authentication failed. Error: {str(auth_err)}")
            except RedisConnectionErrorType as conn_err:
                logger.error(f"Redis connection error: {conn_err}")
                raise RedisConnectionError(f"Cannot connect to Redis at {self.config.host}:{self.config.port}. {str(conn_err)}")
            
            auth_info = " (password protected)" if self.config.password else ""
            logger.info(f"Connected to Redis: {self.config.host}:{self.config.port}/DB{self.config.db}{auth_info}")
        
        except RedisConnectionError:
            raise
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {type(e).__name__}: {e}")
            raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")
    
    async def close(self):
        """
        Close Redis connection and cleanup resources.
        
        Properly disconnects and clears the connection pool.
        """
        if self.redis:
            try:
                # Clear connection pool
                await self.redis.close()
                logger.info("✓ Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
    
    # Redis Stream operations
    async def xadd(self, metric_dict: Dict) -> str:
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            # Serialize labels to JSON if present
            if 'labels' in metric_dict and isinstance(metric_dict['labels'], dict):
                metric_dict['labels'] = json.dumps(metric_dict['labels'])
            
            entry_id = await self.redis.xadd(self.config.stream_key, metric_dict)
            logger.debug(f"Metric written to stream {self.config.stream_key}: {entry_id}")
            return entry_id
        
        except Exception as e:
            logger.error(f"Failed to write metric to Redis stream: {e}")
            raise RedisConnectionError(f"XADD operation failed: {str(e)}")
    
    # Batch XADD for multiple metrics
    async def xadd_batch(self, metrics: List[Dict]) -> List[str]:
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        if not metrics:
            logger.warning("Empty metrics list provided to xadd_batch")
            return []
        
        try:
            async with self.redis.pipeline() as pipe:
                for metric in metrics:
                    # Serialize labels
                    if 'labels' in metric and isinstance(metric['labels'], dict):
                        metric['labels'] = json.dumps(metric['labels'])
                    
                    await pipe.xadd(self.config.stream_key, metric)
                
                entry_ids = await pipe.execute()
                logger.info(f"Batch written to stream: {len(entry_ids)} metrics (pipeline optimization)")
                return entry_ids
        
        except Exception as e:
            logger.error(f"Failed to write batch to Redis stream: {e}")
            raise RedisConnectionError(f"XADD batch operation failed: {str(e)}")
    
    async def xrange(
        self, 
        start: str = "-", 
        end: str = "+",
        count: Optional[int] = None
    ) -> List[Tuple[str, Dict]]:
        """
        Read range of metrics from Redis Stream.
        
        Args:
            start: Start entry ID (inclusive, "-" for first)
            end: End entry ID (inclusive, "+" for last)
            count: Maximum number of entries to return
        
        Returns:
            List of (entry_id, data_dict) tuples
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            kwargs = {}
            if count:
                kwargs['count'] = count
            
            results = await self.redis.xrange(
                self.config.stream_key,
                min=start,
                max=end,
                **kwargs
            )
            
            # Deserialize labels
            for entry_id, data in results:
                self._deserialize_labels(data)
            
            logger.debug(f"XRANGE: Read {len(results)} entries (start={start}, end={end})")
            return results
        
        except Exception as e:
            logger.error(f"Failed to read range from Redis stream: {e}")
            raise RedisConnectionError(f"XRANGE operation failed: {str(e)}")
    
    async def xrevrange(
        self, 
        start: str = "+", 
        end: str = "-",
        count: Optional[int] = None
    ) -> List[Tuple[str, Dict]]:
        """
        Read range of metrics from Redis Stream in REVERSE order (newest first).
        
        Args:
            start: Start entry ID (inclusive, "+" for last)
            end: End entry ID (inclusive, "-" for first)
            count: Maximum number of entries to return
        
        Returns:
            List of (entry_id, data_dict) tuples ordered from newest to oldest
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            kwargs = {}
            if count:
                kwargs['count'] = count
            
            results = await self.redis.xrevrange(
                self.config.stream_key,
                max=start,
                min=end,
                **kwargs
            )
            
            # Deserialize labels
            for entry_id, data in results:
                self._deserialize_labels(data)
            
            logger.debug(f"XREVRANGE: Read {len(results)} entries in reverse (newest to oldest)")
            return results
        
        except Exception as e:
            logger.error(f"Failed to read reverse range from Redis stream: {e}")
            raise RedisConnectionError(f"XREVRANGE operation failed: {str(e)}")
    
    async def xread(
        self,
        streams: Dict[str, str],
        count: Optional[int] = None,
        block: Optional[int] = None
    ) -> List[Tuple[str, List[Tuple[str, Dict]]]]:
        """
        Read from streams (blocking or non-blocking).
        
        Args:
            streams: Dict of stream_key -> entry_id
            count: Maximum number of entries per stream
            block: Block timeout in milliseconds (None = non-blocking)
        
        Returns:
            List of (stream_key, [(entry_id, data), ...]) tuples
        
        Raises:
            RedisConnectionError: If operation fails
        """
        if not self.redis:
            raise RedisConnectionError("Client not connected")
        
        try:
            kwargs = {}
            if count:
                kwargs['count'] = count
            if block is not None:
                kwargs['block'] = block
            
            results = await self.redis.xread(streams, **kwargs)
            
            # Deserialize labels
            for stream_key, entries in results or []:
                for entry_id, data in entries:
                    self._deserialize_labels(data)
            
            logger.debug(f"XREAD: Read from {len(streams)} stream(s)")
            return results or []
        
        except Exception as e:
            logger.error(f"Failed to read from Redis streams: {e}")
            raise RedisConnectionError(f"XREAD operation failed: {str(e)}")
    
    async def xlen(self) -> int:
        """
        Get length of Redis Stream.
        
        Returns:
            Number of entries in stream
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            length = await self.redis.xlen(self.config.stream_key)
            logger.debug(f"Stream length: {length} entries")
            return length
        except Exception as e:
            logger.error(f"Failed to get stream length: {e}")
            raise RedisConnectionError(f"XLEN operation failed: {str(e)}")
    
    async def xinfo_stream(self) -> Dict:
        """
        Get detailed stream information.
        
        Returns:
            Stream metadata dictionary
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            info = await self.redis.xinfo_stream(self.config.stream_key)
            logger.debug(f"Stream info: {info}")
            return info
        except Exception as e:
            logger.error(f"Failed to get stream info: {e}")
            raise RedisConnectionError(f"XINFO STREAM operation failed: {str(e)}")
    
    async def create_consumer_group(self, start_id: str = "$") -> bool:
        """
        Create consumer group for stream (idempotent).
        
        If group already exists, silently returns True.
        
        Args:
            start_id: Starting point for new consumers ("$" = end, "0" = start)
        
        Returns:
            True if successful, False if error
        """
        if not self.redis:
            logger.error("Redis client not connected")
            return False
        
        try:
            # Try to create group, ignore if already exists
            try:
                await self.redis.xgroup_create(
                    self.config.stream_key,
                    self.config.consumer_group,
                    id=start_id,
                    mkstream=True
                )
                logger.info(f"✓ Created consumer group: {self.config.consumer_group}")
            except RedisResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.debug(f"Consumer group already exists: {self.config.consumer_group}")
                else:
                    raise
            
            return True
        
        except Exception as e:
            logger.error(f"✗ Failed to create consumer group: {e}")
            return False
    
    async def xreadgroup(
        self,
        count: Optional[int] = None,
        block: Optional[int] = None
    ) -> List[Tuple[str, List[Tuple[str, Dict]]]]:
        """
        Read from consumer group with automatic acknowledgment support.
        
        Args:
            count: Maximum entries to return
            block: Block timeout in milliseconds
        
        Returns:
            List of (stream_key, [(entry_id, data), ...]) tuples
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            kwargs = {}
            if count:
                kwargs['count'] = count
            if block is not None:
                kwargs['block'] = block
            
            results = await self.redis.xreadgroup(
                self.config.consumer_group,
                self.config.consumer_name,
                {self.config.stream_key: '>'},
                **kwargs
            )
            
            # Deserialize labels
            for stream_key, entries in results or []:
                for entry_id, data in entries:
                    self._deserialize_labels(data)
            
            logger.debug(f"XREADGROUP: Read {sum(len(e) for _, e in results or [])} messages")
            return results or []
        
        except Exception as e:
            logger.error(f"Failed to read from consumer group: {e}")
            raise RedisConnectionError(f"XREADGROUP operation failed: {str(e)}")
    
    async def xack(self, entry_ids: List[str]) -> int:
        """
        Acknowledge messages in consumer group.
        
        Args:
            entry_ids: List of entry IDs to acknowledge
        
        Returns:
            Number of acknowledged entries
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        if not entry_ids:
            logger.warning("Empty entry_ids list provided to xack")
            return 0
        
        try:
            acked = await self.redis.xack(
                self.config.stream_key,
                self.config.consumer_group,
                *entry_ids
            )
            logger.debug(f"XACK: Acknowledged {acked} message(s)")
            return acked
        except Exception as e:
            logger.error(f"Failed to acknowledge messages: {e}")
            raise RedisConnectionError(f"XACK operation failed: {str(e)}")
    
    async def set_ttl(self, ttl_seconds: int = 3600) -> None:
        """
        Set TTL (auto-expire) for the stream key.
        
        After TTL expires, Redis will automatically delete the stream.
        
        Args:
            ttl_seconds: Time to live in seconds (default: 1 hour)
        
        Raises:
            RedisConnectionError: If operation fails or client not connected
        """
        if not self.redis:
            raise RedisConnectionError("Redis client not connected. Call connect() first.")
        
        try:
            await self.redis.expire(self.config.stream_key, ttl_seconds)
            logger.info(f"TTL set for stream '{self.config.stream_key}': {ttl_seconds} seconds")
        except Exception as e:
            logger.error(f"Failed to set TTL: {e}")
            raise RedisConnectionError(f"EXPIRE operation failed: {str(e)}")
