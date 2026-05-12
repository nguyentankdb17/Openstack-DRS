import pandas as pd

from app import config
from app.collector import collect_host_metric_averages, collect_host_metric_history


def collect_5m_metrics() -> pd.DataFrame:
	return collect_host_metric_averages(
		window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)


def collect_30m_metrics() -> pd.DataFrame:
	return collect_host_metric_history(
		window_minutes=config.HISTORY_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)
