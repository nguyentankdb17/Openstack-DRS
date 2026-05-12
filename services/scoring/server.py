"""
drs-scoring  —  gRPC :50053
Computes cluster-level and host-level imbalance scores.
"""
import asyncio
import grpc

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import scoring_pb2_grpc, scoring_pb2

logger = get_logger(__name__)


class ScoringServicer(scoring_pb2_grpc.ScoringServiceServicer):

    async def ScoreCluster(
        self,
        request: scoring_pb2.ScoreClusterRequest,
        context: grpc.ServicerContext,
    ) -> scoring_pb2.ScoreClusterResponse:
        """Compute current cluster imbalance score from live Prometheus metrics."""
        try:
            from app.domain.metrics_service import collect_5m_metrics
            from app.scoring.cluster_imbalance import compute_cluster_imbalance

            metrics_df = await asyncio.to_thread(collect_5m_metrics)
            score = compute_cluster_imbalance(metrics_df)

            logger.info("ScoreCluster: score=%.4f", score)
            return scoring_pb2.ScoreClusterResponse(score=score)
        except Exception as exc:
            logger.exception("ScoreCluster error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return scoring_pb2.ScoreClusterResponse(score=0.0)

    async def ScoreHost(
        self,
        request: scoring_pb2.ScoreHostRequest,
        context: grpc.ServicerContext,
    ) -> scoring_pb2.ScoreHostResponse:
        """Compute imbalance contribution for a specific host."""
        try:
            from app.domain.metrics_service import collect_5m_metrics
            from app.scoring.cluster_imbalance import compute_cluster_imbalance

            metrics_df = await asyncio.to_thread(collect_5m_metrics)

            if request.host_id:
                host_df = metrics_df[metrics_df["host"] == request.host_id]
                if host_df.empty:
                    logger.warning(
                        "ScoreHost: host_id=%s not found in metrics", request.host_id
                    )
                    return scoring_pb2.ScoreHostResponse(score=0.0)
                # Score the cluster as if only this host existed
                score = compute_cluster_imbalance(host_df)
            else:
                score = compute_cluster_imbalance(metrics_df)

            logger.info("ScoreHost: host_id=%s score=%.4f", request.host_id, score)
            return scoring_pb2.ScoreHostResponse(score=score)
        except Exception as exc:
            logger.exception("ScoreHost error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return scoring_pb2.ScoreHostResponse(score=0.0)


async def serve(host: str = "0.0.0.0", port: int = 50053) -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 16 * 1024 * 1024),
            ("grpc.max_receive_message_length", 16 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_timeout_ms", 10_000),
        ]
    )
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(ScoringServicer(), server)
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("Starting drs-scoring gRPC server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    import os, sys
    if __package__ in {None, ""}:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    setup_logging(settings.app.log_level)
    asyncio.run(serve())
