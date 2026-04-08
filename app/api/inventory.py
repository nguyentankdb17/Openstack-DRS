from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app import config
from app.decision.datasource.openstack_inventory import OpenStackInventoryDatasource
from app.decision.datasource.prometheus_datasource import PrometheusDatasource


router = APIRouter(tags=["inventory"])


@router.get("/inventory/test")
def test_inventory() -> list[dict[str, Any]]:
	"""Return merged host+vm inventory payload for manual testing."""
	inventory_datasource = OpenStackInventoryDatasource()
	if not inventory_datasource.is_available():
		raise HTTPException(
			status_code=503,
			detail="OpenStack connection is unavailable. Check OPENSTACK_* configuration.",
		)

	prometheus_datasource = PrometheusDatasource()
	host_metrics = prometheus_datasource.build_host_snapshots(
		window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)
	vm_metrics = prometheus_datasource.build_vm_snapshots(
		window_minutes=config.CHECK_EVENT_LOOKBACK_MINUTES,
		step_seconds=config.PREDICTION_STEP_SECONDS,
	)
	return inventory_datasource.build_inventory(host_metrics=host_metrics, vm_metrics=vm_metrics)