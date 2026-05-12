from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone

from app import config
from app.utils.logger import get_logger

scheduler = AsyncIOScheduler()
logger = get_logger(__name__)
MONITOR_JOB_ID = "monitor_cluster_job"


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
				engine_pb2.ComputeDecisionRequest(trigger_source="api_scheduler"),
				timeout=300,
			)
		logger.info("Engine decision cycle triggered by API scheduler: status=%s", response.status)
	except Exception as exc:  # pylint: disable=broad-except
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
			misfire_grace_time=60,
			max_instances=1,
			coalesce=True,
			replace_existing=True,
		)
	return scheduler.get_job(MONITOR_JOB_ID)


def pause_monitor_job() -> dict:
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


def restart_monitor_job(run_now: bool = False) -> dict:
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


def apply_monitor_job_runtime_config(run_now: bool = False) -> dict:
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
	}


def get_monitor_job_status() -> dict:
	job = scheduler.get_job(MONITOR_JOB_ID)
	return {
		"job_id": MONITOR_JOB_ID,
		"scheduler_running": scheduler.running,
		"job_exists": job is not None,
		"paused": bool(job and job.next_run_time is None),
		"next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
	}

