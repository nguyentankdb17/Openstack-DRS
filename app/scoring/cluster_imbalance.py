from __future__ import annotations

import pandas as pd

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC


def _weighted_cv(series: pd.Series) -> float:
	mean_val = float(series.mean())
	if mean_val <= 0:
		return 0.0
	std_val = float(series.std(ddof=0))
	return std_val / mean_val


def compute_cluster_imbalance(metrics_df: pd.DataFrame) -> float:
	if metrics_df.empty:
		return 0.0

	cpu_cv = _weighted_cv(metrics_df[CPU_METRIC])
	ram_cv = _weighted_cv(metrics_df[RAM_METRIC])
	swap_cv = _weighted_cv(metrics_df[SWAP_METRIC])

	return (
		config.CPU_WEIGHT * cpu_cv
		+ config.RAM_WEIGHT * ram_cv
		+ config.SWAP_WEIGHT * swap_cv
	)
