from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, RUNNING_VM_METRIC, SWAP_METRIC
from app.models.schemas import VMMetricSnapshot
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
		metric_meta.get("hostname")
		or "unknown"
	)
	return host.split(":")[0]


def _normalize_vm(metric_meta: dict) -> str:
	vm_identity = (
		metric_meta.get("uuid")
		or metric_meta.get("domain_uuid")
		or metric_meta.get("domain")
		or metric_meta.get("name")
		or metric_meta.get("instance")
		or metric_meta.get("vm")
		or metric_meta.get("id")
		or "unknown"
	)
	return str(vm_identity)


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


def _query_instant(query: str, at_ts: float | None = None) -> list[dict]:
	params: dict[str, str] = {"query": query}
	if at_ts is not None:
		params["time"] = f"{at_ts:.3f}"

	response = requests.get(
		f"{config.PROMETHEUS_BASE_URL}/api/v1/query",
		params=params,
		auth=_prometheus_auth(),
		timeout=config.PROMETHEUS_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	payload = response.json()
	if payload.get("status") != "success":
		raise RuntimeError(f"Prometheus query failed: {payload}")
	return payload.get("data", {}).get("result", [])


def _render_query_template(template: str, window_text: str) -> str:
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


def _vm_metric_map(series: list[dict]) -> dict[str, float]:
	values: dict[str, float] = {}
	for item in series:
		vm = _normalize_vm(item.get("metric", {}))
		value_raw = item.get("value", [])
		if len(value_raw) < 2:
			continue
		try:
			values[vm] = float(value_raw[1])
		except (TypeError, ValueError):
			continue
	return values


def _host_metric_map(series: list[dict]) -> dict[str, float]:
	values: dict[str, float] = {}
	for item in series:
		host = _normalize_host(item.get("metric", {}))
		value_raw = item.get("value", [])
		if len(value_raw) < 2:
			continue
		try:
			values[host] = float(value_raw[1])
		except (TypeError, ValueError):
			continue
	return values


def collect_host_total_allocations() -> pd.DataFrame:
	now_ts = datetime.now(timezone.utc).timestamp()
	cpu_series = _query_instant(config.HOST_TOTAL_CPU_QUERY, at_ts=now_ts)
	ram_series = _query_instant(config.HOST_TOTAL_MEM_QUERY, at_ts=now_ts)
	swap_series = _query_instant(config.HOST_TOTAL_SWAP_QUERY, at_ts=now_ts)

	cpu_by_host = _host_metric_map(cpu_series)
	ram_by_host = _host_metric_map(ram_series)
	swap_by_host = _host_metric_map(swap_series)
	hosts = sorted(set(cpu_by_host.keys()) | set(ram_by_host.keys()) | set(swap_by_host.keys()))
	if not hosts:
		return pd.DataFrame(columns=["host", "cpu_allocated", "ram_allocated", "swap_allocated"])

	return pd.DataFrame(
		[
			{
				"host": host,
				"cpu_allocated": float(cpu_by_host.get(host, 0.0)),
				"ram_allocated": float(ram_by_host.get(host, 0.0)),
				"swap_allocated": float(swap_by_host.get(host, 0.0)),
			}
			for host in hosts
		],
		columns=["host", "cpu_allocated", "ram_allocated", "swap_allocated"],
	)


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
	total_df = collect_host_total_allocations()

	if history_df.empty:
		logger.warning("No data from Prometheus in last %s minutes", window_minutes)
		if total_df.empty:
			return pd.DataFrame(columns=["host", CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC, "cpu_allocated", "ram_allocated", "swap_allocated"])
		for column_name in [CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC]:
			total_df[column_name] = 0.0
		return total_df[["host", CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC, "cpu_allocated", "ram_allocated", "swap_allocated"]]

	grouped = (
		history_df.groupby("host", as_index=False)[[CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC]]
		.mean(numeric_only=True)
		.fillna(0.0)
	)
	if total_df.empty:
		grouped["cpu_allocated"] = 0.0
		grouped["ram_allocated"] = 0.0
		grouped["swap_allocated"] = 0.0
		return grouped

	grouped = grouped.merge(total_df, on="host", how="left")
	for column_name in ["cpu_allocated", "ram_allocated", "swap_allocated"]:
		grouped[column_name] = grouped[column_name].fillna(0.0)
	return grouped


def collect_vm_metric_averages(window_minutes: int, step_seconds: int) -> list[VMMetricSnapshot]:
	del step_seconds  # VM snapshot uses instant vector queries per metric.
	window_text = f"{window_minutes}m"
	now_ts = datetime.now(timezone.utc).timestamp()

	cpu_series = _query_instant(_render_query_template(config.VM_CPU_QUERY, window_text), at_ts=now_ts)
	ram_series = _query_instant(_render_query_template(config.VM_MEM_QUERY, window_text), at_ts=now_ts)

	cpu_by_vm = _vm_metric_map(cpu_series)
	ram_by_vm = _vm_metric_map(ram_series)
	vm_ids = sorted(set(cpu_by_vm.keys()) | set(ram_by_vm.keys()))
	if not vm_ids:
		logger.warning("No VM data from Prometheus in last %s minutes", window_minutes)
		return []
	
	logger.debug("VM metrics snaphot: %d VMs with CPU data, %d VMs with RAM data", len(cpu_by_vm), len(ram_by_vm))

	return [
		VMMetricSnapshot(
			uuid=vm_id,
			hostname="",
			cpu=float(cpu_by_vm.get(vm_id, 0.0)),
			ram=float(ram_by_vm.get(vm_id, 0.0)),
		)
		for vm_id in vm_ids
	]
