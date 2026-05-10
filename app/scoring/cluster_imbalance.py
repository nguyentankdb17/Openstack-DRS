from __future__ import annotations

import numpy as np
import pandas as pd

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC

_MEAN_FLOOR = getattr(config, "IMBALANCE_MEAN_FLOOR", 5.0)  # %
_CV_CLAMP = getattr(config, "IMBALANCE_CV_CLAMP", 1.5)
_IDLE_CPU_THRESHOLD = getattr(config, "IMBALANCE_IDLE_CPU", 5.0)  # %
_IDLE_RAM_THRESHOLD = getattr(config, "IMBALANCE_IDLE_RAM", 10.0)  # %


def _extract_clean_array(series_like) -> np.ndarray:
	"""Convert a column (Series / None) to a clean float64 numpy array (NaN dropped)."""
	if series_like is None:
		return np.empty(0, dtype=np.float64)
	arr = pd.to_numeric(series_like, errors="coerce").to_numpy(dtype=np.float64)
	return arr[~np.isnan(arr)]


def _cv_from_array(arr: np.ndarray, mean_val: float, *, square: bool = False) -> float:
	"""
	Stabilized coefficient of variation given a pre-computed mean.

	Assumes `arr` is already clean (no NaN) and non-empty.
	Skips redundant mean computation when the caller already has it.
	"""
	std_val = float(np.std(arr))            # ddof=0, avoids pandas overhead
	denom = mean_val + _MEAN_FLOOR
	if denom <= 0:
		return 0.0
	cv = min(std_val / denom, _CV_CLAMP)
	return cv * cv if square else cv


def compute_cluster_imbalance(metrics_df: pd.DataFrame) -> float:
	if metrics_df is None or metrics_df.empty:
		return 0.0

	cpu_arr = _extract_clean_array(metrics_df.get(CPU_METRIC))
	ram_arr = _extract_clean_array(metrics_df.get(RAM_METRIC))

	if cpu_arr.size == 0 or ram_arr.size == 0:
		return 0.0

	# Compute means once – reused for both activity gating and CV calculation
	cpu_mean = float(cpu_arr.mean())
	ram_mean = float(ram_arr.mean())

	# ===== Activity gating (avoid noise when cluster idle) =====
	if cpu_mean < _IDLE_CPU_THRESHOLD and ram_mean < _IDLE_RAM_THRESHOLD:
		return 0.0

	# ===== Compute CVs =====
	cpu_cv = _cv_from_array(cpu_arr, cpu_mean)
	ram_cv = _cv_from_array(ram_arr, ram_mean)

	swap_arr = _extract_clean_array(metrics_df.get(SWAP_METRIC))
	swap_cv = 0.0
	if swap_arr.size > 0:
		swap_cv = _cv_from_array(swap_arr, float(swap_arr.mean()), square=True)

	# ===== Weighted sum =====
	return (
		config.CPU_WEIGHT * cpu_cv
		+ config.RAM_WEIGHT * ram_cv
		+ config.SWAP_WEIGHT * swap_cv
	)