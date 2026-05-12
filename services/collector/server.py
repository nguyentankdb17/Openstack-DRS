"""
drs-collector  —  gRPC :50051
Collects host metrics from Prometheus and VM events from OpenStack Nova.
"""
import asyncio
import grpc

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import collector_pb2_grpc, collector_pb2

logger = get_logger(__name__)


class CollectorServicer(collector_pb2_grpc.CollectorServiceServicer):

    async def CollectMetrics(
        self,
        request: collector_pb2.CollectMetricsRequest,
        context: grpc.ServicerContext,
    ) -> collector_pb2.CollectMetricsResponse:
        """Trigger Prometheus metrics collection and persist to DB / cache."""
        try:
            from app.domain.metrics_service import collect_5m_metrics
            metrics_df = await asyncio.to_thread(collect_5m_metrics)
            row_count = len(metrics_df) if metrics_df is not None else 0
            logger.info("CollectMetrics: collected %d host rows", row_count)
            return collector_pb2.CollectMetricsResponse(
                status="ok",
                message=f"Collected {row_count} host metric rows",
            )
        except Exception as exc:
            logger.exception("CollectMetrics error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return collector_pb2.CollectMetricsResponse(status="error", message=str(exc))

    async def CollectEvents(
        self,
        request: collector_pb2.CollectEventsRequest,
        context: grpc.ServicerContext,
    ) -> collector_pb2.CollectEventsResponse:
        """Poll OpenStack Nova event log for recent VM lifecycle events."""
        try:
            from app import config
            from app.collector import has_recent_vm_events
            has_events, events = await asyncio.to_thread(
                has_recent_vm_events, config.CHECK_EVENT_LOOKBACK_MINUTES
            )
            event_count = len(events) if events else 0
            logger.info(
                "CollectEvents: has_events=%s count=%d", has_events, event_count
            )
            return collector_pb2.CollectEventsResponse(
                status="ok",
                has_events=has_events,
                event_count=event_count,
                events=events or [],
            )
        except Exception as exc:
            logger.exception("CollectEvents error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return collector_pb2.CollectEventsResponse(
                status="error", has_events=False, event_count=0
            )


async def serve(host: str = "0.0.0.0", port: int = 50051) -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 16 * 1024 * 1024),
            ("grpc.max_receive_message_length", 16 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_timeout_ms", 10_000),
        ]
    )
    collector_pb2_grpc.add_CollectorServiceServicer_to_server(CollectorServicer(), server)
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("Starting drs-collector gRPC server on %s", listen_addr)
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
