from __future__ import annotations

from app.models.schemas import MigrationCandidate, VMHostAffinityRule, VMInventory, VMAffinityRule


def _normalized_host_set(hosts: list[str]) -> set[str]:
	return {str(host).strip() for host in hosts if str(host).strip()}


def _vm_host_rule_reasons(vm_id: str, target_host: str, rules: list[VMHostAffinityRule]) -> list[str]:
	reasons: list[str] = []
	for rule in rules:
		if rule.vm_id != vm_id:
			continue

		allowed_hosts = _normalized_host_set(rule.allowed_hosts)
		forbidden_hosts = _normalized_host_set(rule.forbidden_hosts)

		if allowed_hosts and target_host not in allowed_hosts:
			reasons.append(
				f"rule={rule.rule_id}: vm={vm_id} must be placed on one of {sorted(allowed_hosts)}, target={target_host}"
			)
		if target_host in forbidden_hosts:
			reasons.append(
				f"rule={rule.rule_id}: vm={vm_id} is forbidden on host={target_host}"
			)
	return reasons


def _vm_vm_rule_reasons(
	vm_id: str,
	target_host: str,
	placements: dict[str, str],
	rules: list[VMAffinityRule],
) -> list[str]:
	reasons: list[str] = []
	for rule in rules:
		group = [item for item in rule.vm_ids if item]
		if vm_id not in group or len(group) < 2:
			continue

		peer_vm_ids = [peer_vm_id for peer_vm_id in group if peer_vm_id != vm_id]
		known_peers = [(peer_vm_id, placements.get(peer_vm_id)) for peer_vm_id in peer_vm_ids if placements.get(peer_vm_id)]
		if not known_peers:
			continue

		if rule.policy == "must_separate":
			conflicts = [peer_vm_id for peer_vm_id, host_name in known_peers if host_name == target_host]
			if conflicts:
				reasons.append(
					f"rule={rule.rule_id}: vm={vm_id} must separate from {sorted(conflicts)}, target={target_host}"
				)
			continue

		if rule.policy == "must_together":
			divergent = [f"{peer_vm_id}@{host_name}" for peer_vm_id, host_name in known_peers if host_name != target_host]
			if divergent:
				reasons.append(
					f"rule={rule.rule_id}: vm={vm_id} must colocate with peers={sorted(divergent)}, target={target_host}"
				)

	return reasons


def evaluate_candidate(
	candidate: MigrationCandidate,
	vm_inventory: list[VMInventory],
	vm_host_rules: list[VMHostAffinityRule],
	vm_vm_rules: list[VMAffinityRule],
) -> tuple[bool, list[str]]:
	vm_by_id = {vm.vm_id: vm for vm in vm_inventory}
	placements = {vm.vm_id: vm.current_host for vm in vm_inventory}
	vm = vm_by_id.get(candidate.vm_id)
	if vm is None:
		return False, [f"vm={candidate.vm_id} not found in inventory"]

	reasons: list[str] = []
	if vm.current_host != candidate.source_host:
		reasons.append(
			f"stale_source: vm={candidate.vm_id} current={vm.current_host} candidate_source={candidate.source_host}"
		)

	reasons.extend(_vm_host_rule_reasons(candidate.vm_id, candidate.target_host, vm_host_rules))

	projected_placements = dict(placements)
	projected_placements[candidate.vm_id] = candidate.target_host
	reasons.extend(
		_vm_vm_rule_reasons(
			vm_id=candidate.vm_id,
			target_host=candidate.target_host,
			placements=projected_placements,
			rules=vm_vm_rules,
		)
	)

	return len(reasons) == 0, reasons


def filter_candidates(
	candidates: list[MigrationCandidate],
	vm_inventory: list[VMInventory],
	vm_host_rules: list[VMHostAffinityRule],
	vm_vm_rules: list[VMAffinityRule],
) -> tuple[list[MigrationCandidate], list[MigrationCandidate]]:
	allowed: list[MigrationCandidate] = []
	rejected: list[MigrationCandidate] = []

	for candidate in candidates:
		is_allowed, reasons = evaluate_candidate(candidate, vm_inventory, vm_host_rules, vm_vm_rules)
		evaluated_candidate = candidate.model_copy(update={"policy_reasons": reasons})
		if is_allowed:
			allowed.append(evaluated_candidate)
		else:
			rejected.append(evaluated_candidate)

	return allowed, rejected
