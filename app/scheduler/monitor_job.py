from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import config
from app.collector import has_recent_vm_events
from app.services.decision_service import (
    build_error_decision,
    build_event_skip_decision,
    evaluate_current,
    evaluate_predicted,
)
from app.services.metrics_service import collect_30m_metrics, collect_5m_metrics
from app.services.prediction_service import build_chronos_input, build_predict_input, predict_next_window
from app.utils.logger import get_logger

scheduler = AsyncIOScheduler()
logger = get_logger(__name__)

def monitor_cluster():
    try:
        has_events, events = has_recent_vm_events(config.CHECK_EVENT_LOOKBACK_MINUTES)
        if has_events:
            decision = build_event_skip_decision(events)
            logger.info("Monitor result: %s", decision.model_dump())
            return

        metrics_df = collect_5m_metrics()
        metrics_df.to_csv("metrics_df.csv", index=False)  # Debugging output
        current_decision = evaluate_current(metrics_df)
        logger.info("Current window decision: %s", current_decision.model_dump())
        if current_decision.current_cluster_imbalance and current_decision.current_cluster_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD:
            return

        history_df = collect_30m_metrics()
        history_df.to_csv("history_df.csv", index=False)  # Debugging output
        build_chronos_input(history_df).to_csv("history_df_chronos.csv", index=False)  # Chronos format
        future_df = build_predict_input(history_df)
        future_df.to_csv("future_df.csv", index=False)  # Debugging output
        pred_df = predict_next_window(history_df, future_df)
        pred_df.to_csv("pred_df.csv", index=False)  # Debugging output

        predicted_decision = evaluate_predicted(
            pred_df=pred_df,
            current_score=float(current_decision.current_cluster_imbalance or 0.0),
        )
        logger.info("Predicted window decision: %s", predicted_decision.model_dump())
    except Exception as exc:  # pylint: disable=broad-except
        decision = build_error_decision(str(exc))
        logger.exception("Monitor cycle failed: %s", exc)
        logger.info("Monitor result: %s", decision.model_dump())

def start_scheduler():

    scheduler.add_job(
        monitor_cluster,
        "interval",
        minutes=config.SCHEDULER_INTERVAL_MINUTES,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    return scheduler


def stop_scheduler(scheduler):
    scheduler.shutdown()