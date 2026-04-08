from __future__ import annotations

from dataclasses import dataclass

from app.decision.planner.candidate_generator import build_candidate_pairs
from app.models.schemas import (
	HostDeviation,
	HostMetricSnapshot,
	MigrationPlan,
	VMHostAffinityRule,
	VMInventory,
	VMAffinityRule,
)
from app.scoring.migration_cost import rank_candidates


@dataclass(slots=True)
class MigrationPlanner:
	def build_plan(
		self,
		host_metrics: list[HostMetricSnapshot],
		overloaded_hosts: list[HostDeviation],
		vm_inventory: list[VMInventory],
		vm_host_rules: list[VMHostAffinityRule] | None = None,
		vm_vm_rules: list[VMAffinityRule] | None = None,
		current_cluster_imbalance: float | None = None,
	) -> MigrationPlan:
		vm_host_rules = vm_host_rules or []
		vm_vm_rules = vm_vm_rules or []
		candidates = build_candidate_pairs(
			host_metrics=host_metrics,
			overloaded_hosts=overloaded_hosts,
			vm_inventory=vm_inventory,
			vm_host_rules=vm_host_rules,
			vm_vm_rules=vm_vm_rules,
		)
		ranked_candidates = rank_candidates(candidates, host_metrics, vm_inventory)
		return MigrationPlan(
			overloaded_hosts=overloaded_hosts,
			candidates=ranked_candidates,
			current_cluster_imbalance=current_cluster_imbalance,
			details="Candidates ranked by migration cost",
		)