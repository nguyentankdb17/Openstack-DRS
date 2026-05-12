"""API endpoints for manual approval of pending migration plans."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app import config
from app.executor.migration_executor import MigrationExecutor
from app.models.schemas import ApproveRequest, MigrationCandidate
from app.services.pending_plan_store import clear_pending, get_pending
from app.services.cycle_history_service import record_cycle_history
from app.services.decision_service import build_migration_execution_decision
from app.utils.logger import get_logger

router = APIRouter(tags=["plan"])
logger = get_logger(__name__)
_executor = MigrationExecutor()


@router.get("/plan/pending")
def get_pending_plan() -> dict[str, Any]:
    """Return the current pending migration plan (if any)."""
    pending = get_pending()
    if pending is None:
        return {"pending": False, "plan": None}
    return {"pending": True, "plan": pending.model_dump()}


@router.delete("/plan/pending", status_code=status.HTTP_200_OK)
def reject_pending_plan() -> dict[str, Any]:
    """Discard the current pending plan without executing it."""
    pending = get_pending()
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending plan")
    clear_pending()
    logger.info("Pending plan rejected by operator (plan_id=%s)", pending.plan_id)
    return {"rejected": True, "plan_id": pending.plan_id}


@router.post("/plan/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_pending_plan(body: ApproveRequest) -> dict[str, Any]:
    """
    Approve and execute the current pending plan.

    - Leave `candidate_ids` empty to execute **all** candidates.
    - Pass specific VM IDs to execute only a subset.
    """
    pending = get_pending()
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending plan")

    candidates_to_run: list[MigrationCandidate] = (
        [c for c in pending.candidates if c.vm_id in body.candidate_ids]
        if body.candidate_ids
        else pending.candidates
    )

    if not candidates_to_run:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No matching candidates found in the pending plan",
        )

    max_migrations = max(1, int(config.MAX_MIGRATIONS_PER_CYCLE))
    selected = candidates_to_run[:max_migrations]
    cycle_started_at = datetime.now(timezone.utc)
    results = []

    for idx, candidate in enumerate(selected, start=1):
        result = _executor.execute(candidate)
        execution_decision = build_migration_execution_decision(
            candidate,
            result,
            current_score=pending.current_cluster_imbalance,
        )
        results.append(execution_decision.model_dump())
        logger.info(
            "Manual approval — executed candidate %d/%d vm_id=%s source=%s target=%s success=%s",
            idx,
            len(selected),
            candidate.vm_id,
            candidate.source_host,
            candidate.target_host,
            result.success,
        )

    clear_pending()

    try:
        record_cycle_history(
            cycle_started_at=cycle_started_at,
            cycle_finished_at=datetime.now(timezone.utc),
            trigger_source=f"manual_approve:{pending.trigger_source}",
            decision=execution_decision,
            planned_candidates=pending.candidates,
            executed_candidates=selected,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to record cycle history after manual approval: %s", exc)

    return {
        "approved": True,
        "plan_id": pending.plan_id,
        "executed": len(selected),
        "results": results,
    }
