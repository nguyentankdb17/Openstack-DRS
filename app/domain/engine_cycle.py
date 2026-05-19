from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import grpc
import pandas as pd

from app import config
from app.core import constants
from app.core.constants import METRIC_COLUMNS
from app.decision.datasource.openstack_inventory import OpenStackInventoryDatasource
from app.decision.datasource.prometheus_datasource import PrometheusDatasource
from app.decision.planner.migration_planner import MigrationPlanner
from app.domain.constraint_service import load_active_constraint_rules
from app.domain.decision_service import (
	build_error_decision,
	build_event_skip_decision,
	build_migration_execution_decision,
	build_migration_plan_decision,
	evaluate_current,
	evaluate_predicted,
	set_latest_decision,
)
from app.domain.metrics_service import collect_averages_metric
from app.domain.pending_plan_store import set_pending
from app.executor.migration_executor import MigrationExecutor
from app.models.schemas import HostMetricSnapshot
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


def _scoring_channel() -> grpc.aio.Channel:
	return _make_channel("DRS_SCORING_HOST", "drs-scoring", 50053)


def _analytics_channel() -> grpc.aio.Channel:
	return _make_channel("DRS_ANALYTICS_HOST", "drs-analytics", 50052)


async def run_decision_cycle(trigger_source: str = "rpc") -> dict:
	cycle_started_at = datetime.now(timezone.utc)
	logger.info("[engine] Decision cycle started: trigger_source=%s", trigger_source)

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
	except Exception as exc:  
		logger.warning("[engine] CollectEvents RPC failed, continuing: %s", exc)

	try:
		async with _collector_channel() as channel:
			stub = collector_pb2_grpc.CollectorServiceStub(channel)
			await stub.CollectMetrics(collector_pb2.CollectMetricsRequest(), timeout=60)
		logger.info("[engine] CollectMetrics done")
	except Exception as exc:  
		logger.warning("[engine] CollectMetrics RPC failed, continuing: %s", exc)

	current_score = await _score_cluster()
	current_decision = await _evaluate_current_window(cycle_started_at, trigger_source)
	if current_decision is None:
		return {"status": "error", "error": "evaluate_current failed"}

	if (
		current_decision.current_cluster_imbalance is None
		or current_decision.current_cluster_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD
	):
		logger.info("[engine] Current imbalance is below threshold - evaluating prediction")
		predicted_decision, pred_df, prediction_results = await _record_balanced_prediction(
			cycle_started_at,
			current_decision,
		)
		if (
			predicted_decision is not None
			and predicted_decision.status == constants.STATUS_PREDICTED_IMBALANCED
		):
			logger.info(
				"[engine] Predicted imbalance is above threshold - planning from predicted window"
			)
			return await _plan_or_execute(
				cycle_started_at,
				"predicted_imbalance",
				predicted_decision,
				pred_df=pred_df,
				prediction_results=prediction_results,
			)
		return {
			"status": "monitor_only",
			"score": current_score,
			"predicted_status": predicted_decision.status if predicted_decision else None,
			"predicted_cluster_imbalance": (
				predicted_decision.predicted_cluster_imbalance if predicted_decision else None
			),
		}

	return await _plan_or_execute(cycle_started_at, trigger_source, current_decision)


async def _score_cluster() -> float:
	try:
		async with _scoring_channel() as channel:
			stub = scoring_pb2_grpc.ScoringServiceStub(channel)
			response = await stub.ScoreCluster(scoring_pb2.ScoreClusterRequest(), timeout=30)
		logger.info("[engine] Current cluster imbalance score=%.4f", response.score)
		return response.score
	except Exception as exc:  
		logger.warning("[engine] ScoreCluster RPC failed, falling back to local: %s", exc)

	try:
		from app.scoring.cluster_imbalance import compute_cluster_imbalance

		metrics_df = await asyncio.to_thread(collect_averages_metric)
		return compute_cluster_imbalance(metrics_df)
	except Exception as exc:  
		logger.exception("[engine] Local scoring also failed: %s", exc)
		return 0.0


async def _evaluate_current_window(cycle_started_at: datetime, trigger_source: str):
	try:
		metrics_df = await asyncio.to_thread(collect_averages_metric)
		return evaluate_current(metrics_df)
	except Exception as exc:  
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


async def _record_balanced_prediction(cycle_started_at: datetime, current_decision):
	try:
		current_score = float(current_decision.current_cluster_imbalance or 0.0)
		window_minutes = int(config.HISTORY_LOOKBACK_MINUTES)
		result = await _predict_balanced_window(window_minutes, current_score)
		predicted_decision = result["decision"].model_copy(
			update={
				"details": (
					f"History lookback prediction evaluated "
					f"({result['window_minutes']} minutes)"
				)
			}
		)
		set_latest_decision(predicted_decision)
		pred_df = result["pred_df"]
		prediction_payload = _prediction_results_payload(result)
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source="monitor_only",
			decision=predicted_decision,
			planned=[],
			executed=[],
			prediction_results=prediction_payload,
		)
		return predicted_decision, pred_df, prediction_payload
	except Exception:
		logger.exception("[engine] Failed to record balanced prediction")
		return None, pd.DataFrame(columns=["timestamp", "host", *METRIC_COLUMNS]), {}


async def _predict_balanced_window(
	window_minutes: int,
	current_score: float,
) -> dict:
	pred_df = await _predict_next_window_via_analytics(window_minutes)
	predicted_decision = evaluate_predicted(
		pred_df=pred_df,
		current_score=current_score,
	)
	logger.info(
		"[engine] history-lookback prediction evaluated: history_lookback_minutes=%d predicted_imbalance=%.4f status=%s",
		window_minutes,
		float(predicted_decision.predicted_cluster_imbalance or 0.0),
		predicted_decision.status,
	)
	return {
		"window_minutes": window_minutes,
		"decision": predicted_decision,
		"pred_df": pred_df,
	}


def _prediction_df_records(pred_df: pd.DataFrame) -> list[dict]:
	if pred_df is None or pred_df.empty:
		return []

	records_df = pred_df[["timestamp", "host", *METRIC_COLUMNS]].copy()
	records_df["timestamp"] = pd.to_datetime(records_df["timestamp"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
	return records_df.to_dict(orient="records")


def _prediction_results_payload(prediction_result: dict) -> dict[str, dict]:
	decision = prediction_result["decision"]
	return {
		"history_lookback": {
			"mode": "history-lookback-prediction",
			"window_minutes": int(prediction_result["window_minutes"]),
			"selected": True,
			"status": decision.status,
			"predicted_cluster_imbalance": decision.predicted_cluster_imbalance,
			"rows": _prediction_df_records(prediction_result["pred_df"]),
		}
	}


async def _predict_next_window_via_analytics(window_minutes: int) -> pd.DataFrame:
	async with _analytics_channel() as channel:
		stub = analytics_pb2_grpc.AnalyticsServiceStub(channel)
		response = await stub.PredictCluster(
			analytics_pb2.PredictClusterRequest(
				horizon_minutes=config.PREDICTION_HORIZON_MINUTES,
				history_lookback_minutes=window_minutes,
			),
			timeout=180,
		)

	rows = [
		{
			"timestamp": row.timestamp,
			"host": row.host,
			"cpu": float(row.cpu),
			"ram": float(row.ram),
			"swap": float(row.swap),
		}
		for row in response.rows
	]

	logger.info(
		"[engine] Analytics PredictCluster completed via gRPC: window_minutes=%d rows=%d model=%s",
		window_minutes,
		len(rows),
		response.model,
	)
	return pd.DataFrame(rows)


def _predicted_host_snapshots(
	pred_df: pd.DataFrame,
	current_host_metrics: list[HostMetricSnapshot],
) -> list[HostMetricSnapshot]:
	if pred_df is None or pred_df.empty or "host" not in pred_df.columns:
		return current_host_metrics

	current_by_host = {metric.host: metric for metric in current_host_metrics}
	predicted_means = pred_df.groupby("host", as_index=False)[METRIC_COLUMNS].mean(numeric_only=True)
	predicted_hosts: list[HostMetricSnapshot] = []
	for row in predicted_means.itertuples(index=False):
		host = str(row.host)
		current = current_by_host.get(host)
		if current is None:
			logger.info(
				"[engine] skipping predicted host without current metrics: host=%s",
				host,
			)
			continue
		predicted_hosts.append(
			HostMetricSnapshot(
				host=host,
				cpu=float(getattr(row, "cpu", 0) or 0),
				ram=float(getattr(row, "ram", 0) or 0),
				swap=float(getattr(row, "swap", 0) or 0),
				running_vm=float(getattr(current, "running_vm", 0) or 0),
				cpu_allocated=float(getattr(current, "cpu_allocated", 0) or 0),
				ram_allocated=float(getattr(current, "ram_allocated", 0) or 0),
				swap_allocated=float(getattr(current, "swap_allocated", 0) or 0),
			)
		)

	return predicted_hosts or current_host_metrics


def _planning_imbalance(decision) -> float | None:
	if decision.status == constants.STATUS_PREDICTED_IMBALANCED:
		return decision.predicted_cluster_imbalance
	return decision.current_cluster_imbalance


def _predicted_imbalance_for_plan(decision) -> float | None:
	if decision.status == constants.STATUS_PREDICTED_IMBALANCED:
		return decision.predicted_cluster_imbalance
	return None


async def _plan_or_execute(
	cycle_started_at: datetime,
	trigger_source: str,
	current_decision,
	pred_df: pd.DataFrame | None = None,
	prediction_results: dict[str, dict] | None = None,
) -> dict:
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
		if pred_df is not None and current_decision.status == constants.STATUS_PREDICTED_IMBALANCED:
			host_metrics = _predicted_host_snapshots(pred_df, host_metrics)
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
			vm_host_rules, vm_vm_rules, exclude_rules = load_active_constraint_rules()
		except Exception:
			vm_host_rules, vm_vm_rules, exclude_rules = [], [], []

		migration_plan = await asyncio.to_thread(
			planner.build_plan,
			host_metrics=host_metrics,
			vm_inventory=vm_inventory,
			vm_host_rules=vm_host_rules,
			vm_vm_rules=vm_vm_rules,
			exclude_rules=exclude_rules,
			current_cluster_imbalance=current_decision.current_cluster_imbalance,
			predicted_cluster_imbalance=_predicted_imbalance_for_plan(current_decision),
			planning_cluster_imbalance=_planning_imbalance(current_decision),
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
				prediction_results=prediction_results,
			)
			return {"status": "no_candidates"}

		approval_mode = str(getattr(config, "APPROVAL_MODE", "manual")).strip().lower()
		if approval_mode != "auto":
			pending = set_pending(
				migration_plan,
				trigger_source=trigger_source,
				cycle_started_at=cycle_started_at,
			)
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
				prediction_results=prediction_results,
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
				predicted_score=_predicted_imbalance_for_plan(current_decision),
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
			prediction_results=prediction_results,
		)
		return {
			"status": "executed",
			"executed": len(selected),
			"planned": len(migration_plan.candidates),
		}
	except Exception as exc:  
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
	prediction_results: dict[str, dict] | None = None,
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
			prediction_results=prediction_results,
			error_message=error,
		)
	except Exception as exc:  
		logger.warning("[engine] Failed to record cycle history: %s", exc)
