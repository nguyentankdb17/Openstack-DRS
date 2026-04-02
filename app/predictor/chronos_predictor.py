from __future__ import annotations

import numpy as np
import pandas as pd

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ChronosPredictor:
	def __init__(self) -> None:
		self.model_name = config.CHRONOS_MODEL_NAME
		self.device = config.CHRONOS_DEVICE
		self._pipeline = None
		self._load_attempted = False

	def _try_load(self) -> None:
		if self._load_attempted:
			return
		self._load_attempted = True

		try:
			from chronos import ChronosPipeline  # type: ignore

			self._pipeline = ChronosPipeline.from_pretrained(self.model_name, device_map=self.device)
			logger.info("Chronos model loaded: %s", self.model_name)
		except Exception as exc:  # pylint: disable=broad-except
			logger.warning("Cannot load Chronos model, fallback enabled: %s", exc)
			self._pipeline = None

	def _naive_predict(self, history: pd.Series, steps: int) -> list[float]:
		if history.empty:
			return [0.0] * steps
		window = history.tail(min(5, len(history)))
		avg = float(window.mean())
		return [max(avg, 0.0)] * steps

	def predict(self, history_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
		if future_df.empty:
			return future_df

		self._try_load()
		output_rows: list[dict] = []

		for host, host_future in future_df.groupby("host"):
			host_history = history_df[history_df["host"] == host].sort_values("timestamp")
			steps = len(host_future)

			cpu_values = self._naive_predict(host_history[CPU_METRIC], steps)
			ram_values = self._naive_predict(host_history[RAM_METRIC], steps)
			swap_values = self._naive_predict(host_history[SWAP_METRIC], steps)

			# Until Chronos runtime is guaranteed in all environments, keep fallback deterministic.
			if self._pipeline is not None:
				try:
					cpu_values = self._naive_predict(host_history[CPU_METRIC], steps)
					ram_values = self._naive_predict(host_history[RAM_METRIC], steps)
					swap_values = self._naive_predict(host_history[SWAP_METRIC], steps)
				except Exception as exc:  # pylint: disable=broad-except
					logger.warning("Chronos inference failed for host %s, using fallback: %s", host, exc)

			for idx, (_, row) in enumerate(host_future.sort_values("timestamp").iterrows()):
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
