from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import CycleHistoryRecord
from app.services.cycle_history_service import list_cycle_history


router = APIRouter(tags=["cycle-history"])


@router.get("/cycles/history", response_model=list[CycleHistoryRecord])
def get_cycle_history(limit: int = Query(default=50, ge=1, le=500)) -> list[CycleHistoryRecord]:
	return list_cycle_history(limit=limit)
