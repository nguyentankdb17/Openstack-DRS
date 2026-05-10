from __future__ import annotations

import numpy as np
import pandas as pd

from app import config
from app.core.constants import CPU_METRIC, RAM_METRIC, SWAP_METRIC
from app.predictor.feature_builder import build_chronos_history_df
from app.utils.logger import get_logger
from autogluon.timeseries import TimeSeriesDataFrame
from autogluon.timeseries import TimeSeriesPredictor as AGPredictor

logger = get_logger(__name__)


class ChronosPredictor:
    def __init__(self) -> None:
        self.model_path = config.CHRONOS_FINETUNED_MODEL_PATH
        self._pipeline: AGPredictor | None = None

    # ------------------------------------------------------------------ #
    #  Model loading                                                       #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        """Load the fine-tuned AutoGluon/Chronos model once."""
        if self._pipeline is not None:
            return
        logger.info("Loading fine-tuned Chronos model from: %s", self.model_path)
        self._pipeline = AGPredictor.load(self.model_path)
        logger.info("Model loaded successfully.")

    # ------------------------------------------------------------------ #
    #  Core prediction                                                     #
    # ------------------------------------------------------------------ #

    def _forecast_one_host(self, host_chronos_history: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
        """
        Run AutoGluon prediction for a single host.

        Parameters
        ----------
        host_chronos_history : long-format DataFrame with columns
            [item_id, timestamp, target] — one row per (metric, time-step).

        Returns
        -------
        Nested dict {timestamp -> {metric -> predicted_value}}
        """
        # Ensure timezone-naive timestamps (AutoGluon requirement)
        ts_input = host_chronos_history.copy()
        if ts_input["timestamp"].dtype != "datetime64[ns]":
            ts_input["timestamp"] = pd.to_datetime(ts_input["timestamp"]).dt.tz_localize(None)

        # Wrap in AutoGluon's TimeSeriesDataFrame
        ts_df = TimeSeriesDataFrame.from_data_frame(
            ts_input,
            id_column="item_id",
            timestamp_column="timestamp",
        )

        # Predict → reset index so item_id / timestamp become plain columns
        forecast_df = self._pipeline.predict(ts_df).reset_index()

        # Normalise the prediction column name to "predictions"
        pred_cols = [c for c in forecast_df.columns if c not in ("item_id", "timestamp")]
        rename_col = "mean" if "mean" in pred_cols else pred_cols[0]
        forecast_df = forecast_df.rename(columns={rename_col: "predictions"})[
            ["item_id", "timestamp", "predictions"]
        ]

        # Derive metric name from item_id ('host:metric' → 'metric')
        forecast_df["metric"] = forecast_df["item_id"].apply(
            lambda x: x.split(":", 1)[1] if ":" in x else x
        )

        # Build {timestamp -> {metric -> value}} for O(1) look-up
        result: dict[pd.Timestamp, dict[str, float]] = {}
        for row in forecast_df.itertuples(index=False):
            result.setdefault(row.timestamp, {})[row.metric] = row.predictions

        return result

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def predict(self, history_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate resource-usage forecasts for every host in history_df.

        Parameters
        ----------
        history_df : raw historical observations with columns
            [host, timestamp, <metric columns>, ...]

        Returns
        -------
        DataFrame with columns:
            [timestamp, host, CPU_METRIC, RAM_METRIC, SWAP_METRIC]
        """
        self._load()

        output_rows: list[dict] = []

        for host, host_history in history_df.groupby("host"):
            # Build the Chronos-style long-format history for this host
            host_chronos_history = build_chronos_history_df(
                host_history.sort_values("timestamp")
            )

            # Run model forecast
            forecast = self._forecast_one_host(host_chronos_history)

            # Flatten forecast dict into output rows
            for timestamp, metrics in forecast.items():
                output_rows.append({
                    "timestamp": timestamp,
                    "host":      host,
                    CPU_METRIC:  float(np.clip(metrics.get(CPU_METRIC,  0.0), 0, 100)),
                    RAM_METRIC:  float(np.clip(metrics.get(RAM_METRIC,  0.0), 0, 100)),
                    SWAP_METRIC: float(np.clip(metrics.get(SWAP_METRIC, 0.0), 0, 100)),
                })

        return pd.DataFrame(output_rows)