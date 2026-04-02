from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.core.constants import CPU_METRIC, RAM_METRIC, RUNNING_VM_METRIC, SWAP_METRIC


def build_chronos_history_df(history_df: pd.DataFrame) -> pd.DataFrame:
	"""Convert wide metrics into Chronos long format: item_id, target, timestamp."""
	if history_df.empty:
		return pd.DataFrame(columns=["item_id", "target", "timestamp"])

	metrics = [CPU_METRIC, RAM_METRIC, SWAP_METRIC]
	chronos_df = history_df[["timestamp", "host", *metrics]].melt(
		id_vars=["timestamp", "host"],
		value_vars=metrics,
		var_name="metric",
		value_name="target",
	)

	if chronos_df["host"].nunique(dropna=True) <= 1:
		chronos_df["item_id"] = chronos_df["metric"]
	else:
		# Keep each time series unique when multiple hosts are present.
		chronos_df["item_id"] = chronos_df["host"].astype(str) + ":" + chronos_df["metric"].astype(str)

	return chronos_df[["timestamp", "item_id", "target"]]


def build_future_df(
	history_df: pd.DataFrame,
	horizon_minutes: int,
	step_seconds: int,
) -> pd.DataFrame:
	if history_df.empty:
		return pd.DataFrame(columns=["timestamp", "host", CPU_METRIC, RAM_METRIC, SWAP_METRIC, RUNNING_VM_METRIC])

	future_rows: list[dict] = []
	step_count = max(1, int((horizon_minutes * 60) / step_seconds))

	for host, host_df in history_df.groupby("host"):
		host_df = host_df.sort_values("timestamp")
		last_time = host_df["timestamp"].iloc[-1]
		last_vm = float(host_df[RUNNING_VM_METRIC].iloc[-1])

		for idx in range(step_count):
			ts = last_time + timedelta(seconds=step_seconds * (idx + 1))
			future_rows.append(
				{
					"timestamp": ts,
					"host": host,
					RUNNING_VM_METRIC: last_vm,
					CPU_METRIC: None,
					RAM_METRIC: None,
					SWAP_METRIC: None,
				}
			)

	return pd.DataFrame(future_rows)
