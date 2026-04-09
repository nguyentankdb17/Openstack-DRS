from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC


def build_chronos_history_df(history_df: pd.DataFrame) -> pd.DataFrame:
	"""Convert wide metrics into Chronos long format: item_id, target, timestamp."""
	if history_df.empty:
		return pd.DataFrame(columns=["item_id", "target", "timestamp", "running_vm"])

	metrics = [CPU_METRIC, RAM_METRIC, SWAP_METRIC]
	chronos_df = history_df[["timestamp", "host", *metrics]].melt(
		id_vars=["timestamp", "host"],
		value_vars=metrics,
		var_name="metric",
		value_name="target",
	)
	running_vm_df = history_df[["timestamp", "host", RUNNING_VM_METRIC]].copy()

	if chronos_df["host"].nunique(dropna=True) <= 1:
		chronos_df["item_id"] = chronos_df["metric"]
	else:
		# Keep each time series unique when multiple hosts are present.
		chronos_df["item_id"] = chronos_df["host"].astype(str) + ":" + chronos_df["metric"].astype(str)

	chronos_df = chronos_df.merge(running_vm_df, on=["timestamp", "host"], how="left")

	return chronos_df[["timestamp", "item_id", "target", RUNNING_VM_METRIC]]


def build_future_df(
	history_df: pd.DataFrame,
	horizon_minutes: int,
	step_seconds: int,
) -> pd.DataFrame:
	if history_df.empty:
		return pd.DataFrame(columns=["timestamp", "item_id", RUNNING_VM_METRIC])

	future_rows: list[dict] = []
	step_count = max(1, int((horizon_minutes * 60) / step_seconds))
	has_multiple_hosts = history_df["host"].nunique(dropna=True) > 1

	for host, host_df in history_df.groupby("host"):
		host_df = host_df.sort_values("timestamp")
		last_time = host_df["timestamp"].iloc[-1]
		last_vm = float(host_df[RUNNING_VM_METRIC].iloc[-1])

		for idx in range(step_count):
			ts = last_time + timedelta(seconds=step_seconds * (idx + 1))
			for metric in (CPU_METRIC, RAM_METRIC, SWAP_METRIC):
				future_rows.append(
					{
						"timestamp": ts,
						"item_id": f"{host}:{metric}" if has_multiple_hosts else metric,
						RUNNING_VM_METRIC: last_vm,
					}
				)

	return pd.DataFrame(future_rows)
