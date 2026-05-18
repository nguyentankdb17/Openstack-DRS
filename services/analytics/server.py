"""
drs-analytics  —  gRPC :50052
Provides time-series forecasting (Chronos) and feature building for hosts.
"""
import asyncio
import grpc
import pandas as pd

from app.utils.logger import get_logger, setup_logging
from app.core import settings

# Generated imports
from app.grpc import analytics_pb2_grpc, analytics_pb2

logger = get_logger(__name__)


class AnalyticsServicer(analytics_pb2_grpc.AnalyticsServiceServicer):

    async def Predict(
        self,
        request: analytics_pb2.PredictRequest,
        context: grpc.ServicerContext,
    ) -> analytics_pb2.PredictResponse:
        """
        Run Chronos forecasting for a single (host_id, metric) pair.
        Returns `horizon_minutes` steps of predicted values.
        """
        try:
            from app import config
            from app.domain.metrics_service import collect_fully_metric
            from app.domain.prediction_service import predict_next_window

            # Collect history for this host / all hosts (filter by host_id if given)
            history_df = await asyncio.to_thread(collect_fully_metric)

            if request.host_id:
                history_df = history_df[history_df["host"] == request.host_id]

            if history_df.empty:
                logger.warning(
                    "Predict: no history data for host_id=%s metric=%s",
                    request.host_id,
                    request.metric,
                )
                return analytics_pb2.PredictResponse(values=[], model="chronos")

            pred_df = await asyncio.to_thread(predict_next_window, history_df)

            # Extract the requested metric column
            metric_col = request.metric or "cpu"
            if metric_col in pred_df.columns:
                if request.host_id:
                    host_pred = pred_df[pred_df["host"] == request.host_id]
                    values = host_pred[metric_col].dropna().tolist()
                else:
                    values = pred_df[metric_col].dropna().tolist()
            else:
                logger.warning(
                    "Predict: metric column '%s' not found in prediction output, "
                    "available=%s",
                    metric_col,
                    list(pred_df.columns),
                )
                values = []

            logger.info(
                "Predict: host_id=%s metric=%s horizon=%d returned %d values",
                request.host_id,
                request.metric,
                request.horizon_minutes,
                len(values),
            )
            return analytics_pb2.PredictResponse(values=values, model="chronos")

        except Exception as exc:
            logger.exception("Predict error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return analytics_pb2.PredictResponse(values=[], model="")

    async def PredictCluster(
        self,
        request: analytics_pb2.PredictClusterRequest,
        context: grpc.ServicerContext,
    ) -> analytics_pb2.PredictClusterResponse:
        """
        Run Chronos forecasting for all hosts using the requested history window.
        """
        try:
            from app import config
            from app.domain.metrics_service import collect_fully_metric
            from app.domain.prediction_service import predict_next_window

            history_window = int(request.history_window_minutes or config.HISTORY_LOOKBACK_MINUTES)
            history_df = await asyncio.to_thread(
                collect_fully_metric,
                window_minutes=history_window,
            )
            if history_df.empty:
                logger.warning(
                    "PredictCluster: no history data for history_window_minutes=%d",
                    history_window,
                )
                return analytics_pb2.PredictClusterResponse(rows=[], model="chronos")

            pred_df = await asyncio.to_thread(predict_next_window, history_df)
            if pred_df.empty:
                logger.warning(
                    "PredictCluster: no prediction rows for history_window_minutes=%d",
                    history_window,
                )
                return analytics_pb2.PredictClusterResponse(rows=[], model="chronos")

            rows = []
            for row in pred_df.itertuples(index=False):
                timestamp = getattr(row, "timestamp", "")
                if isinstance(timestamp, pd.Timestamp):
                    timestamp = timestamp.isoformat()
                rows.append(
                    analytics_pb2.PredictedHostMetricRow(
                        timestamp=str(timestamp),
                        host=str(getattr(row, "host", "")),
                        cpu=float(getattr(row, "cpu", 0.0) or 0.0),
                        ram=float(getattr(row, "ram", 0.0) or 0.0),
                        swap=float(getattr(row, "swap", 0.0) or 0.0),
                    )
                )

            logger.info(
                "PredictCluster: history_window=%d horizon=%d rows=%d hosts=%d",
                history_window,
                request.horizon_minutes,
                len(rows),
                pred_df["host"].nunique(dropna=True) if "host" in pred_df.columns else 0,
            )
            return analytics_pb2.PredictClusterResponse(rows=rows, model="chronos")

        except Exception as exc:
            logger.exception("PredictCluster error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return analytics_pb2.PredictClusterResponse(rows=[], model="")

    async def BuildFeatures(
        self,
        request: analytics_pb2.BuildFeaturesRequest,
        context: grpc.ServicerContext,
    ) -> analytics_pb2.BuildFeaturesResponse:
        """Build and cache Chronos input features for a host (or all hosts)."""
        try:
            from app.domain.metrics_service import collect_fully_metric
            from app.domain.prediction_service import build_chronos_input

            history_df = await asyncio.to_thread(collect_fully_metric)
            if request.host_id:
                history_df = history_df[history_df["host"] == request.host_id]

            _ = await asyncio.to_thread(build_chronos_input, history_df)

            logger.info("BuildFeatures: host_id=%s done", request.host_id)
            return analytics_pb2.BuildFeaturesResponse(status="ok")
        except Exception as exc:
            logger.exception("BuildFeatures error: %s", exc)
            context.set_details(str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            return analytics_pb2.BuildFeaturesResponse(status="error")


async def serve(host: str = "0.0.0.0", port: int = 50052) -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_timeout_ms", 10_000),
        ]
    )
    analytics_pb2_grpc.add_AnalyticsServiceServicer_to_server(AnalyticsServicer(), server)
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("Starting drs-analytics gRPC server on %s", listen_addr)
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
