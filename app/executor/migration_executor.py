from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.executor.openstack_client import OpenStackClient
from app.models.schemas import MigrationCandidate, MigrationExecutionResult
from app.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(slots=True)
class MigrationExecutor:
	client: OpenStackClient | None = None

	def __post_init__(self) -> None:
		if self.client is None:
			self.client = OpenStackClient()

	def execute(self, candidate: MigrationCandidate) -> MigrationExecutionResult:
		assert self.client is not None
		try:
			self.client.live_migrate(candidate.vm_id, candidate.target_host)
			message = f"Migration requested for {candidate.vm_id} to {candidate.target_host}"
			logger.info(message)
			return MigrationExecutionResult(
				vm_id=candidate.vm_id,
				source_host=candidate.source_host,
				target_host=candidate.target_host,
				success=True,
				message=message,
				executed_at=datetime.now(timezone.utc),
			)
		except Exception as exc:  # pylint: disable=broad-except
			logger.exception("Migration failed for vm %s: %s", candidate.vm_id, exc)
			return MigrationExecutionResult(
				vm_id=candidate.vm_id,
				source_host=candidate.source_host,
				target_host=candidate.target_host,
				success=False,
				message=str(exc),
				executed_at=datetime.now(timezone.utc),
			)