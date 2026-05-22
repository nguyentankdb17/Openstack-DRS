from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app import config
from app.core import constants
from app.models.schemas import ClusterDecision, MigrationCandidate, MigrationExecutionResult, MigrationPlan
from app.scoring.cluster_imbalance import compute_cluster_imbalance


_latest_decision: ClusterDecision | None = None


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
		return set_latest_decision(
			ClusterDecision(
				status=constants.STATUS_CURRENT_IMBALANCED,
				timestamp=datetime.now(timezone.utc),
				current_cluster_imbalance=score,
				threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
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
		pred_df.groupby("host", as_index=False)[["cpu", "ram", "swap"]].mean(numeric_only=True)
	)

	if pred_score > config.CLUSTER_IMBALANCE_THRESHOLD:
		return set_latest_decision(
			ClusterDecision(
				status=constants.STATUS_PREDICTED_IMBALANCED,
				timestamp=datetime.now(timezone.utc),
				current_cluster_imbalance=current_score,
				predicted_cluster_imbalance=pred_score,
				threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
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


def build_migration_plan_decision(plan: MigrationPlan) -> ClusterDecision:
	status = constants.STATUS_MIGRATION_PLANNED if plan.candidates else constants.STATUS_REEVALUATING
	return set_latest_decision(
		ClusterDecision(
			status=status,
			timestamp=datetime.now(timezone.utc),
			current_cluster_imbalance=plan.current_cluster_imbalance,
			predicted_cluster_imbalance=plan.predicted_cluster_imbalance,
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			planned_candidates=plan.candidates,
			details=plan.details,
		)
	)


def build_migration_rejected_decision(
	candidates: list[MigrationCandidate],
	current_score: float | None = None,
	predicted_score: float | None = None,
	details: str | None = None,
) -> ClusterDecision:
	return set_latest_decision(
		ClusterDecision(
			status=constants.STATUS_MIGRATION_REJECTED,
			timestamp=datetime.now(timezone.utc),
			current_cluster_imbalance=current_score,
			predicted_cluster_imbalance=predicted_score,
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			planned_candidates=candidates,
			details=details or "Migration plan rejected by operator",
		)
	)


def build_migration_execution_decision(
	candidate: MigrationCandidate,
	result: MigrationExecutionResult,
	current_score: float | None = None,
	predicted_score: float | None = None,
) -> ClusterDecision:
	status = constants.STATUS_MIGRATION_EXECUTED if result.success else constants.STATUS_MIGRATION_FAILED
	return set_latest_decision(
		ClusterDecision(
			status=status,
			timestamp=datetime.now(timezone.utc),
			current_cluster_imbalance=current_score,
			predicted_cluster_imbalance=predicted_score,
			threshold=config.CLUSTER_IMBALANCE_THRESHOLD,
			selected_candidate=candidate,
			execution_result=result,
			details=result.message,
		)
	)
