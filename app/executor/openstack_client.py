from __future__ import annotations

from dataclasses import dataclass

from openstack import connection

from app import config
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _build_conn() -> connection.Connection | None:
	if not all(
		[
			config.OPENSTACK_AUTH_URL,
			config.OPENSTACK_USERNAME,
			config.OPENSTACK_PASSWORD,
			config.OPENSTACK_PROJECT_NAME,
		]
	):
		logger.warning("OpenStack credentials are not fully configured; migration execution disabled")
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


@dataclass(slots=True)
class OpenStackClient:
	connection: connection.Connection | None = None

	def __post_init__(self) -> None:
		if self.connection is None:
			self.connection = _build_conn()

	def is_available(self) -> bool:
		return self.connection is not None

	def live_migrate(self, vm_id: str, target_host: str) -> None:
		if self.connection is None:
			raise RuntimeError("OpenStack client is not configured")

		server = self.connection.compute.get_server(vm_id)
		if server is None:
			raise RuntimeError(f"Server {vm_id} was not found")

		self.connection.compute.live_migrate_server(
			server,
			host=target_host,
			block_migration=False,
			disk_over_commit=False,
		)