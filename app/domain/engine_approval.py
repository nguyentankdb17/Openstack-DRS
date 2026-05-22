from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from app import config
from app.domain.decision_service import (
	build_migration_execution_decision,
	build_migration_rejected_decision,
	get_latest_decision,
)
from app.domain.engine_cycle import record_engine_cycle
from app.domain.pending_plan_store import clear_pending, get_pending
from app.executor.migration_executor import MigrationExecutor
from app.utils.logger import get_logger


logger = get_logger(__name__)


class PendingPlanNotFoundError(RuntimeError):
	"""Raised when an RPC needs a pending plan but none exists."""


class NoMatchingCandidateError(RuntimeError):
	"""Raised when approved candidate ids do not match the pending plan."""


def latest_decision_json() -> str:
	return get_latest_decision().model_dump_json()


def pending_plan_json() -> tuple[bool, str]:
	pending = get_pending()
	if pending is None:
		return False, ""
	return True, pending.model_dump_json()


def reject_pending_plan() -> tuple[bool, str, str]:
	pending = get_pending()
	if pending is None:
		raise PendingPlanNotFoundError("No pending migration plan")

	decision = build_migration_rejected_decision(
		candidates=pending.candidates,
		current_score=pending.current_cluster_imbalance,
		predicted_score=pending.predicted_cluster_imbalance,
		details=f"Pending migration plan rejected by operator (plan_id={pending.plan_id})",
	)
	record_engine_cycle(
		cycle_started_at=pending.cycle_started_at or datetime.now(timezone.utc),
		trigger_source=f"manual_reject:{pending.trigger_source}",
		decision=decision,
		planned=pending.candidates,
		executed=[],
	)
	clear_pending()
	logger.info("[engine] Pending plan rejected via RPC (plan_id=%s)", pending.plan_id)
	return True, pending.plan_id, decision.status


async def execute_migration(migration_id: str) -> str:
	pending = get_pending()
	if pending is None:
		raise PendingPlanNotFoundError("No pending migration plan")

	candidate = next((c for c in pending.candidates if c.vm_id == migration_id), None)
	if candidate is None:
		candidate = pending.candidates[0] if pending.candidates else None
	if candidate is None:
		return "no_candidate"

	executor = MigrationExecutor()
	result = await asyncio.to_thread(executor.execute, candidate)
	logger.info("[engine] ExecuteMigration vm_id=%s: success=%s", migration_id, result.success)
	return "executed" if result.success else "failed"


async def approve_pending_plan(candidate_ids: list[str]) -> dict:
	pending = get_pending()
	if pending is None:
		raise PendingPlanNotFoundError("No pending migration plan")

	candidate_id_set = set(candidate_ids)
	candidates_to_run = (
		[candidate for candidate in pending.candidates if candidate.vm_id in candidate_id_set]
		if candidate_id_set
		else pending.candidates
	)
	if not candidates_to_run:
		raise NoMatchingCandidateError("No matching candidates found in the pending plan")

	max_migrations = max(1, int(config.MAX_MIGRATIONS_PER_CYCLE))
	selected = candidates_to_run[:max_migrations]
	cycle_started_at = pending.cycle_started_at or datetime.now(timezone.utc)
	executor = MigrationExecutor()
	results = []
	execution_decision = None

	for index, candidate in enumerate(selected, start=1):
		result = await asyncio.to_thread(executor.execute, candidate)
		execution_decision = build_migration_execution_decision(
			candidate,
			result,
			current_score=pending.current_cluster_imbalance,
			predicted_score=pending.predicted_cluster_imbalance,
		)
		results.append(execution_decision.model_dump(mode="json"))
		logger.info(
			"[engine] Manual approval executed candidate %d/%d vm_id=%s source=%s target=%s success=%s",
			index,
			len(selected),
			candidate.vm_id,
			candidate.source_host,
			candidate.target_host,
			result.success,
		)

	clear_pending()

	if execution_decision is not None:
		record_engine_cycle(
			cycle_started_at=cycle_started_at,
			trigger_source=f"manual_approve:{pending.trigger_source}",
			decision=execution_decision,
			planned=pending.candidates,
			executed=selected,
		)

	return {
		"approved": True,
		"plan_id": pending.plan_id,
		"executed": len(selected),
		"results_json": json.dumps(results),
		"status": "approved",
	}
