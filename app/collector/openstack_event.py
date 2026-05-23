from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

try:
	import pymysql
except ImportError:
	pymysql = None

from openstack import connection

from app import config
from app.core.constants import VM_EVENT_ACTIONS
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _to_datetime(value: Any) -> datetime | None:
	if value is None:
		return None
	if isinstance(value, datetime):
		return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
	if isinstance(value, str):
		parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
		return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
	return None


def _build_conn() -> connection.Connection | None:
	if not all(
		[
			config.OPENSTACK_AUTH_URL,
			config.OPENSTACK_USERNAME,
			config.OPENSTACK_PASSWORD,
			config.OPENSTACK_PROJECT_NAME,
		]
	):
		logger.warning("OpenStack credentials are not fully configured; event check skipped")
		return None

	return connection.Connection(
		auth_url=config.OPENSTACK_AUTH_URL,
		username=config.OPENSTACK_USERNAME,
		password=config.OPENSTACK_PASSWORD,
		project_name=config.OPENSTACK_PROJECT_NAME,
		user_domain_name=config.OPENSTACK_USER_DOMAIN_NAME,
		project_domain_name=config.OPENSTACK_PROJECT_DOMAIN_NAME,
		region_name=config.OPENSTACK_REGION_NAME,
	)


def _nova_db_enabled() -> bool:
	return all([config.NOVA_DB_HOST, config.NOVA_DB_USER, config.NOVA_DB_PASSWORD, config.NOVA_DB_NAME])


def _query_recent_events_from_nova_db(lookback_minutes: int) -> tuple[bool, list[str]]:
	if pymysql is None:
		logger.warning("PyMySQL is not installed; skipping Nova DB event check")
		return False, []

	if not _nova_db_enabled():
		logger.warning("Nova DB config is incomplete; skipping Nova DB event check")
		return False, []

	query = """
	SELECT
		host,
		created_at,
		updated_at,
		deleted,
		deleted_at,
		task_state
	FROM instances
	WHERE
		created_at >= (UTC_TIMESTAMP() - INTERVAL %s MINUTE)
		OR updated_at >= (UTC_TIMESTAMP() - INTERVAL %s MINUTE)
		OR deleted_at >= (UTC_TIMESTAMP() - INTERVAL %s MINUTE)
	ORDER BY updated_at DESC
	"""

	detected: list[str] = []
	conn = None
	try:
		conn = pymysql.connect(
			host=config.NOVA_DB_HOST,
			port=config.NOVA_DB_PORT,
			user=config.NOVA_DB_USER,
			password=config.NOVA_DB_PASSWORD,
			database=config.NOVA_DB_NAME,
			connect_timeout=config.NOVA_DB_CONNECT_TIMEOUT_SECONDS,
			cursorclass=pymysql.cursors.DictCursor,
		)

		with conn.cursor() as cursor:
			cursor.execute(query, (lookback_minutes, lookback_minutes, lookback_minutes))
			rows = cursor.fetchall()

		for row in rows:
			host = row.get("host") or "unknown"
			task_state = (row.get("task_state") or "").lower()
			deleted = bool(row.get("deleted"))

			if row.get("created_at"):
				detected.append(f"{host}:create")
			if deleted or row.get("deleted_at"):
				detected.append(f"{host}:delete")
			if any(action in task_state for action in VM_EVENT_ACTIONS):
				detected.append(f"{host}:{task_state}")
	except Exception as exc:
		logger.exception("Nova DB event check failed: %s", exc)
		return False, []
	finally:
		if conn is not None:
			conn.close()

	return True, list(dict.fromkeys(detected))


def _query_recent_events_from_openstack_api(lookback_minutes: int) -> list[str]:
	conn = _build_conn()
	if conn is None:
		return []

	since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
	detected: list[str] = []

	servers = conn.compute.servers(details=True, all_projects=True)
	for server in servers:
		created_at = _to_datetime(getattr(server, "created_at", None))
		updated_at = _to_datetime(getattr(server, "updated_at", None))
		task_state = (getattr(server, "task_state", "") or "").lower()

		if created_at and created_at >= since:
			detected.append(f"{server.name}:create")

		if updated_at and updated_at >= since:
			if any(action in task_state for action in VM_EVENT_ACTIONS):
				detected.append(f"{server.name}:{task_state}")

		if getattr(server, "status", "").upper() == "DELETED" and updated_at and updated_at >= since:
			detected.append(f"{server.name}:delete")

	return list(dict.fromkeys(detected))


def has_recent_vm_events(lookback_minutes: int) -> tuple[bool, list[str]]:
	db_checked, detected_from_db = _query_recent_events_from_nova_db(lookback_minutes)
	if db_checked:
		if detected_from_db:
			logger.info("Detected %d recent VM events from Nova DB", len(detected_from_db))
		else:
			logger.debug("No recent VM events found in Nova DB")
		return len(detected_from_db) > 0, detected_from_db

	logger.info("Falling back to OpenStack API for VM event check")

	try:
		detected = _query_recent_events_from_openstack_api(lookback_minutes)
	except Exception as exc:
		logger.exception("Failed to check OpenStack events: %s", exc)
		return False, []

	return len(detected) > 0, detected
