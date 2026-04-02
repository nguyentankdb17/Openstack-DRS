from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app import config
from app.core import constants
from app.models.schemas import ClusterDecision, HostDeviation
from app.scoring.cluster_imbalance import compute_cluster_imbalance, find_unbalanced_hosts


_latest_decision: ClusterDecision | None = None


def _to_host_deviations(items: list[dict]) -> list[HostDeviation]:
	return [HostDeviation(host=item["host"], score=float(item["score"])) for item in items]


def set_latest_decision(decision: ClusterDecision) -> ClusterDecision:
	global _latest_decision
	_latest_decision = decision
	return decision


def get_latest_decision() -> ClusterDecision:
	if _latest_decision is None:
		return ClusterDecision(
			status=constants.STATUS_CURRENT_BALANCED,
			timestamp=datetime.now(timezone.utc),
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			details="Monitor has not run yet",
		)
	return _latest_decision


def build_event_skip_decision(events: list[str]) -> ClusterDecision:
	return set_latest_decision(
		ClusterDecision(
			status=constants.STATUS_SKIPPED_BY_EVENT,
			timestamp=datetime.now(timezone.utc),
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			recent_events=events,
			details="Recent VM events detected, skip rebalance cycle",
		)
	)


def evaluate_current(metrics_df: pd.DataFrame) -> ClusterDecision:
	score = compute_cluster_imbalance(metrics_df)
	if score > config.CLUSTER_IMBALANCE_THRESHOLD:
		offenders = find_unbalanced_hosts(metrics_df)
		return set_latest_decision(
			ClusterDecision(
				status=constants.STATUS_CURRENT_IMBALANCED,
				timestamp=datetime.now(timezone.utc),
				current_cluster_imbalance=score,
				threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
				unbalanced_hosts=_to_host_deviations(offenders),
				details="Current 5-minute window is imbalanced",
			)
		)

	return set_latest_decision(
		ClusterDecision(
			status=constants.STATUS_CURRENT_BALANCED,
			timestamp=datetime.now(timezone.utc),
			current_cluster_imbalance=score,
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			details="Current 5-minute window is balanced",
		)
	)


def evaluate_predicted(pred_df: pd.DataFrame, current_score: float) -> ClusterDecision:
	pred_score = compute_cluster_imbalance(
		pred_df.groupby("host", as_index=False)[["cpu", "ram", "swap", "running_vm"]].mean(numeric_only=True)
	)

	if pred_score > config.CLUSTER_IMBALANCE_THRESHOLD:
		offenders = find_unbalanced_hosts(
			pred_df.groupby("host", as_index=False)[["cpu", "ram", "swap", "running_vm"]].mean(numeric_only=True)
		)
		return set_latest_decision(
			ClusterDecision(
				status=constants.STATUS_PREDICTED_IMBALANCED,
				timestamp=datetime.now(timezone.utc),
				current_cluster_imbalance=current_score,
				predicted_cluster_imbalance=pred_score,
				threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
				unbalanced_hosts=_to_host_deviations(offenders),
				details="Predicted next 5-minute window is imbalanced",
			)
		)

	return set_latest_decision(
		ClusterDecision(
			status=constants.STATUS_PREDICTED_BALANCED,
			timestamp=datetime.now(timezone.utc),
			current_cluster_imbalance=current_score,
			predicted_cluster_imbalance=pred_score,
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			details="Predicted next 5-minute window is balanced",
		)
	)


def build_error_decision(message: str) -> ClusterDecision:
	return set_latest_decision(
		ClusterDecision(
			status=constants.STATUS_ERROR,
			timestamp=datetime.now(timezone.utc),
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			details=message,
		)
	)
