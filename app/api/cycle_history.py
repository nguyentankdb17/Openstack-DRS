from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import CycleHistoryRecord, LatestPredictionHistoryResponse
from app.domain.cycle_history_service import get_latest_prediction_history, list_cycle_history


router = APIRouter(tags=["cycle-history"])


@router.get("/cycles/history", response_model=list[CycleHistoryRecord])
def get_cycle_history(limit: int = Query(default=50, ge=1, le=500)) -> list[CycleHistoryRecord]:
	return list_cycle_history(limit=limit)


@router.get("/cycles/history/latest-predict", response_model=LatestPredictionHistoryResponse)
def get_latest_predict_history() -> LatestPredictionHistoryResponse:
	return get_latest_prediction_history()
