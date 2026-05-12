from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg2.extras import Json

from app.db.postgres import get_connection
from app.models.schemas import ClusterDecision, CycleHistoryRecord, MigrationCandidate


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
	error_message: str | None = None,
) -> int:
	payload: dict[str, Any] = decision.model_dump(mode="json")
	planned_candidates_payload = _candidate_list_to_payload(planned_candidates)
	executed_candidates_payload = _candidate_list_to_payload(executed_candidates)
	with get_connection() as connection:
		with connection.cursor() as cursor:
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
					details,
					decision_payload,
					error_message
				)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s)
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
				details=str(row[10]) if row[10] is not None else None,
				decision_payload=dict(row[11] or {}),
				error_message=str(row[12]) if row[12] is not None else None,
				created_at=row[13],
			)
		)

	return results
