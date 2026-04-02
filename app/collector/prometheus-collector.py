from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, RUNNING_VM_METRIC, SWAP_METRIC
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _prometheus_auth() -> tuple[str, str] | None:
	username = (config.PROMETHEUS_USERNAME or "").strip()
	password = config.PROMETHEUS_PASSWORD or ""
	if not username and not password:
		return None
	return username, password


def _normalize_host(metric_meta: dict) -> str:
	host = (
		metric_meta.get("instance")
		or metric_meta.get("nodename")
		or metric_meta.get("host")
		or "unknown"
	)
	return host.split(":")[0]


def _query_range(query: str, start_ts: float, end_ts: float, step_seconds: int) -> list[dict]:
	response = requests.get(
		f"{config.PROMETHEUS_BASE_URL}/api/v1/query_range",
		params={
			"query": query,
			"start": f"{start_ts:.3f}",
			"end": f"{end_ts:.3f}",
			"step": str(step_seconds),
		},
		auth=_prometheus_auth(),
		timeout=config.PROMETHEUS_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	payload = response.json()
	if payload.get("status") != "success":
		raise RuntimeError(f"Prometheus query failed: {payload}")
	return payload.get("data", {}).get("result", [])


def _render_query_template(template: str, window_text: str) -> str:
	# Avoid str.format() because PromQL labels also use braces (e.g. {job="..."}).
	return template.replace("{window}", window_text)


def _metric_df(series: list[dict], metric_name: str) -> pd.DataFrame:
	rows: list[dict] = []
	for item in series:
		host = _normalize_host(item.get("metric", {}))
		for ts_raw, value_raw in item.get("values", []):
			rows.append(
				{
					"timestamp": datetime.fromtimestamp(float(ts_raw), tz=timezone.utc),
					"host": host,
					metric_name: float(value_raw),
				}
			)

	if not rows:
		return pd.DataFrame(columns=["timestamp", "host", metric_name])

	return pd.DataFrame(rows)


def _build_window(window_minutes: int, end_time: datetime | None = None) -> tuple[float, float]:
	end = end_time.astimezone(timezone.utc) if end_time else datetime.now(timezone.utc)
	start = end - timedelta(minutes=window_minutes)
	return start.timestamp(), end.timestamp()


def collect_host_metric_history(window_minutes: int, step_seconds: int) -> pd.DataFrame:
	start_ts, end_ts = _build_window(window_minutes)
	window_text = f"{window_minutes}m"

	cpu_series = _query_range(_render_query_template(config.HOST_CPU_QUERY, window_text), start_ts, end_ts, step_seconds)
	ram_series = _query_range(_render_query_template(config.HOST_MEM_QUERY, window_text), start_ts, end_ts, step_seconds)
	swap_series = _query_range(_render_query_template(config.HOST_SWAP_QUERY, window_text), start_ts, end_ts, step_seconds)
	vm_series = _query_range(_render_query_template(config.HOST_RUNNING_VM_QUERY, window_text), start_ts, end_ts, step_seconds)

	cpu_df = _metric_df(cpu_series, CPU_METRIC)
	ram_df = _metric_df(ram_series, RAM_METRIC)
	swap_df = _metric_df(swap_series, SWAP_METRIC)
	vm_df = _metric_df(vm_series, RUNNING_VM_METRIC)

	merged = cpu_df.merge(ram_df, on=["timestamp", "host"], how="outer")
	merged = merged.merge(swap_df, on=["timestamp", "host"], how="outer")
	merged = merged.merge(vm_df, on=["timestamp", "host"], how="outer")

	if merged.empty:
		return merged

	merged = merged.sort_values(["host", "timestamp"]).ffill().bfill()
	return merged


def collect_host_metric_averages(window_minutes: int, step_seconds: int) -> pd.DataFrame:
	history_df = collect_host_metric_history(window_minutes=window_minutes, step_seconds=step_seconds)
	if history_df.empty:
		logger.warning("No data from Prometheus in last %s minutes", window_minutes)
		return pd.DataFrame(columns=["host", CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC])

	grouped = (
		history_df.groupby("host", as_index=False)[[CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC]]
		.mean(numeric_only=True)
		.fillna(0.0)
	)
	return grouped
