import os
import grpc
from grpc import aio as grpc_aio

from app.core import settings

# Import generated stubs (will exist after protoc generation)
try:
    from app.grpc.analytics_pb2_grpc import AnalyticsServiceStub
    from app.grpc.analytics_pb2 import PredictRequest, BuildFeaturesRequest
    from app.grpc.scoring_pb2_grpc import ScoringServiceStub
    from app.grpc.scoring_pb2 import ScoreClusterRequest, ScoreHostRequest
    from app.grpc.engine_pb2_grpc import EngineServiceStub
    from app.grpc.engine_pb2 import ComputeDecisionRequest, ExecuteMigrationRequest
    from app.grpc.collector_pb2_grpc import CollectorServiceStub
    from app.grpc.collector_pb2 import CollectMetricsRequest, CollectEventsRequest
except Exception as e:
    AnalyticsServiceStub = None
    ScoringServiceStub = None
    EngineServiceStub = None
    CollectorServiceStub = None
    PredictRequest = BuildFeaturesRequest = None
    ScoreClusterRequest = ScoreHostRequest = None
    ComputeDecisionRequest = ExecuteMigrationRequest = None
    CollectMetricsRequest = CollectEventsRequest = None


def _channel_for(target_env: str, default_port: int) -> grpc_aio.Channel:
    host = os.getenv(target_env, f"{target_env.lower().replace('_HOST','').replace('DRS_','drs-')}")
    port = int(os.getenv(f"{target_env}_PORT", str(default_port)))
    return grpc_aio.insecure_channel(f"{host}:{port}")


def get_analytics_client() -> tuple[AnalyticsServiceStub, grpc.Channel]:
    channel = _channel_for("DRS_ANALYTICS_HOST", 50052)
    return AnalyticsServiceStub(channel), channel


def get_scoring_client() -> tuple[ScoringServiceStub, grpc.Channel]:
    channel = _channel_for("DRS_SCORING_HOST", 50053)
    return ScoringServiceStub(channel), channel


def get_engine_client() -> tuple[EngineServiceStub, grpc.Channel]:
    channel = _channel_for("DRS_ENGINE_HOST", 50054)
    return EngineServiceStub(channel), channel


def get_collector_client() -> tuple[CollectorServiceStub, grpc.Channel]:
    channel = _channel_for("DRS_COLLECTOR_HOST", 50051)
    return CollectorServiceStub(channel), channel
