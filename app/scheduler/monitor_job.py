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
        return None

    try:
        if current_decision.current_cluster_imbalance is None:
            return None

        if current_decision.current_cluster_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD:
            return None

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
            "Inventory host alignment: metrics_only=%s inventory_only=%s vm_hosts=%s",
            sorted(host_metric_hosts - host_inventory_hosts),
            sorted(host_inventory_hosts - host_metric_hosts),
            sorted(vm_hosts),
        )

        migration_plan = migration_planner.build_plan(
            host_metrics=host_metrics,
            overloaded_hosts=[],
            vm_inventory=vm_inventory,
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
            return plan_decision

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
        return execution_decisions[-1] if execution_decisions else plan_decision
    finally:
        rebalance_lock.release()

async def monitor_cluster():
    try:
        has_events, events = has_recent_vm_events(config.CHECK_EVENT_LOOKBACK_MINUTES)
        if has_events:
            decision = build_event_skip_decision(events)
            logger.info("Monitor result: %s", decision.model_dump())
            return

        metrics_df = collect_5m_metrics()
        # metrics_df.to_csv("metrics_df.csv", index=False)  # Debugging output
        current_decision = evaluate_current(metrics_df)
        logger.info("Current window decision: %s", current_decision.model_dump())
        if current_decision.current_cluster_imbalance and current_decision.current_cluster_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD:
            _execute_rebalance_cycle(current_decision)
            return

        history_df = collect_30m_metrics()
        # history_df.to_csv("history_df.csv", index=False)  # Debugging output
        # build_chronos_input(history_df).to_csv("history_df_chronos.csv", index=False)  # Chronos format
        future_df = build_predict_input(history_df)
        # future_df.to_csv("future_df.csv", index=False)  # Debugging output
        pred_df = predict_next_window(history_df, future_df)
        # pred_df.to_csv("pred_df.csv", index=False)  # Debugging output

        predicted_decision = evaluate_predicted(
            pred_df=pred_df,
            current_score=float(current_decision.current_cluster_imbalance or 0.0),
        )
        logger.info("Predicted window decision: %s", predicted_decision.model_dump())
        if predicted_decision.predicted_cluster_imbalance and predicted_decision.predicted_cluster_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD:
            _execute_rebalance_cycle(predicted_decision)
    except Exception as exc:  # pylint: disable=broad-except
        decision = build_error_decision(str(exc))
        logger.exception("Monitor cycle failed: %s", exc)
        logger.info("Monitor result: %s", decision.model_dump())

def start_scheduler():
    next_run_time = _resolve_next_run_time()
    scheduler.add_job(
        monitor_cluster,
        "interval",
        minutes=config.SCHEDULER_INTERVAL_MINUTES,
        next_run_time=next_run_time,
        misfire_grace_time=60,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    return scheduler


def stop_scheduler(scheduler):
    scheduler.shutdown()