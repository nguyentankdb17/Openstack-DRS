import asyncio
import grpc

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import scoring_pb2_grpc, scoring_pb2

logger = get_logger(__name__)


class ScoringService(scoring_pb2_grpc.ScoringServiceServicer):
    async def ScoreCluster(self, request: scoring_pb2.ScoreClusterRequest, context):
        try:
            from app.scoring.cluster_imbalance import ClusterImbalanceScorer
            scorer = ClusterImbalanceScorer()
            score = 0.0  # Replace with actual score from scorer
            return scoring_pb2.ScoreClusterResponse(score=score)
        except Exception as e:
            logger.error(f"ScoreCluster error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return scoring_pb2.ScoreClusterResponse(score=0.0)

    async def ScoreHost(self, request: scoring_pb2.ScoreHostRequest, context):
        try:
            score = 0.0  # Replace with actual host score
            return scoring_pb2.ScoreHostResponse(score=score)
        except Exception as e:
            logger.error(f"ScoreHost error: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return scoring_pb2.ScoreHostResponse(score=0.0)


async def serve(host: str = "0.0.0.0", port: int = 50053):
    server = grpc.aio.server()
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(ScoringService(), server)
    server.add_insecure_port(f"{host}:{port}")
    logger.info(f"Starting Scoring gRPC server on {host}:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    setup_logging(settings.app.log_level)
    asyncio.run(serve())
