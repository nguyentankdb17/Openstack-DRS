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
