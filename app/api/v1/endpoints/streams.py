from fastapi import APIRouter, Depends, HTTPException
import logging

from schemas import StreamInfoResponse
from services import MetricsReaderService
from clients import AsyncRedisClient
from dependencies import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streams", tags=["Streams"])


async def get_reader_service(redis_client: AsyncRedisClient = Depends(get_redis_client)) -> MetricsReaderService:
    """Dependency: Get reader service"""
    return MetricsReaderService(redis_client)


@router.get("/info", response_model=StreamInfoResponse)
async def get_stream_info(
    reader: MetricsReaderService = Depends(get_reader_service),
) -> StreamInfoResponse:
    """
    Get Redis Stream information.
    
    Returns:
        Stream metadata including length, timestamps, consumer groups
    """
    try:
        info_dict = await reader.get_stream_info()
        
        logger.info(f"Retrieved stream info: {info_dict['length']} entries")
        
        return StreamInfoResponse(
            stream_key=info_dict["stream_key"],
            length=info_dict["length"],
            first_entry=info_dict["first_entry"],
            last_entry=info_dict["last_entry"],
            consumer_groups=info_dict["consumer_groups"],
            first_timestamp=info_dict["first_timestamp"],
            last_timestamp=info_dict["last_timestamp"],
        )
    
    except Exception as e:
        logger.error(f"Failed to get stream info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
