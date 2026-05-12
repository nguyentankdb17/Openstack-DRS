"""Thread-safe in-memory store for the pending migration plan.

Only one plan can be pending at a time. A new plan from the scheduler
will silently replace the previous one if it has not yet been approved.
"""
from __future__ import annotations

import uuid
from threading import Lock

from app.models.schemas import MigrationPlan, PendingPlan

_lock = Lock()
_pending: PendingPlan | None = None


def set_pending(plan: MigrationPlan, trigger_source: str) -> PendingPlan:
    """Store a new pending plan, replacing any existing one."""
    global _pending
    pending = PendingPlan(
        plan_id=str(uuid.uuid4()),
        trigger_source=trigger_source,
        candidates=plan.candidates,
        current_cluster_imbalance=plan.current_cluster_imbalance,
        details=plan.details,
    )
    with _lock:
        _pending = pending
    return pending


def get_pending() -> PendingPlan | None:
    """Return the current pending plan, or None if there is none."""
    with _lock:
        return _pending


def clear_pending() -> None:
    """Remove the pending plan (called after approval or rejection)."""
    global _pending
    with _lock:
        _pending = None
