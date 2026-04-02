from fastapi import APIRouter

from app.models.schemas import MonitorResponse
from app.services.decision_service import get_latest_decision


router = APIRouter(tags=["monitor"])


@router.get("/monitor/latest", response_model=MonitorResponse)
def latest_monitor_decision() -> MonitorResponse:
    return MonitorResponse(data=get_latest_decision())
