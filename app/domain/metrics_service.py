import pandas as pd
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app import config


def _load_prometheus_collector():
	module_path = Path(__file__).resolve().parents[1] / "collector" / "prometheus-collector.py"
	spec = spec_from_file_location("collector.prometheus_collector", module_path)
	if spec is None or spec.loader is None:
		raise ImportError(f"Cannot load Prometheus collector from {module_path}")
	module = module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_prometheus_collector = _load_prometheus_collector()


def collect_averages_metric() -> pd.DataFrame:
	return _prometheus_collector.collect_host_metric_averages(
		window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)


def collect_fully_metric(window_minutes: int | None = None) -> pd.DataFrame:
	return _prometheus_collector.collect_host_metric_history(
		window_minutes=window_minutes or config.HISTORY_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)
