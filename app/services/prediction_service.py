import pandas as pd

from app import config
from app.predictor.chronos_predictor import ChronosPredictor
from app.predictor.feature_builder import build_chronos_history_df, build_future_df


_predictor = ChronosPredictor()


def build_predict_input(history_df: pd.DataFrame) -> pd.DataFrame:
	return build_future_df(
		history_df=history_df,
		horizon_minutes=config.PREDICTION_HORIZON_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)


def build_chronos_input(history_df: pd.DataFrame) -> pd.DataFrame:
	return build_chronos_history_df(history_df)


def predict_next_window(history_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
	return _predictor.predict(history_df=history_df, future_df=future_df)
