import asyncio
import grpc
from concurrent import futures

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import analytics_pb2_grpc, analytics_pb2

logger = get_logger(__name__)


class AnalyticsService(analytics_pb2_grpc.AnalyticsServiceServicer):
    async def Predict(self, request: analytics_pb2.PredictRequest, context):
        try:
            from app.services.prediction_service import PredictionService
            service = PredictionService()
            result = await service.predict_metric(request.host_id, request.metric, request.horizon_minutes)
            return analytics_pb2.PredictResponse(values=result, model="chronos")
        except Exception as e:
            logger.error(f"Predict error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return analytics_pb2.PredictResponse(values=[], model="")

    async def BuildFeatures(self, request: analytics_pb2.BuildFeaturesRequest, context):
        try:
            # Call feature builder here
            return analytics_pb2.BuildFeaturesResponse(status="started")
        except Exception as e:
            logger.error(f"BuildFeatures error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return analytics_pb2.BuildFeaturesResponse(status="error")


async def serve(host: str = "0.0.0.0", port: int = 50052):
    server = grpc.aio.server(options=[('grpc.max_send_message_length', 50 * 1024 * 1024), ('grpc.max_receive_message_length', 50 * 1024 * 1024)])
    analytics_pb2_grpc.add_AnalyticsServiceServicer_to_server(AnalyticsService(), server)
    server.add_insecure_port(f"{host}:{port}")
    logger.info(f"Starting Analytics gRPC server on {host}:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    setup_logging(settings.app.log_level)
    asyncio.run(serve())
