from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app import config
from app.decision.planner.simulate_migration import compute_inventory_imbalance, simulate_migration
from app.decision.constraints.affinity_policy import filter_candidates
from app.models.schemas import (
	HostMetricSnapshot,
	MigrationCandidate,
	MigrationPlan,
	VMHostAffinityRule,
	VMInventory,
	VMAffinityRule,
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _to_float(value: Any) -> float:
	if value in (None, ""):
		return 0.0
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0


def _build_inventory_payload(
	host_metrics: list[HostMetricSnapshot],
	vm_inventory: list[VMInventory],
) -> list[dict[str, Any]]:
	host_metric_map = {item.host: item for item in host_metrics}
	hosts = sorted({item.host for item in host_metrics} | {item.current_host for item in vm_inventory})
	host_to_vms: dict[str, list[VMInventory]] = {host: [] for host in hosts}
	for vm in vm_inventory:
		host_to_vms.setdefault(vm.current_host, []).append(vm)

	payload: list[dict[str, Any]] = []
	for host in hosts:
		metric = host_metric_map.get(host)
		payload.append(
			{
				"hostname": host,
				"cpu_allocated": _to_float(getattr(metric, "cpu_allocated", 0.0)),
				"cpu_usage": _to_float(getattr(metric, "cpu", 0.0)),
				"memory_allocated": _to_float(getattr(metric, "ram_allocated", 0.0)),
				"memory_usage": _to_float(getattr(metric, "ram", 0.0)),
				"swap_allocated": _to_float(getattr(metric, "swap_allocated", 0.0)),
				"swap_usage": _to_float(getattr(metric, "swap", 0.0)),
				"vm": [
					{
						"uuid": vm.vm_id,
						"instance_name": vm.name or "",
						"vcpu_allocated": _to_float(vm.cpu),
						"vcpu_usage": "",
						"memory_allocated": _to_float(vm.ram),
						"memory_usage": "",
					}
					for vm in host_to_vms.get(host, [])
				],
			}
		)
	return payload


def _refresh_vm_hosts(vm_inventory: list[VMInventory], candidate: MigrationCandidate) -> list[VMInventory]:
	updated: list[VMInventory] = []
	for vm in vm_inventory:
		if vm.vm_id == candidate.vm_id:
			updated.append(vm.model_copy(update={"current_host": candidate.target_host}))
		else:
			updated.append(vm)
	return updated


def _all_raw_candidates(inventory_payload: list[dict[str, Any]]) -> list[MigrationCandidate]:
	hosts = [str(item.get("hostname", "")) for item in inventory_payload if item.get("hostname")]
	raw_candidates: list[MigrationCandidate] = []
	host_vm_counts: dict[str, int] = {}
	for source_payload in inventory_payload:
		source_host = str(source_payload.get("hostname", ""))
		host_vm_counts[source_host] = len(source_payload.get("vm", []))
		for vm in source_payload.get("vm", []):
			vm_id = str(vm.get("uuid", ""))
			if not vm_id:
				continue
			for target_host in hosts:
				if target_host == source_host:
					continue
				raw_candidates.append(
					MigrationCandidate(
						vm_id=vm_id,
						source_host=source_host,
						target_host=target_host,
						migration_cost=0.0,
						policy_reasons=[],
						score_breakdown={},
					)
				)
	logger.debug(
		"inventory scan complete: hosts=%d host_vm_counts=%s generated_candidates=%d",
		len(hosts),
		host_vm_counts,
		len(raw_candidates),
	)
	return raw_candidates


@dataclass(slots=True)
class MigrationPlanner:
	def build_plan(
		self,
		host_metrics: list[HostMetricSnapshot],
		vm_inventory: list[VMInventory],
		vm_host_rules: list[VMHostAffinityRule] | None = None,
		vm_vm_rules: list[VMAffinityRule] | None = None,
		current_cluster_imbalance: float | None = None,
		inventory_payload: list[dict[str, Any]] | None = None,
	) -> MigrationPlan:
		vm_host_rules = vm_host_rules or []
		vm_vm_rules = vm_vm_rules or []
		working_inventory = deepcopy(inventory_payload) if inventory_payload is not None else _build_inventory_payload(host_metrics, vm_inventory)
		if not working_inventory:
			logger.debug("build_plan aborted: empty working inventory")
			return MigrationPlan(
				candidates=[],
				current_cluster_imbalance=current_cluster_imbalance,
				details="No inventory available for migration simulation",
			)

		baseline_imbalance = (
			float(current_cluster_imbalance)
			if current_cluster_imbalance is not None
			else compute_inventory_imbalance(working_inventory)
		)
		if baseline_imbalance <= config.CLUSTER_IMBALANCE_THRESHOLD:
			logger.debug(
				"build_plan skipped: imbalance already under threshold baseline=%.6f threshold=%.6f",
				baseline_imbalance,
				config.CLUSTER_IMBALANCE_THRESHOLD,
			)
			return MigrationPlan(
				candidates=[],
				current_cluster_imbalance=baseline_imbalance,
				details="Cluster imbalance is already under threshold",
			)

		planned_candidates: list[MigrationCandidate] = []
		used_vm_ids: set[str] = set()
		working_vm_inventory = list(vm_inventory)
		current_imbalance = baseline_imbalance
		remaining_steps = max(1, sum(len(item.get("vm", [])) for item in working_inventory))
		logger.debug(
			"build_plan start: baseline_imbalance=%.6f threshold=%.6f max_steps=%d",
			baseline_imbalance,
			config.CLUSTER_IMBALANCE_THRESHOLD,
			remaining_steps,
		)

		while current_imbalance > config.CLUSTER_IMBALANCE_THRESHOLD and remaining_steps > 0:
			current_step = len(planned_candidates) + 1
			raw_candidates = _all_raw_candidates(working_inventory)
			if not raw_candidates:
				logger.debug("build_plan stop at step=%d: no raw candidates", current_step)
				break

			allowed_candidates, _ = filter_candidates(raw_candidates, working_vm_inventory, vm_host_rules, vm_vm_rules)
			allowed_candidates = [candidate for candidate in allowed_candidates if candidate.vm_id not in used_vm_ids]
			logger.debug(
				"build_plan step=%d: raw_candidates=%d allowed_candidates=%d used_vm_ids=%s current_imbalance=%.6f",
				current_step,
				len(raw_candidates),
				len(allowed_candidates),
				sorted(used_vm_ids),
				current_imbalance,
			)
			best_candidate: MigrationCandidate | None = None
			best_inventory: list[dict[str, Any]] | None = None
			best_imbalance = current_imbalance

			for candidate in allowed_candidates:
				simulation = simulate_migration(
					inventory=working_inventory,
					vm_id=candidate.vm_id,
					source_host=candidate.source_host,
					target_host=candidate.target_host,
				)
				if simulation is None:
					continue
				logger.debug(
					"simulation result: vm_id=%s source=%s target=%s imbalance_before=%.6f imbalance_after=%.6f",
					candidate.vm_id,
					candidate.source_host,
					candidate.target_host,
					current_imbalance,
					simulation.cluster_imbalance,
				)

				if simulation.cluster_imbalance >= best_imbalance:
					continue

				candidate_score = current_imbalance - simulation.cluster_imbalance
				best_candidate = candidate.model_copy(
					update={
						"score_breakdown": {
							"imbalance_before": current_imbalance,
							"imbalance_after": simulation.cluster_imbalance,
							"imbalance_reduction": candidate_score,
						}
					}
				)
				best_inventory = simulation.inventory
				best_imbalance = simulation.cluster_imbalance
				logger.debug(
					"new best candidate at step=%d: vm_id=%s source=%s target=%s reduction=%.6f",
					current_step,
					candidate.vm_id,
					candidate.source_host,
					candidate.target_host,
					candidate_score,
				)

			if best_candidate is None or best_inventory is None:
				logger.debug("build_plan stop at step=%d: no candidate improved imbalance", current_step)
				break

			planned_candidates.append(best_candidate)
			used_vm_ids.add(best_candidate.vm_id)
			working_inventory = best_inventory
			working_vm_inventory = _refresh_vm_hosts(working_vm_inventory, best_candidate)
			current_imbalance = best_imbalance
			remaining_steps -= 1
			logger.debug(
				"build_plan apply step=%d: selected vm_id=%s source=%s target=%s new_imbalance=%.6f used_vm_ids=%s remaining_steps=%d",
				current_step,
				best_candidate.vm_id,
				best_candidate.source_host,
				best_candidate.target_host,
				current_imbalance,
				sorted(used_vm_ids),
				remaining_steps,
			)

		if planned_candidates:
			details = (
				"Migration candidates selected greedily by maximum imbalance reduction "
				f"({baseline_imbalance:.4f} -> {current_imbalance:.4f})"
			)
		else:
			details = "No migration candidate can further reduce cluster imbalance"

		logger.debug(
			"build_plan done: selected_candidates=%d baseline_imbalance=%.6f final_imbalance=%.6f",
			len(planned_candidates),
			baseline_imbalance,
			current_imbalance,
		)

		return MigrationPlan(
			candidates=planned_candidates,
			current_cluster_imbalance=baseline_imbalance,
			details=details,
		)