from __future__ import annotations

import numpy as np
import pandas as pd

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC
from app.predictor.feature_builder import build_chronos_history_df
from app.utils.logger import get_logger
from chronos import BaseChronosPipeline, Chronos2Pipeline


logger = get_logger(__name__)


class ChronosPredictor:
	def __init__(self) -> None:
		self.model_name = config.CHRONOS_MODEL_NAME
		self.device = config.CHRONOS_DEVICE
		self._pipeline = None
		self._load_attempted = False

	def _split_item_id(self, item_id: str) -> tuple[str | None, str]:
		if ":" in item_id:
			host, metric = item_id.split(":", 1)
			return host, metric
		return None, item_id

	def _try_load(self) -> None:
		if self._load_attempted:
			return
		self._load_attempted = True

		try:
			self._pipeline: Chronos2Pipeline = BaseChronosPipeline.from_pretrained(
				self.model_name,
				device_map=self.device,
			)
			logger.info("Chronos model loaded: %s", self.model_name)

		except Exception as e:
			logger.exception("Failed to load Chronos model: %s", e)
			self._pipeline = None

	def _naive_predict(self, history: pd.Series, steps: int) -> list[float]:
		if history.empty:
			return [0.0] * steps
		window = history.tail(min(5, len(history)))
		avg = float(window.mean())
		return [max(avg, 0.0)] * steps

	def _predict_metric_values(
		self,
		host_chronos_history: pd.DataFrame,
		metric: str,
		steps: int,
	) -> list[float]:
		return self._naive_predict(
			host_chronos_history.loc[host_chronos_history["item_id"] == metric, "target"],
			steps,
		)

	def predict(self, history_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
		if future_df.empty:
			return future_df

		self._try_load()
		output_rows: list[dict] = []

		if "item_id" in future_df.columns:
			future_work_df = future_df.copy()
			future_work_df[["host", "metric"]] = future_work_df["item_id"].apply(
				lambda item_id: pd.Series(self._split_item_id(str(item_id)))
			)
			if future_work_df["host"].isna().any():
				unique_hosts = history_df["host"].dropna().unique()
				if len(unique_hosts) == 1:
					future_work_df["host"] = future_work_df["host"].fillna(unique_hosts[0])
		else:
			future_work_df = future_df.copy()

		for host, host_future in future_work_df.groupby("host"):
			host_history = history_df[history_df["host"] == host].sort_values("timestamp")
			host_chronos_history = build_chronos_history_df(host_history)
			host_timestamps = (
				host_future.sort_values("timestamp")
				.drop_duplicates(subset=["timestamp"])
				[["timestamp", "running_vm"]]
			)
			steps = len(host_timestamps)
			if steps == 0:
				continue

			cpu_values = self._predict_metric_values(host_chronos_history, CPU_METRIC, steps)
			ram_values = self._predict_metric_values(host_chronos_history, RAM_METRIC, steps)
			swap_values = self._predict_metric_values(host_chronos_history, SWAP_METRIC, steps)
			# Until Chronos runtime is guaranteed in all environments, keep fallback deterministic.
			if self._pipeline is not None:
				try:
					cpu_values = self._predict_metric_values(host_chronos_history, CPU_METRIC, steps)
					ram_values = self._predict_metric_values(host_chronos_history, RAM_METRIC, steps)
					swap_values = self._predict_metric_values(host_chronos_history, SWAP_METRIC, steps)
				except Exception as exc:  # pylint: disable=broad-except
					logger.warning("Chronos inference failed for host %s, using fallback: %s", host, exc)

			for idx, (_, row) in enumerate(host_timestamps.iterrows()):
				output_rows.append(
					{
						"timestamp": row["timestamp"],
						"host": host,
						CPU_METRIC: float(np.clip(cpu_values[idx], 0, 100)),
						RAM_METRIC: float(np.clip(ram_values[idx], 0, 100)),
						SWAP_METRIC: float(np.clip(swap_values[idx], 0, 100)),
						"running_vm": float(row["running_vm"]),
					}
				)

		return pd.DataFrame(output_rows)
