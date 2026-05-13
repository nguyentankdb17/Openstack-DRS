from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ConstraintRecord, ExcludeConstraintUpsert, VMHostConstraintUpsert, VMVMConstraintUpsert
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
