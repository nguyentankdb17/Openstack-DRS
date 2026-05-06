import asyncio
import grpc

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import collector_pb2_grpc, collector_pb2

logger = get_logger(__name__)


class CollectorService(collector_pb2_grpc.CollectorServiceServicer):
    async def CollectMetrics(self, request: collector_pb2.CollectMetricsRequest, context):
        try:
            # Trigger metrics collection
            return collector_pb2.CollectMetricsResponse(status="started")
        except Exception as e:
            logger.error(f"CollectMetrics error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return collector_pb2.CollectMetricsResponse(status="error")

    async def CollectEvents(self, request: collector_pb2.CollectEventsRequest, context):
        try:
            # Trigger event collection
            return collector_pb2.CollectEventsResponse(status="started")
        except Exception as e:
            logger.error(f"CollectEvents error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return collector_pb2.CollectEventsResponse(status="error")


async def serve(host: str = "0.0.0.0", port: int = 50051):
    server = grpc.aio.server()
    collector_pb2_grpc.add_CollectorServiceServicer_to_server(CollectorService(), server)
    server.add_insecure_port(f"{host}:{port}")
    logger.info(f"Starting Collector gRPC server on {host}:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    setup_logging(settings.app.log_level)
    asyncio.run(serve())
