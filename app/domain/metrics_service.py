import pandas as pd
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app import config
from app.collector import prometheus_collector


def collect_averages_metric() -> pd.DataFrame:
	return prometheus_collector.collect_host_metric_averages(
		window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)


def collect_fully_metric(window_minutes: int | None = None) -> pd.DataFrame:
	return prometheus_collector.collect_host_metric_history(
		window_minutes=window_minutes or config.HISTORY_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)
