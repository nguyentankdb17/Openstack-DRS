from __future__ import annotations

import numpy as np
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


def find_unbalanced_hosts(metrics_df: pd.DataFrame, top_k: int | None = None) -> list[dict]:
	if metrics_df.empty:
		return []

	top = top_k or config.UNBALANCED_TOP_K
	means = metrics_df[[CPU_METRIC, RAM_METRIC, SWAP_METRIC]].mean()
	stds = metrics_df[[CPU_METRIC, RAM_METRIC, SWAP_METRIC]].std(ddof=0).replace(0, np.nan)
	z_scores = ((metrics_df[[CPU_METRIC, RAM_METRIC, SWAP_METRIC]] - means) / stds).abs().fillna(0.0)

	weighted_score = (
		config.CPU_WEIGHT * z_scores[CPU_METRIC]
		+ config.RAM_WEIGHT * z_scores[RAM_METRIC]
		+ config.SWAP_WEIGHT * z_scores[SWAP_METRIC]
	)

	ranked = metrics_df[["host"]].copy()
	ranked["score"] = weighted_score
	ranked = ranked.sort_values("score", ascending=False).head(top)
	return ranked.to_dict(orient="records")
