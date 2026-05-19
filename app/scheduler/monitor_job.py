from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone

from app import config
from app.utils.logger import get_logger

scheduler = AsyncIOScheduler()
logger = get_logger(__name__)
MONITOR_JOB_ID = "monitor_cluster_job"


def _misfire_grace_time_seconds() -> int:
    interval_seconds = max(int(config.SCHEDULER_INTERVAL_MINUTES) * 60, 60)
    configured_seconds = max(int(config.SCHEDULER_MISFIRE_GRACE_SECONDS), 60)
    return max(configured_seconds, interval_seconds)


def _resolve_next_run_time() -> datetime | None:
    start_mode = config.SCHEDULER_START_MODE
    if start_mode == "immediate":
        delay_seconds = max(config.SCHEDULER_STARTUP_DELAY_SECONDS, 0)
        next_run_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        logger.info(
            "Scheduler start mode=immediate, first run at %s (delay=%ss)",
            next_run_time.isoformat(),
            delay_seconds,
        )
        return next_run_time

    if start_mode != "lazy":
        logger.warning(
            "Invalid SCHEDULER_START_MODE=%s. Falling back to lazy mode.",
            start_mode,
        )

    logger.info("Scheduler start mode=lazy, first run follows the interval schedule")
    return None


async def monitor_cluster():
	from app.grpc import engine_pb2
	from app.clients.rpc_clients import engine_client

	try:
		async with engine_client() as stub:
			response = await stub.ComputeDecision(
				engine_pb2.ComputeDecisionRequest(trigger_source="openstack_drs"),
				timeout=300,
			)
		logger.info("Engine decision cycle triggered by API scheduler: status=%s", response.status)
	except Exception as exc:  
		logger.exception("API scheduler failed to trigger engine decision cycle via gRPC: %s", exc)


def _ensure_monitor_job():
	job = scheduler.get_job(MONITOR_JOB_ID)
	if job is None:
		next_run_time = _resolve_next_run_time()
		scheduler.add_job(
			monitor_cluster,
			"interval",
			id=MONITOR_JOB_ID,
			minutes=config.SCHEDULER_INTERVAL_MINUTES,
			next_run_time=next_run_time,
			misfire_grace_time=_misfire_grace_time_seconds(),
			max_instances=1,
			coalesce=True,
			replace_existing=True,
		)
	else:
		scheduler.modify_job(job.id, misfire_grace_time=_misfire_grace_time_seconds())
	return scheduler.get_job(MONITOR_JOB_ID)


async def start_monitor_scheduler() -> dict:
	job = _ensure_monitor_job()
	if not scheduler.running:
		scheduler.start()

	job = scheduler.get_job(MONITOR_JOB_ID)
	if job is not None:
		if job.next_run_time is None:
			scheduler.resume_job(job.id)
		job = scheduler.get_job(MONITOR_JOB_ID)

	logger.info(
		"API monitor scheduler started: running=%s interval=%s next_run_time=%s",
		scheduler.running,
		config.SCHEDULER_INTERVAL_MINUTES,
		job.next_run_time.isoformat() if job and job.next_run_time else None,
	)
	return {
		"job_id": MONITOR_JOB_ID,
		"action": "started",
		"scheduler_running": scheduler.running,
		"job_exists": job is not None,
		"next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
		"interval_minutes": config.SCHEDULER_INTERVAL_MINUTES,
		"misfire_grace_seconds": _misfire_grace_time_seconds(),
	}


async def shutdown_monitor_scheduler() -> None:
	if scheduler.running:
		scheduler.shutdown(wait=False)


async def pause_monitor_job() -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "pause_failed",
			"scheduler_running": scheduler.running,
		}

	scheduler.pause_job(job.id)
	return {
		"job_id": job.id,
		"action": "paused",
		"scheduler_running": scheduler.running,
	}


async def restart_monitor_job(run_now: bool = False) -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "restart_failed",
			"run_now": run_now,
			"scheduler_running": scheduler.running,
			"next_run_time": None,
		}

	if not scheduler.running:
		scheduler.start()

	scheduler.resume_job(job.id)
	if run_now:
		scheduler.modify_job(job.id, next_run_time=datetime.now(timezone.utc))

	updated_job = scheduler.get_job(job.id)
	return {
		"job_id": job.id,
		"action": "restarted",
		"run_now": run_now,
		"scheduler_running": scheduler.running,
		"next_run_time": updated_job.next_run_time.isoformat() if updated_job and updated_job.next_run_time else None,
	}


async def apply_monitor_job_runtime_config(run_now: bool = False) -> dict:
	job = _ensure_monitor_job()
	if job is None:
		return {
			"job_id": MONITOR_JOB_ID,
			"action": "apply_config_failed",
			"run_now": run_now,
			"scheduler_running": scheduler.running,
			"next_run_time": None,
		}

	if not scheduler.running:
		scheduler.start()

	was_paused = bool(job.next_run_time is None)
	scheduler.reschedule_job(
		job.id,
		trigger="interval",
		minutes=config.SCHEDULER_INTERVAL_MINUTES,
	)
	scheduler.modify_job(job.id, misfire_grace_time=_misfire_grace_time_seconds())

	if run_now:
		scheduler.modify_job(job.id, next_run_time=datetime.now(timezone.utc))

	if was_paused:
		scheduler.pause_job(job.id)

	updated_job = scheduler.get_job(job.id)
	return {
		"job_id": job.id,
		"action": "config_applied",
		"run_now": run_now,
		"scheduler_running": scheduler.running,
		"next_run_time": updated_job.next_run_time.isoformat() if updated_job and updated_job.next_run_time else None,
		"interval_minutes": config.SCHEDULER_INTERVAL_MINUTES,
		"misfire_grace_seconds": _misfire_grace_time_seconds(),
	}


def get_monitor_job_status() -> dict:
	job = scheduler.get_job(MONITOR_JOB_ID)
	return {
		"job_id": MONITOR_JOB_ID,
		"scheduler_running": scheduler.running,
		"job_exists": job is not None,
		"paused": bool(job and job.next_run_time is None),
		"next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
		"misfire_grace_seconds": _misfire_grace_time_seconds(),
	}
