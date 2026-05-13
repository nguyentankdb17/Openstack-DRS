from __future__ import annotations

from app.models.schemas import ExcludeRule, MigrationCandidate


def _normalized_set(items: list[str]) -> set[str]:
	return {str(item).strip() for item in items if str(item).strip()}


def evaluate_candidate(candidate: MigrationCandidate, rules: list[ExcludeRule]) -> tuple[bool, list[str]]:
	reasons: list[str] = []
	for rule in rules:
		excluded_vm_ids = _normalized_set(rule.vm_ids)
		excluded_host_ids = _normalized_set(rule.host_ids)

		if candidate.vm_id in excluded_vm_ids:
			reasons.append(f"rule={rule.rule_id}: vm={candidate.vm_id} is excluded from migration candidates")

		if candidate.source_host in excluded_host_ids:
			reasons.append(f"rule={rule.rule_id}: source_host={candidate.source_host} is excluded from migration candidates")

		if candidate.target_host in excluded_host_ids:
			reasons.append(f"rule={rule.rule_id}: target_host={candidate.target_host} is excluded from migration candidates")

	return len(reasons) == 0, reasons


def filter_candidates(
	candidates: list[MigrationCandidate],
	exclude_rules: list[ExcludeRule],
) -> tuple[list[MigrationCandidate], list[MigrationCandidate]]:
	if not exclude_rules:
		return candidates, []

	allowed: list[MigrationCandidate] = []
	rejected: list[MigrationCandidate] = []

	for candidate in candidates:
		is_allowed, reasons = evaluate_candidate(candidate, exclude_rules)
		evaluated_candidate = candidate.model_copy(
			update={"policy_reasons": [*candidate.policy_reasons, *reasons]}
		)
		if is_allowed:
			allowed.append(evaluated_candidate)
		else:
			rejected.append(evaluated_candidate)

	return allowed, rejected
