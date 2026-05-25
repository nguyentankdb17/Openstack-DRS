from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.decision.datasource.openstack_inventory import OpenStackInventoryDatasource
from app.models.schemas import (
	ConstraintHostOption,
	ConstraintInventoryOptions,
	ConstraintRecord,
	ConstraintVMOption,
	ExcludeConstraintUpsert,
	VMHostConstraintUpsert,
	VMVMConstraintUpsert,
)
from app.domain.constraint_service import (
	delete_constraint,
	get_constraint,
	list_constraints,
	set_constraint_enabled,
	upsert_exclude_constraint,
	upsert_vm_host_constraint,
	upsert_vm_vm_constraint,
)


router = APIRouter(tags=["constraints"])


@router.get("/constraints", response_model=list[ConstraintRecord])
def get_constraints() -> list[ConstraintRecord]:
	return list_constraints()


@router.get("/constraints/options", response_model=ConstraintInventoryOptions)
def get_constraint_inventory_options() -> ConstraintInventoryOptions:
	datasource = OpenStackInventoryDatasource()
	if not datasource.is_available():
		return ConstraintInventoryOptions()

	try:
		vms = [
			ConstraintVMOption(
				id=vm.vm_id,
				name=vm.name,
				current_host=vm.current_host,
			)
			for vm in datasource.list_vms()
		]
		hosts = [
			ConstraintHostOption(
				id=host.host,
				name=host.metadata.get("hostname") or host.host,
				state=host.state,
				status=host.metadata.get("status"),
			)
			for host in datasource.list_hosts()
		]
	except Exception as exc:
		raise HTTPException(status_code=502, detail=f"Unable to load OpenStack inventory: {exc}") from exc

	return ConstraintInventoryOptions(
		vms=sorted(vms, key=lambda item: ((item.name or item.id).lower(), item.id)),
		hosts=sorted(hosts, key=lambda item: ((item.name or item.id).lower(), item.id)),
	)


@router.get("/constraints/{rule_name}", response_model=ConstraintRecord)
def get_constraint_by_rule_name(rule_name: str) -> ConstraintRecord:
	item = get_constraint(rule_name)
	if item is None:
		raise HTTPException(status_code=404, detail=f"Constraint rule_name={rule_name} not found")
	return item


@router.post("/constraints/vm-host", response_model=ConstraintRecord)
def create_or_update_vm_host_constraint(payload: VMHostConstraintUpsert) -> ConstraintRecord:
	return upsert_vm_host_constraint(payload)


@router.post("/constraints/vm-vm", response_model=ConstraintRecord)
def create_or_update_vm_vm_constraint(payload: VMVMConstraintUpsert) -> ConstraintRecord:
	return upsert_vm_vm_constraint(payload)


@router.post("/constraints/exclude", response_model=ConstraintRecord)
def create_or_update_exclude_constraint(payload: ExcludeConstraintUpsert) -> ConstraintRecord:
	return upsert_exclude_constraint(payload)


@router.put("/constraints/vm-host/{rule_name}", response_model=ConstraintRecord)
def update_vm_host_constraint(rule_name: str, payload: VMHostConstraintUpsert) -> ConstraintRecord:
	merged_payload = payload.model_copy(update={"rule_name": rule_name})
	return upsert_vm_host_constraint(merged_payload)


@router.put("/constraints/vm-vm/{rule_name}", response_model=ConstraintRecord)
def update_vm_vm_constraint(rule_name: str, payload: VMVMConstraintUpsert) -> ConstraintRecord:
	merged_payload = payload.model_copy(update={"rule_name": rule_name})
	return upsert_vm_vm_constraint(merged_payload)


@router.put("/constraints/exclude/{rule_name}", response_model=ConstraintRecord)
def update_exclude_constraint(rule_name: str, payload: ExcludeConstraintUpsert) -> ConstraintRecord:
	merged_payload = payload.model_copy(update={"rule_name": rule_name})
	return upsert_exclude_constraint(merged_payload)


@router.delete("/constraints/{rule_name}")
def remove_constraint(rule_name: str) -> dict[str, bool]:
	deleted = delete_constraint(rule_name)
	if not deleted:
		raise HTTPException(status_code=404, detail=f"Constraint rule_name={rule_name} not found")
	return {"deleted": True}


@router.patch("/constraints/{rule_name}/enable", response_model=ConstraintRecord)
def patch_constraint_enabled(rule_name: str, enabled: bool = True) -> ConstraintRecord:
	item = set_constraint_enabled(rule_name, enabled)
	if item is None:
		raise HTTPException(status_code=404, detail=f"Constraint rule_name={rule_name} not found")
	return item
