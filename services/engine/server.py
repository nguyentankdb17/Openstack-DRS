import asyncio
import grpc

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import engine_pb2_grpc, engine_pb2

logger = get_logger(__name__)


class EngineService(engine_pb2_grpc.EngineServiceServicer):
    async def ComputeDecision(self, request: engine_pb2.ComputeDecisionRequest, context):
        try:
            # Compute decisions here
            return engine_pb2.ComputeDecisionResponse(status="started")
        except Exception as e:
            logger.error(f"ComputeDecision error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return engine_pb2.ComputeDecisionResponse(status="error")

    async def ExecuteMigration(self, request: engine_pb2.ExecuteMigrationRequest, context):
        try:
            # Execute migration here
            return engine_pb2.ExecuteMigrationResponse(status="started")
        except Exception as e:
            logger.error(f"ExecuteMigration error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return engine_pb2.ExecuteMigrationResponse(status="error")


async def serve(host: str = "0.0.0.0", port: int = 50054):
    server = grpc.aio.server()
    engine_pb2_grpc.add_EngineServiceServicer_to_server(EngineService(), server)
    server.add_insecure_port(f"{host}:{port}")
    logger.info(f"Starting Engine gRPC server on {host}:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    setup_logging(settings.app.log_level)
    asyncio.run(serve())
