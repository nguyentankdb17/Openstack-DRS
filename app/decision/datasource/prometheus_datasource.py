from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Iterable

import pandas as pd

from app import config
from app.models.schemas import HostMetricSnapshot, VMMetricSnapshot


def _load_prometheus_collector():
	module_path = Path(__file__).resolve().parents[2] / "collector" / "prometheus-collector.py"
	spec = spec_from_file_location("collector.prometheus_collector", module_path)
	if spec is None or spec.loader is None:
		raise ImportError(f"Cannot load Prometheus collector from {module_path}")
	module = module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


_prometheus_collector = _load_prometheus_collector()


@dataclass(slots=True)
class PrometheusDatasource:
	def collect_host_metrics(self, window_minutes: int | None = None, step_seconds: int | None = None) -> pd.DataFrame:
		return _prometheus_collector.collect_host_metric_averages(
			window_minutes=window_minutes or config.CHECK_EVENT_LOOKBACK_MINUTES,
			step_seconds=step_seconds or config.PREDICTION_STEP_SECONDS,
		)

	def collect_vm_metrics(
		self,
		window_minutes: int | None = None,
		step_seconds: int | None = None,
	) -> list[VMMetricSnapshot]:
		return _prometheus_collector.collect_vm_metric_averages(
			window_minutes=window_minutes or config.CHECK_EVENT_LOOKBACK_MINUTES,
			step_seconds=step_seconds or config.PREDICTION_STEP_SECONDS,
		)

	def collect_host_history(self, window_minutes: int | None = None, step_seconds: int | None = None) -> pd.DataFrame:
		return _prometheus_collector.collect_host_metric_history(
			window_minutes=window_minutes or config.HISTORY_LOOKBACK_MINUTES,
			step_seconds=step_seconds or config.PREDICTION_STEP_SECONDS,
		)

	def build_host_snapshots(
		self,
		window_minutes: int | None = None,
		step_seconds: int | None = None,
		hosts: Iterable[str] | None = None,
	) -> list[HostMetricSnapshot]:
		metrics_df = self.collect_host_metrics(window_minutes=window_minutes, step_seconds=step_seconds)
		if metrics_df.empty:
			return []

		if hosts is not None:
			host_filter = {host for host in hosts}
			metrics_df = metrics_df[metrics_df["host"].isin(host_filter)]

		return [
			HostMetricSnapshot(
				host=row.host,
				cpu=float(row.cpu or 0),
				ram=float(row.ram or 0),
				swap=float(row.swap or 0),
				running_vm=float(getattr(row, "running_vm", 0) or 0),
				cpu_allocated=float(getattr(row, "cpu_allocated", 0) or 0),
				ram_allocated=float(getattr(row, "ram_allocated", 0) or 0),
				swap_allocated=float(getattr(row, "swap_allocated", 0) or 0),
			)
			for row in metrics_df.itertuples(index=False)
		]

	def build_vm_snapshots(
		self,
		window_minutes: int | None = None,
		step_seconds: int | None = None,
		hosts: Iterable[str] | None = None,
	) -> list[VMMetricSnapshot]:
		metrics = self.collect_vm_metrics(window_minutes=window_minutes, step_seconds=step_seconds)
		if not metrics:
			return []

		if hosts is None:
			return metrics

		host_filter = {host for host in hosts}
		return [metric for metric in metrics if metric.hostname in host_filter]
