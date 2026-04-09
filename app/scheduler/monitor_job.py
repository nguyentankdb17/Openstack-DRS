import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone
import logging
from threading import Lock

from app import config
from app.collector import has_recent_vm_events
from app.decision.datasource.openstack_inventory import OpenStackInventoryDatasource
from app.decision.datasource.prometheus_datasource import PrometheusDatasource
from app.decision.planner.migration_planner import MigrationPlanner
from app.executor.migration_executor import MigrationExecutor
from app.models.schemas import ClusterDecision, MigrationCandidate
from app.services.constraint_service import load_active_affinity_rules
from app.services.cycle_history_service import record_cycle_history
from app.services.decision_service import (
    build_error_decision,
    build_event_skip_decision,
    build_migration_execution_decision,
    build_migration_plan_decision,
    evaluate_current,
    evaluate_predicted,
)
from app.services.metrics_service import collect_30m_metrics, collect_5m_metrics
from app.services.prediction_service import build_chronos_input, build_predict_input, predict_next_window
from app.utils.logger import get_logger

scheduler = AsyncIOScheduler()
logger = get_logger(__name__)
prometheus_datasource = PrometheusDatasource()
inventory_datasource = OpenStackInventoryDatasource()
migration_planner = MigrationPlanner()
migration_executor = MigrationExecutor()
rebalance_lock = Lock()
MONITOR_JOB_ID = "monitor_cluster_job"


def _safe_load_affinity_rules():
    try:
        return load_active_affinity_rules()
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to load constraints from database: %s", exc)
        return [], []


def _safe_record_cycle_history(
    *,
    cycle_started_at: datetime,
    cycle_finished_at: datetime,
    trigger_source: str,
    decision: ClusterDecision,
    planned_candidates: list[MigrationCandidate],
    executed_candidates: list[MigrationCandidate],
    error_message: str | None = None,
) -> None:
    try:
        record_cycle_history(
            cycle_started_at=cycle_started_at,
            cycle_finished_at=cycle_finished_at,
            trigger_source=trigger_source,
            decision=decision,
            planned_candidates=planned_candidates,
            executed_candidates=executed_candidates,
            error_message=error_message,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to write cycle history: %s", exc)


def _resolve_next_run_time() -> datetime | None:
    start_mode = config.SCHEDULER_START_MODE
    if start_mode == "immediate":
        delay_seconds = max(config.SCHEDULER_STARTUP_DELAY_SECONDS, 0)
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        logger.info(
            "Scheduler start mode=immediate, first run at %s (delay=%ss)",
            next_run_time.isoformat(),
            delay_seconds,
        )
        return next_run_time

    if start_mode != "lazy":
        logger.warning(
            "Invalid SCHEDULER_START_MODE=%s. Falling back to lazy mode.",
            start_mode,
        )

    logger.info("Scheduler start mode=lazy, first run follows the interval schedule")
    return None


def _execute_rebalance_cycle(current_decision):
	if not rebalance_lock.acquire(blocking=False):
		logger.info("Rebalance cycle already in progress, skipping this tick")
		return None, [], []

	try:
		if current_decision.current_cluster_imbalance is None:
			return None, [], []

		if current_decision.current_cluster_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD and current_decision.predicted_cluster_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD:
			return None, [], []

		host_metrics = [
			metric
			for metric in prometheus_datasource.build_host_snapshots(
				window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
				step_seconds=config.PREDICTION_STEP_SECONDS,
			)
		]
		vm_metrics = [
			metric
			for metric in prometheus_datasource.build_vm_snapshots(
				window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
				step_seconds=config.PREDICTION_STEP_SECONDS,
			)
		]
		combined_inventory = inventory_datasource.build_inventory(host_metrics=host_metrics, vm_metrics=vm_metrics)
		vm_inventory = inventory_datasource.extract_vm_inventory(combined_inventory)
		vm_host_rules, vm_vm_rules = _safe_load_affinity_rules()

		if logger.isEnabledFor(logging.DEBUG):
			logger.debug(
				"Combined inventory payload: %s",
				combined_inventory,
			)

		host_metric_hosts = {metric.host for metric in host_metrics}
		host_inventory_hosts = {item.get("hostname", "unknown") for item in combined_inventory}
		vm_hosts = {vm.current_host for vm in vm_inventory}
		unknown_vm_host_count = sum(1 for vm in vm_inventory if vm.current_host == "unknown")
		logger.debug(
			"Inventory diagnostics: host_metrics=%d vm_metrics=%d host_inventory=%d vm_inventory=%d unknown_vm_hosts=%d",
			len(host_metrics),
			len(vm_metrics),
			len(combined_inventory),
			len(vm_inventory),
			unknown_vm_host_count,
		)
		logger.debug(
			"Placement policies loaded: vm_host_rules=%d vm_vm_rules=%d",
			len(vm_host_rules),
			len(vm_vm_rules),
		)
		logger.debug(
			"Inventory host alignment: metrics_only=%s inventory_only=%s vm_hosts=%s",
			sorted(host_metric_hosts - host_inventory_hosts),
			sorted(host_inventory_hosts - host_metric_hosts),
			sorted(vm_hosts),
		)

		migration_plan = migration_planner.build_plan(
			host_metrics=host_metrics,
			vm_inventory=vm_inventory,
			vm_host_rules=vm_host_rules,
			vm_vm_rules=vm_vm_rules,
			current_cluster_imbalance=current_decision.current_cluster_imbalance,
			inventory_payload=combined_inventory,
		)
		plan_decision = build_migration_plan_decision(migration_plan)
		logger.info(
			"New migration plan created with %d candidates: %s",
			len(migration_plan.candidates),
			plan_decision.model_dump(),
		)

		if not migration_plan.candidates:
			logger.info("No feasible migration candidates found")
			return plan_decision, [], []

		max_migrations = max(1, int(config.MAX_MIGRATIONS_PER_CYCLE))
		selected_candidates = migration_plan.candidates[:max_migrations]
		execution_decisions = []
		for candidate_index, selected_candidate in enumerate(selected_candidates, start=1):
			execution_result = migration_executor.execute(selected_candidate)
			execution_decision = build_migration_execution_decision(
				selected_candidate,
				execution_result,
				current_score=current_decision.current_cluster_imbalance,
			)
			execution_decisions.append(execution_decision)
			logger.info(
				"Migration execution decision [candidate %d/%d]: %s",
				candidate_index,
				len(selected_candidates),
				execution_decision.model_dump(),
			)

		logger.info(
			"Plan execution complete. Processed %d/%d candidates.",
			len(selected_candidates),
			len(migration_plan.candidates),
		)
		final_decision = execution_decisions[-1] if execution_decisions else plan_decision
		return final_decision, migration_plan.candidates, selected_candidates
	finally:
		rebalance_lock.release()



def _monitor_cluster_sync():
	cycle_started_at = datetime.now(timezone.utc)
	try:
		has_events, events = has_recent_vm_events(config.CHECK_EVENT_LOOKBACK_MINUTES)
		if has_events:
			decision = build_event_skip_decision(events)
			logger.info("Monitor result: %s", decision.model_dump())
			_safe_record_cycle_history(
				cycle_started_at=cycle_started_at,
				cycle_finished_at=datetime.now(timezone.utc),
				trigger_source="event_guard",
				decision=decision,
				planned_candidates=[],
				executed_candidates=[],
			)
			return

		metrics_df = collect_5m_metrics()
		current_decision = evaluate_current(metrics_df)
		logger.info("Current window decision: %s", current_decision.model_dump())
		if current_decision.current_cluster_imbalance and current_decision.current_cluster_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD:
			final_decision, planned_candidates, executed_candidates = _execute_rebalance_cycle(current_decision)
			_safe_record_cycle_history(
				cycle_started_at=cycle_started_at,
				cycle_finished_at=datetime.now(timezone.utc),
				trigger_source="current_window",
				decision=final_decision or current_decision,
				planned_candidates=planned_candidates,
				executed_candidates=executed_candidates,
			)
			return

		history_df = collect_30m_metrics()
		future_df = build_predict_input(history_df)
		pred_df = predict_next_window(history_df, future_df)

		predicted_decision = evaluate_predicted(
			pred_df=pred_df,
			current_score=float(current_decision.current_cluster_imbalance or 0.0),
		)
		logger.info("Predicted window decision: %s", predicted_decision.model_dump())
		if predicted_decision.predicted_cluster_imbalance and predicted_decision.predicted_cluster_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD:
			final_decision, planned_candidates, executed_candidates = _execute_rebalance_cycle(predicted_decision)
			_safe_record_cycle_history(
				cycle_started_at=cycle_started_at,
				cycle_finished_at=datetime.now(timezone.utc),
				trigger_source="predicted_window",
				decision=final_decision or predicted_decision,
				planned_candidates=planned_candidates,
				executed_candidates=executed_candidates,
			)
			return

		_safe_record_cycle_history(
			cycle_started_at=cycle_started_at,
			cycle_finished_at=datetime.now(timezone.utc),
			trigger_source="monitor_only",
			decision=predicted_decision,
			planned_candidates=[],
			executed_candidates=[],
		)
	except Exception as exc:  # pylint: disable=broad-except
		decision = build_error_decision(str(exc))
		logger.exception("Monitor cycle failed: %s", exc)
		logger.info("Monitor result: %s", decision.model_dump())
		_safe_record_cycle_history(
			cycle_started_at=cycle_started_at,
			cycle_finished_at=datetime.now(timezone.utc),
			trigger_source="error",
			decision=decision,
			planned_candidates=[],
			executed_candidates=[],
			error_message=str(exc),
		)


async def monitor_cluster():
	await asyncio.to_thread(_monitor_cluster_sync)


def _ensure_monitor_job():
	job = scheduler.get_job(MONITOR_JOB_ID)
	if job is None:
		next_run_time = _resolve_next_run_time()
		scheduler.add_job(
			monitor_cluster,
			"interval",
			id=MONITOR_JOB_ID,
			minutes=config.SCHEDULER_INTERVAL_MINUTES,
			next_run_time=next_run_time,
			misfire_grace_time=60,
			max_instances=1,
			coalesce=True,
			replace_existing=True,
		)
	return scheduler.get_job(MONITOR_JOB_ID)


def pause_monitor_job() -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "pause_failed",
			"scheduler_running": scheduler.running,
		}

	scheduler.pause_job(job.id)
	return {
		"job_id": job.id,
		"action": "paused",
		"scheduler_running": scheduler.running,
	}


def restart_monitor_job(run_now: bool = False) -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "restart_failed",
			"run_now": run_now,
			"scheduler_running": scheduler.running,
			"next_run_time": None,
		}

	if not scheduler.running:
		scheduler.start()

	scheduler.resume_job(job.id)
	if run_now:
		scheduler.modify_job(job.id, next_run_time=datetime.now(timezone.utc))

	updated_job = scheduler.get_job(job.id)
	return {
		"job_id": job.id,
		"action": "restarted",
		"run_now": run_now,
		"scheduler_running": scheduler.running,
		"next_run_time": updated_job.next_run_time.isoformat() if updated_job and updated_job.next_run_time else None,
	}


def apply_monitor_job_runtime_config(run_now: bool = False) -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "apply_config_failed",
			"run_now": run_now,
			"scheduler_running": scheduler.running,
			"next_run_time": None,
		}

	if not scheduler.running:
		scheduler.start()

	was_paused = bool(job.next_run_time is None)
	scheduler.reschedule_job(
		job.id,
		trigger="interval",
		minutes=config.SCHEDULER_INTERVAL_MINUTES,
	)

	if run_now:
		scheduler.modify_job(job.id, next_run_time=datetime.now(timezone.utc))

	if was_paused:
		scheduler.pause_job(job.id)

	updated_job = scheduler.get_job(job.id)
	return {
		"job_id": job.id,
		"action": "config_applied",
		"run_now": run_now,
		"scheduler_running": scheduler.running,
		"next_run_time": updated_job.next_run_time.isoformat() if updated_job and updated_job.next_run_time else None,
		"interval_minutes": config.SCHEDULER_INTERVAL_MINUTES,
	}


def get_monitor_job_status() -> dict:
	job = scheduler.get_job(MONITOR_JOB_ID)
	return {
		"job_id": MONITOR_JOB_ID,
		"scheduler_running": scheduler.running,
		"job_exists": job is not None,
		"paused": bool(job and job.next_run_time is None),
		"next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
	}


def start_scheduler():
	_ensure_monitor_job()
	if not scheduler.running:
		scheduler.start()

	return scheduler


def stop_scheduler(scheduler):
	scheduler.shutdown()