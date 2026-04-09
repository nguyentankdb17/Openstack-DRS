from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
	RuntimeConfigResponse,
	RuntimeConfigUpdateRequest,
	SchedulerJobControlResponse,
)
from app.scheduler.monitor_job import (
	apply_monitor_job_runtime_config,
	get_monitor_job_status,
	pause_monitor_job,
	restart_monitor_job,
)
from app.services.config_service import get_runtime_config, update_runtime_config


router = APIRouter(tags=["configuration"])

SCHEDULER_RUNTIME_KEYS = {
	"SCHEDULER_INTERVAL_MINUTES",
	"SCHEDULER_START_MODE",
	"SCHEDULER_STARTUP_DELAY_SECONDS",
}


@router.get("/admin/config", response_model=RuntimeConfigResponse)
def get_admin_runtime_config() -> RuntimeConfigResponse:
	return RuntimeConfigResponse(data=get_runtime_config())


@router.patch("/admin/config", response_model=RuntimeConfigResponse)
def patch_admin_runtime_config(payload: RuntimeConfigUpdateRequest) -> RuntimeConfigResponse:
	try:
		updated = update_runtime_config(payload.updates)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	if any(key in SCHEDULER_RUNTIME_KEYS for key in updated.keys()):
		apply_monitor_job_runtime_config(run_now=False)

	return RuntimeConfigResponse(data=updated)


@router.get("/admin/jobs/monitor", response_model=SchedulerJobControlResponse)
def get_admin_monitor_job_status() -> SchedulerJobControlResponse:
	return SchedulerJobControlResponse(data=get_monitor_job_status())


@router.post("/admin/jobs/monitor/pause", response_model=SchedulerJobControlResponse)
def post_admin_pause_monitor_job() -> SchedulerJobControlResponse:
	return SchedulerJobControlResponse(data=pause_monitor_job())


@router.post("/admin/jobs/monitor/restart", response_model=SchedulerJobControlResponse)
def post_admin_restart_monitor_job(run_now: bool = False) -> SchedulerJobControlResponse:
	return SchedulerJobControlResponse(data=restart_monitor_job(run_now=run_now))
