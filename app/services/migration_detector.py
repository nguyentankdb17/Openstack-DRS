"""Migration event detector using OpenStack API."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

import openstack
from openstack.connection import Connection

logger = logging.getLogger(__name__)


class MigrationEventDetector:
    """Detects live-migration, create, and delete events from OpenStack."""
    
    def __init__(self, openstack_config):
        """
        Initialize migration event detector.
        
        Args:
            openstack_config: OpenStack configuration object
        """
        self.config = openstack_config
        self._connection: Optional[Connection] = None
        logger.info("MigrationEventDetector initialized")
    
    def _get_connection(self) -> Connection:
        """Get or create OpenStack connection. Lazy initialization."""
        if self._connection is None:
            try:
                self._connection = openstack.connect(
                    auth_url=self.config.auth_url,
                    username=self.config.username,
                    password=self.config.password,
                    project_name=self.config.project_name,
                    project_domain_id=self.config.project_domain_id,
                    user_domain_id=self.config.user_domain_id,
                    region_name=self.config.region_name,
                    connect_timeout=self.config.timeout,
                )
                logger.info(f"Connected to OpenStack at {self.config.auth_url}")
            except Exception as e:
                logger.error(f"Failed to connect to OpenStack: {e}")
                raise
        return self._connection
    
    async def check_migration_events(self, lookback_minutes: int = 5) -> bool:
        """
        Check if any migration/create/delete events occurred in the last N minutes.
        
        Runs blocking OpenStack API call in thread pool to avoid blocking async loop.
        
        Args:
            lookback_minutes: Number of minutes to look back
        
        Returns:
            True if events found, False otherwise
        """
        try:
            # Run blocking operation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._check_migration_events_sync,
                lookback_minutes
            )
            return result
        except Exception as e:
            logger.error(f"Failed to check migration events: {e}")
            return False
    
    def _check_migration_events_sync(self, lookback_minutes: int) -> bool:
        """
        Synchronous implementation of event checking.
        
        Queries OpenStack compute API for server action events.
        
        Args:
            lookback_minutes: Number of minutes to look back
        
        Returns:
            True if events found, False otherwise
        """
        try:
            conn = self._get_connection()
            
            # Calculate time window
            cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)
            cutoff_iso = cutoff_time.isoformat()
            
            logger.debug(f"Checking for events since {cutoff_iso}")
            
            # Check server actions (migrations, create, delete)
            # Server actions API returns recent server operations
            server_actions = list(conn.compute.server_actions())
            
            if not server_actions:
                logger.debug("No server actions found")
                return False
            
            # Filter actions by time and type
            recent_events = []
            for action in server_actions:
                try:
                    # action.start_time is ISO format
                    action_time_str = getattr(action, 'start_time', None)
                    if not action_time_str:
                        continue
                    
                    # Parse ISO format timestamp
                    if isinstance(action_time_str, str):
                        # Remove timezone suffix if present
                        action_time_str = action_time_str.replace('Z', '+00:00').split('.')[0]
                        action_time = datetime.fromisoformat(action_time_str.replace('Z', '+00:00'))
                    else:
                        action_time = action_time_str
                    
                    # Check if action is within lookback window and matches our event types
                    action_type = getattr(action, 'action', '').lower()
                    
                    if action_time > cutoff_time:
                        if any(event_type.lower() in action_type for event_type in ['livemigration', 'create', 'delete']):
                            recent_events.append({
                                'server_id': getattr(action, 'server_id', 'unknown'),
                                'action': action_type,
                                'timestamp': action_time.isoformat()
                            })
                except Exception as e:
                    logger.warning(f"Error parsing action {action}: {e}")
                    continue
            
            if recent_events:
                logger.info(f"Found {len(recent_events)} migration/create/delete events in last {lookback_minutes}min")
                for event in recent_events:
                    logger.debug(f"  - {event['action']} on {event['server_id']}")
                return True
            
            logger.debug(f"No migration/create/delete events found in last {lookback_minutes}min")
            return False
            
        except Exception as e:
            logger.error(f"Error checking migration events: {e}", exc_info=True)
            # On error, assume no events (fail-safe)
            return False
    
    async def close(self):
        """Close OpenStack connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("OpenStack connection closed")
                self._connection = None
            except Exception as e:
                logger.error(f"Error closing OpenStack connection: {e}")
