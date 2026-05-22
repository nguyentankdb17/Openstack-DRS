from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class HostMetricSnapshot(BaseModel):
	host: str
	cpu: float = Field(ge=0)
	ram: float = Field(ge=0)
	swap: float = Field(ge=0)
	running_vm: float = Field(default=0, ge=0)
	cpu_allocated: float = Field(default=0, ge=0)
	ram_allocated: float = Field(default=0, ge=0)
	swap_allocated: float = Field(default=0, ge=0)

class VMMetricSnapshot(BaseModel):
	uuid: str
	hostname: str
	cpu: float = Field(ge=0)
	ram: float = Field(ge=0)


class HostInventory(BaseModel):
	host: str
	cpu: float = Field(default=0, ge=0)
	ram: float = Field(default=0, ge=0)
	swap: float = Field(default=0, ge=0)
	running_vm: float = Field(default=0, ge=0)
	state: str | None = None
	metadata: dict[str, str] = Field(default_factory=dict)


class VMInventory(BaseModel):
	vm_id: str
	name: str | None = None
	current_host: str
	cpu: float = Field(default=0, ge=0)
	ram: float = Field(default=0, ge=0)
	swap: float = Field(default=0, ge=0)
	metadata: dict[str, str] = Field(default_factory=dict)


class VMAffinityRule(BaseModel):
	rule_id: str
	vm_ids: list[str] = Field(default_factory=list)
	policy: Literal["must_together", "must_separate"]


class VMHostAffinityRule(BaseModel):
	rule_id: str
	vm_id: str
	allowed_hosts: list[str] = Field(default_factory=list)
	forbidden_hosts: list[str] = Field(default_factory=list)


class ExcludeRule(BaseModel):
	rule_id: str
	vm_ids: list[str] = Field(default_factory=list)
	host_ids: list[str] = Field(default_factory=list)


class MigrationCandidate(BaseModel):
	vm_id: str
	source_host: str
	target_host: str
	migration_cost: float = Field(default=0)
	policy_reasons: list[str] = Field(default_factory=list)
	score_breakdown: dict[str, float] = Field(default_factory=dict)


class MigrationExecutionRequest(BaseModel):
	candidate: MigrationCandidate


class MigrationExecutionResult(BaseModel):
	vm_id: str
	source_host: str
	target_host: str
	success: bool
	message: str | None = None
	executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	metadata: dict[str, str] = Field(default_factory=dict)


class MigrationPlan(BaseModel):
	generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	candidates: list[MigrationCandidate] = Field(default_factory=list)
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	details: str | None = None


class ClusterDecision(BaseModel):
	status: str
	timestamp: datetime
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	threshold: float
	recent_events: list[str] = Field(default_factory=list)
	planned_candidates: list[MigrationCandidate] = Field(default_factory=list)
	selected_candidate: MigrationCandidate | None = None
	execution_result: MigrationExecutionResult | None = None
	details: str | None = None


class MonitorResponse(BaseModel):
	data: ClusterDecision


class ConstraintRecord(BaseModel):
	rule_name: str
	description: str = ""
	constraint_type: Literal["vm_host", "vm_vm", "exclude"]
	vm_id: str | None = None
	policy: Literal["must_together", "must_separate"] | None = None
	vm_ids: list[str] = Field(default_factory=list)
	allowed_hosts: list[str] = Field(default_factory=list)
	forbidden_hosts: list[str] = Field(default_factory=list)
	host_ids: list[str] = Field(default_factory=list)
	is_enabled: bool = True
	created_at: datetime
	updated_at: datetime


class VMHostConstraintUpsert(BaseModel):
	rule_name: str
	description: str = ""
	vm_id: str
	allowed_hosts: list[str] = Field(default_factory=list)
	forbidden_hosts: list[str] = Field(default_factory=list)
	is_enabled: bool = True


class VMVMConstraintUpsert(BaseModel):
	rule_name: str
	description: str = ""
	vm_ids: list[str] = Field(default_factory=list)
	policy: Literal["must_together", "must_separate"]
	is_enabled: bool = True


class ExcludeConstraintUpsert(BaseModel):
	rule_name: str
	description: str = ""
	vm_ids: list[str] = Field(default_factory=list)
	host_ids: list[str] = Field(default_factory=list)
	is_enabled: bool = True

	@model_validator(mode="after")
	def validate_single_scope(self) -> "ExcludeConstraintUpsert":
		has_vm_scope = any(str(item).strip() for item in self.vm_ids)
		has_host_scope = any(str(item).strip() for item in self.host_ids)
		if has_vm_scope == has_host_scope:
			raise ValueError("Exclude constraint must contain either vm_ids or host_ids, not both")
		return self


class CycleHistoryRecord(BaseModel):
	id: int
	cycle_started_at: datetime
	cycle_finished_at: datetime | None = None
	trigger_source: str
	status: str
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	threshold: float | None = None
	planned_candidates: list[MigrationCandidate] = Field(default_factory=list)
	executed_candidates: list[MigrationCandidate] = Field(default_factory=list)
	prediction_results: dict[str, Any] = Field(default_factory=dict)
	details: str | None = None
	decision_payload: dict[str, Any] = Field(default_factory=dict)
	error_message: str | None = None
	created_at: datetime


class LatestPredictionHistoryResponse(BaseModel):
	cycle_id: int | None = None
	cycle_started_at: datetime | None = None
	prediction_results: dict[str, Any] = Field(default_factory=dict)


class RuntimeConfigUpdateRequest(BaseModel):
	updates: dict[str, Any] = Field(default_factory=dict)


class RuntimeConfigResponse(BaseModel):
	data: dict[str, Any] = Field(default_factory=dict)


class SchedulerJobControlResponse(BaseModel):
	data: dict[str, Any] = Field(default_factory=dict)


class PendingPlan(BaseModel):
	"""A migration plan waiting for manual approval."""
	plan_id: str
	created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	cycle_started_at: datetime | None = None
	trigger_source: str
	candidates: list[MigrationCandidate] = Field(default_factory=list)
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	details: str | None = None


class ApproveRequest(BaseModel):
	"""Body for POST /api/v1/plan/approve.

	Leave candidate_ids empty to approve ALL candidates in the pending plan.
	"""
	candidate_ids: list[str] = Field(
		default_factory=list,
		description="VM IDs to approve. Empty list = approve all.",
	)
