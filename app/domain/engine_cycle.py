from __future__ import annotations

import asyncio
import os
import statistics
from datetime import datetime, timezone

import grpc

from app import config
from app.decision.datasource.openstack_inventory import OpenStackInventoryDatasource
from app.decision.datasource.prometheus_datasource import PrometheusDatasource
from app.decision.planner.migration_planner import MigrationPlanner
from app.domain.constraint_service import load_active_affinity_rules
from app.domain.decision_service import (
	build_error_decision,
	build_event_skip_decision,
	build_migration_execution_decision,
	build_migration_plan_decision,
	evaluate_current,
	evaluate_predicted,
)
from app.domain.metrics_service import collect_30m_metrics, collect_5m_metrics
from app.domain.pending_plan_store import set_pending
from app.domain.prediction_service import predict_next_window
from app.executor.migration_executor import MigrationExecutor
from app.grpc import (
	analytics_pb2,
	analytics_pb2_grpc,
	collector_pb2,
	collector_pb2_grpc,
	scoring_pb2,
	scoring_pb2_grpc,
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _make_channel(env_host: str, default_host: str, default_port: int) -> grpc.aio.Channel:
	host = os.getenv(env_host, default_host)
	port_env = env_host.removesuffix("_HOST") + "_PORT"
	port = int(os.getenv(port_env, str(default_port)))
	return grpc.aio.insecure_channel(
		f"{host}:{port}",
		options=[
			("grpc.keepalive_time_ms", 30_000),
			("grpc.keepalive_timeout_ms", 10_000),
		],
	)


def _collector_channel() -> grpc.aio.Channel:
	return _make_channel("DRS_COLLECTOR_HOST", "drs-collector", 50051)


def _analytics_channel() -> grpc.aio.Channel:
	return _make_channel("DRS_ANALYTICS_HOST", "drs-analytics", 50052)


def _scoring_channel() -> grpc.aio.Channel:
	return _make_channel("DRS_SCORING_HOST", "drs-scoring", 50053)


async def run_decision_cycle(trigger_source: str = "scheduler") -> dict:
	"""
	Run the full DRS decision cycle for the engine runtime.

	The engine owns orchestration. Collector, scoring, and analytics are invoked
	through gRPC; local fallbacks remain for cases where an RPC service is down.
	"""
	cycle_started_at = datetime.now(timezone.utc)

	try:
		async with _collector_channel() as channel:
			stub = collector_pb2_grpc.CollectorServiceStub(channel)
			event_response = await stub.CollectEvents(
				collector_pb2.CollectEventsRequest(),
				timeout=30,
			)
		if event_response.has_events:
			events = list(event_response.events)
			decision = build_event_skip_decision(events)
			logger.info("[engine] Recent VM events detected (%d), skipping rebalance", len(events))
			record_engine_cycle(
				cycle_started_at=cycle_started_at,
				trigger_source="event_guard",
				decision=decision,
				planned=[],
				executed=[],
			)
			return {"status": "skipped_events", "events": events}
	except Exception as exc:  # pylint: disable=broad-except
		logger.warning("[engine] CollectEvents RPC failed, continuing: %s", exc)

	try:
		async with _collector_channel() as channel:
			stub = collector_pb2_grpc.CollectorServiceStub(channel)
			await stub.CollectMetrics(collector_pb2.CollectMetricsRequest(), timeout=60)
		logger.info("[engine] CollectMetrics done")
	except Exception as exc:  # pylint: disable=broad-except
		logger.warning("[engine] CollectMetrics RPC failed, continuing: %s", exc)

	current_score = await _score_cluster()
	current_decision = await _evaluate_current_window(cycle_started_at, trigger_source)
	if current_decision is None:
		return {"status": "error", "error": "evaluate_current failed"}

	if (
		current_decision.current_cluster_imbalance is None
		or current_decision.current_cluster_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD
	):
		predicted_score = await _predict_score()
		if predicted_score <= config.CLUSTER_IMBALANCE_THRESHOLD:
			logger.info("[engine] Both current and predicted imbalance are below threshold - no action")
			await _record_balanced_prediction(cycle_started_at, current_decision)
			return {"status": "balanced", "score": current_score}

	return await _plan_or_execute(cycle_started_at, trigger_source, current_decision)


async def _score_cluster() -> float:
	try:
		async with _scoring_channel() as channel:
			stub = scoring_pb2_grpc.ScoringServiceStub(channel)
			response = await stub.ScoreCluster(scoring_pb2.ScoreClusterRequest(), timeout=30)
		logger.info("[engine] Current cluster imbalance score=%.4f", response.score)
		return response.score
	except Exception as exc:  # pylint: disable=broad-except
		logger.warning("[engine] ScoreCluster RPC failed, falling back to local: %s", exc)

	try:
		from app.scoring.cluster_imbalance import compute_cluster_imbalance

		metrics_df = await asyncio.to_thread(collect_5m_metrics)
		return compute_cluster_imbalance(metrics_df)
	except Exception as exc:  # pylint: disable=broad-except
		logger.exception("[engine] Local scoring also failed: %s", exc)
		return 0.0


async def _evaluate_current_window(cycle_started_at: datetime, trigger_source: str):
	try:
		metrics_df = await asyncio.to_thread(collect_5m_metrics)
		return evaluate_current(metrics_df)
	except Exception as exc:  # pylint: disable=broad-except
		logger.exception("[engine] evaluate_current failed: %s", exc)
		decision = build_error_decision(str(exc))
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source=trigger_source,
			decision=decision,
			planned=[],
			executed=[],
			error=str(exc),
		)
		return None


async def _predict_score() -> float:
	try:
		async with _analytics_channel() as channel:
			stub = analytics_pb2_grpc.AnalyticsServiceStub(channel)
			response = await stub.Predict(
				analytics_pb2.PredictRequest(
					host_id="",
					metric="cpu",
					horizon_minutes=config.PREDICTION_HORIZON_MINUTES,
				),
				timeout=120,
			)
		predicted_score = statistics.mean(response.values) if response.values else 0.0
		logger.info("[engine] Predicted score=%.4f", predicted_score)
		return predicted_score
	except Exception as exc:  # pylint: disable=broad-except
		logger.warning("[engine] Predict RPC failed: %s", exc)
		return 0.0


async def _record_balanced_prediction(cycle_started_at: datetime, current_decision) -> None:
	try:
		history_df = await asyncio.to_thread(collect_30m_metrics)
		pred_df = await asyncio.to_thread(predict_next_window, history_df)
		predicted_decision = evaluate_predicted(
			pred_df=pred_df,
			current_score=float(current_decision.current_cluster_imbalance or 0.0),
		)
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source="monitor_only",
			decision=predicted_decision,
			planned=[],
			executed=[],
		)
	except Exception:
		logger.exception("[engine] Failed to record balanced prediction")


async def _plan_or_execute(cycle_started_at: datetime, trigger_source: str, current_decision) -> dict:
	try:
		prometheus_ds = PrometheusDatasource()
		inventory_ds = OpenStackInventoryDatasource()
		planner = MigrationPlanner()
		executor = MigrationExecutor()

		host_metrics = await asyncio.to_thread(
			lambda: list(
				prometheus_ds.build_host_snapshots(
					window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
					step_seconds=config.PREDICTION_STEP_SECONDS,
				)
			)
		)
		vm_metrics = await asyncio.to_thread(
			lambda: list(
				prometheus_ds.build_vm_snapshots(
					window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
					step_seconds=config.PREDICTION_STEP_SECONDS,
				)
			)
		)
		combined_inventory = await asyncio.to_thread(
			inventory_ds.build_inventory,
			host_metrics,
			vm_metrics,
		)
		vm_inventory = inventory_ds.extract_vm_inventory(combined_inventory)

		try:
			vm_host_rules, vm_vm_rules = load_active_affinity_rules()
		except Exception:
			vm_host_rules, vm_vm_rules = [], []

		migration_plan = await asyncio.to_thread(
			planner.build_plan,
			host_metrics=host_metrics,
			vm_inventory=vm_inventory,
			vm_host_rules=vm_host_rules,
			vm_vm_rules=vm_vm_rules,
			current_cluster_imbalance=current_decision.current_cluster_imbalance,
			inventory_payload=combined_inventory,
		)
		plan_decision = build_migration_plan_decision(migration_plan)
		logger.info("[engine] Migration plan: %d candidates", len(migration_plan.candidates))

		if not migration_plan.candidates:
			record_engine_cycle(
				cycle_started_at=cycle_started_at,
				trigger_source=trigger_source,
				decision=plan_decision,
				planned=[],
				executed=[],
			)
			return {"status": "no_candidates"}

		approval_mode = str(getattr(config, "APPROVAL_MODE", "manual")).strip().lower()
		if approval_mode != "auto":
			pending = set_pending(migration_plan, trigger_source=trigger_source)
			logger.info(
				"[engine] APPROVAL_MODE=manual - plan_id=%s staged (%d candidates)",
				pending.plan_id,
				len(migration_plan.candidates),
			)
			record_engine_cycle(
				cycle_started_at=cycle_started_at,
				trigger_source=trigger_source,
				decision=plan_decision,
				planned=migration_plan.candidates,
				executed=[],
			)
			return {
				"status": "pending_approval",
				"plan_id": pending.plan_id,
				"candidates": len(migration_plan.candidates),
			}

		max_migrations = max(1, int(config.MAX_MIGRATIONS_PER_CYCLE))
		selected = migration_plan.candidates[:max_migrations]
		executed_decisions = []
		for candidate in selected:
			result = await asyncio.to_thread(executor.execute, candidate)
			execution_decision = build_migration_execution_decision(
				candidate,
				result,
				current_score=current_decision.current_cluster_imbalance,
			)
			executed_decisions.append(execution_decision)
			logger.info(
				"[engine] Migration %s -> %s: success=%s",
				candidate.source_host,
				candidate.target_host,
				result.success,
			)

		final_decision = executed_decisions[-1] if executed_decisions else plan_decision
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source=trigger_source,
			decision=final_decision,
			planned=migration_plan.candidates,
			executed=selected,
		)
		return {
			"status": "executed",
			"executed": len(selected),
			"planned": len(migration_plan.candidates),
		}
	except Exception as exc:  # pylint: disable=broad-except
		logger.exception("[engine] Decision cycle failed: %s", exc)
		decision = build_error_decision(str(exc))
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source=trigger_source,
			decision=decision,
			planned=[],
			executed=[],
			error=str(exc),
		)
		return {"status": "error", "error": str(exc)}


def record_engine_cycle(
	*,
	cycle_started_at: datetime,
	trigger_source: str,
	decision,
	planned: list,
	executed: list,
	error: str | None = None,
) -> None:
	try:
		from app.domain.cycle_history_service import record_cycle_history

		record_cycle_history(
			cycle_started_at=cycle_started_at,
			cycle_finished_at=datetime.now(timezone.utc),
			trigger_source=trigger_source,
			decision=decision,
			planned_candidates=planned,
			executed_candidates=executed,
			error_message=error,
		)
	except Exception as exc:  # pylint: disable=broad-except
		logger.warning("[engine] Failed to record cycle history: %s", exc)
