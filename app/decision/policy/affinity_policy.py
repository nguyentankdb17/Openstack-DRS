from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import MigrationCandidate, VMHostAffinityRule, VMInventory, VMAffinityRule


@dataclass(slots=True)
class PolicyDecision:
	allowed: bool
	reasons: list[str]


def _vm_host_rule_reasons(vm: VMInventory, target_host: str, rules: list[VMHostAffinityRule]) -> list[str]:
	reasons: list[str] = []
	for rule in rules:
		if rule.vm_id != vm.vm_id:
			continue
		if rule.allowed_hosts and target_host not in rule.allowed_hosts:
			reasons.append(f"target host {target_host} is not allowed for {vm.vm_id}")
		if target_host in rule.forbidden_hosts:
			reasons.append(f"target host {target_host} is forbidden for {vm.vm_id}")
	return reasons


def _vm_vm_rule_reasons(vm: VMInventory, target_host: str, placements: dict[str, str], rules: list[VMAffinityRule]) -> list[str]:
	reasons: list[str] = []
	for rule in rules:
		if vm.vm_id not in rule.vm_ids:
			continue

		other_vm_ids = [vm_id for vm_id in rule.vm_ids if vm_id != vm.vm_id]
		other_hosts = {placements.get(vm_id) for vm_id in other_vm_ids if placements.get(vm_id)}
		if rule.policy == "must_together" and other_hosts and target_host not in other_hosts:
			reasons.append(f"{vm.vm_id} must stay with affinity group {rule.rule_id}")
		if rule.policy == "must_separate" and target_host in other_hosts:
			reasons.append(f"{vm.vm_id} must stay separate from affinity group {rule.rule_id}")
	return reasons


def evaluate_candidate(
	candidate: MigrationCandidate,
	vm_inventory: list[VMInventory],
	vm_host_rules: list[VMHostAffinityRule],
	vm_vm_rules: list[VMAffinityRule],
) -> PolicyDecision:
	vm_map = {vm.vm_id: vm for vm in vm_inventory}
	vm = vm_map.get(candidate.vm_id)
	if vm is None:
		return PolicyDecision(False, [f"vm {candidate.vm_id} was not found in inventory"])

	placements = {item.vm_id: item.current_host for item in vm_inventory}
	reasons = []
	reasons.extend(_vm_host_rule_reasons(vm, candidate.target_host, vm_host_rules))
	reasons.extend(_vm_vm_rule_reasons(vm, candidate.target_host, placements, vm_vm_rules))
	return PolicyDecision(allowed=not reasons, reasons=reasons)


def filter_candidates(
	candidates: list[MigrationCandidate],
	vm_inventory: list[VMInventory],
	vm_host_rules: list[VMHostAffinityRule],
	vm_vm_rules: list[VMAffinityRule],
) -> tuple[list[MigrationCandidate], list[tuple[MigrationCandidate, list[str]]]]:
	allowed: list[MigrationCandidate] = []
	rejected: list[tuple[MigrationCandidate, list[str]]] = []

	for candidate in candidates:
		decision = evaluate_candidate(candidate, vm_inventory, vm_host_rules, vm_vm_rules)
		if decision.allowed:
			allowed.append(candidate)
		else:
			rejected.append((candidate, decision.reasons))

	return allowed, rejected
