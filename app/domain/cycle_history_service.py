from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg2.extras import Json

from app.db.postgres import get_connection
from app.models.schemas import ClusterDecision, CycleHistoryRecord, LatestPredictionHistoryResponse, MigrationCandidate


def _candidate_list_to_payload(candidates: list[MigrationCandidate]) -> list[dict[str, Any]]:
	return [candidate.model_dump(mode="json") for candidate in candidates]


def record_cycle_history(
	*,
	cycle_started_at: datetime,
	cycle_finished_at: datetime,
	trigger_source: str,
	decision: ClusterDecision,
	planned_candidates: list[MigrationCandidate],
	executed_candidates: list[MigrationCandidate],
	prediction_results: dict[str, Any] | None = None,
	error_message: str | None = None,
) -> int:
	payload: dict[str, Any] = decision.model_dump(mode="json")
	planned_candidates_payload = _candidate_list_to_payload(planned_candidates)
	executed_candidates_payload = _candidate_list_to_payload(executed_candidates)
	prediction_results_update = Json(prediction_results) if prediction_results is not None else None
	prediction_results_insert = Json(prediction_results or {})
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				UPDATE drs_cycle_history
				SET
					cycle_finished_at = %s,
					trigger_source = %s,
					status = %s,
					current_cluster_imbalance = %s,
					predicted_cluster_imbalance = %s,
					threshold = %s,
					planned_candidates = %s::jsonb,
					executed_candidates = %s::jsonb,
					prediction_results = COALESCE(%s::jsonb, prediction_results),
					details = %s,
					decision_payload = %s::jsonb,
					error_message = %s
				WHERE id = (
					SELECT id
					FROM drs_cycle_history
					WHERE cycle_started_at = %s
					ORDER BY id DESC
					LIMIT 1
				)
				RETURNING id
				""",
				(
					cycle_finished_at,
					trigger_source,
					decision.status,
					decision.current_cluster_imbalance,
					decision.predicted_cluster_imbalance,
					decision.threshold,
					Json(planned_candidates_payload),
					Json(executed_candidates_payload),
					prediction_results_update,
					decision.details,
					Json(payload),
					error_message,
					cycle_started_at,
				),
			)
			row = cursor.fetchone()
			if row:
				connection.commit()
				return int(row[0])

			cursor.execute(
				"""
				INSERT INTO drs_cycle_history (
					cycle_started_at,
					cycle_finished_at,
					trigger_source,
					status,
					current_cluster_imbalance,
					predicted_cluster_imbalance,
					threshold,
					planned_candidates,
					executed_candidates,
					prediction_results,
					details,
					decision_payload,
					error_message
				)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s)
				RETURNING id
				""",
				(
					cycle_started_at,
					cycle_finished_at,
					trigger_source,
					decision.status,
					decision.current_cluster_imbalance,
					decision.predicted_cluster_imbalance,
					decision.threshold,
					Json(planned_candidates_payload),
					Json(executed_candidates_payload),
					prediction_results_insert,
					decision.details,
					Json(payload),
					error_message,
				),
			)
			row = cursor.fetchone()
		connection.commit()

	return int(row[0])


def list_cycle_history(limit: int = 50) -> list[CycleHistoryRecord]:
	query_limit = max(1, min(int(limit), 500))
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT
					id,
					cycle_started_at,
					cycle_finished_at,
					trigger_source,
					status,
					current_cluster_imbalance,
					predicted_cluster_imbalance,
					threshold,
					planned_candidates,
					executed_candidates,
					prediction_results,
					details,
					decision_payload,
					error_message,
					created_at
				FROM drs_cycle_history
				ORDER BY cycle_started_at DESC
				LIMIT %s
				""",
				(query_limit,),
			)
			rows = cursor.fetchall()

	results: list[CycleHistoryRecord] = []
	for row in rows:
		results.append(
			CycleHistoryRecord(
				id=int(row[0]),
				cycle_started_at=row[1],
				cycle_finished_at=row[2],
				trigger_source=str(row[3]),
				status=str(row[4]),
				current_cluster_imbalance=float(row[5]) if row[5] is not None else None,
				predicted_cluster_imbalance=float(row[6]) if row[6] is not None else None,
				threshold=float(row[7]) if row[7] is not None else None,
				planned_candidates=[MigrationCandidate.model_validate(item) for item in (row[8] or [])],
				executed_candidates=[MigrationCandidate.model_validate(item) for item in (row[9] or [])],
				prediction_results=dict(row[10] or {}),
				details=str(row[11]) if row[11] is not None else None,
				decision_payload=dict(row[12] or {}),
				error_message=str(row[13]) if row[13] is not None else None,
				created_at=row[14],
			)
		)

	return results


def get_recent_migration_vm_ids(cycle_limit: int) -> set[str]:
	"""Return VM IDs that were planned or executed in recent engine cycles."""
	query_limit = max(0, int(cycle_limit))
	if query_limit <= 0:
		return set()

	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT planned_candidates, executed_candidates
				FROM drs_cycle_history
				ORDER BY cycle_started_at DESC
				LIMIT %s
				""",
				(query_limit,),
			)
			rows = cursor.fetchall()

	vm_ids: set[str] = set()
	for planned_candidates, executed_candidates in rows:
		for candidate in list(planned_candidates or []) + list(executed_candidates or []):
			if not isinstance(candidate, dict):
				continue
			vm_id = str(candidate.get("vm_id") or "").strip()
			if vm_id:
				vm_ids.add(vm_id)

	return vm_ids


def get_latest_prediction_history() -> LatestPredictionHistoryResponse:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT id, cycle_started_at, prediction_results
				FROM drs_cycle_history
				WHERE prediction_results IS NOT NULL
					AND prediction_results <> '{}'::jsonb
				ORDER BY cycle_started_at DESC
				LIMIT 1
				"""
			)
			row = cursor.fetchone()

	if not row:
		return LatestPredictionHistoryResponse()

	return LatestPredictionHistoryResponse(
		cycle_id=int(row[0]),
		cycle_started_at=row[1],
		prediction_results=dict(row[2] or {}),
	)
