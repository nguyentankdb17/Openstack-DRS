import aiohttp
import logging
from typing import Dict, List, Optional
from exceptions import PrometheusConnectionError
from config import PrometheusConfig


logger = logging.getLogger(__name__)


class AsyncPrometheusClient:
    """Async Prometheus query client with optional auth."""
    
    def __init__(self, config: PrometheusConfig):
        """Initialize with PrometheusConfig."""
        self.base_url = config.url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=config.timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.config = config
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """Create aiohttp session with optional auth"""
        auth = None
        if self.config.username and self.config.password:
            auth = aiohttp.BasicAuth(self.config.username, self.config.password)
        
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            auth=auth
        )
        logger.info(f"Connected to Prometheus: {self.base_url}")
    
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            logger.info("Closed Prometheus connection")
    
    async def query(self, query_string: str) -> List[Dict]:
        """Execute instant PromQL query."""
        if not self.session:
            raise PrometheusConnectionError("Client not connected")
        
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/query",
                params={"query": query_string},
                timeout=self.timeout
            ) as response:
                data = await response.json()
                
                if data.get('status') != 'success':
                    error = data.get('error', 'Unknown error')
                    logger.error(f"Prometheus error: {error}")
                    raise PrometheusConnectionError(f"Query failed: {error}")
                
                logger.debug(f"Query succeeded with {len(data['data'].get('result', []))} results")
                return data.get('data', {}).get('result', [])
        
        except aiohttp.ClientError as e:
            logger.error(f"Prometheus connection error: {e}")
            raise PrometheusConnectionError(f"Connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            raise PrometheusConnectionError(str(e))
    
    async def query_range(
        self, 
        query_string: str, 
        start: str, 
        end: str, 
        step: str = "1m"
    ) -> List[Dict]:
        """Execute range query against Prometheus."""
        if not self.session:
            raise PrometheusConnectionError("Client not connected")
        
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": query_string,
                    "start": start,
                    "end": end,
                    "step": step
                },
                timeout=self.timeout
            ) as response:
                data = await response.json()
                
                if data.get('status') != 'success':
                    error = data.get('error', 'Unknown error')
                    logger.error(f"Prometheus error: {error}")
                    raise PrometheusConnectionError(f"Range query failed: {error}")
                
                results = data.get('data', {}).get('result', [])
                logger.debug(f"Range query succeeded with {len(results)} series")
                return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Prometheus connection error: {e}")
            raise PrometheusConnectionError(f"Connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Prometheus range query failed: {e}")
            raise PrometheusConnectionError(str(e))
    
    async def get_all_instances(self, job: str = "compute-node-exporter") -> List[str]:
        try:
            query = f'node_uname_info{{job="{job}"}}'
            results = await self.query(query)
            
            instances = []
            for result in results:
                instance = result.get('metric', {}).get('instance')
                if instance and instance not in instances:
                    instances.append(instance)
            
            logger.info(f"Found {len(instances)} instances from job '{job}'")
            return instances
        
        except Exception as e:
            logger.error(f"Failed to get instances: {e}")
            return []
    
    async def get_all_libvirt_instances(self) -> List[str]:
        return await self.get_all_instances(job="libvirt-exporter")
