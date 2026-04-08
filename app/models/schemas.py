from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


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


class HostDeviation(BaseModel):
	host: str
	score: float


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
	overloaded_hosts: list[HostDeviation] = Field(default_factory=list)
	candidates: list[MigrationCandidate] = Field(default_factory=list)
	current_cluster_imbalance: float | None = None
	details: str | None = None


class ClusterDecision(BaseModel):
	status: str
	timestamp: datetime
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	threshold: float
	recent_events: list[str] = Field(default_factory=list)
	unbalanced_hosts: list[HostDeviation] = Field(default_factory=list)
	planned_candidates: list[MigrationCandidate] = Field(default_factory=list)
	selected_candidate: MigrationCandidate | None = None
	execution_result: MigrationExecutionResult | None = None
	details: str | None = None


class MonitorResponse(BaseModel):
	data: ClusterDecision
