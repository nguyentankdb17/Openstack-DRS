from __future__ import annotations

from collections.abc import Iterable

from app.models.schemas import HostMetricSnapshot, MigrationCandidate, VMInventory


def _normalized_load(metric: HostMetricSnapshot | None) -> float:
	if metric is None:
		return 0.0
	return max(0.0, min(1.0, float((metric.cpu + metric.ram + metric.swap + metric.running_vm) / 400.0)))


def _vm_size_score(vm: VMInventory | None) -> float:
	if vm is None:
		return 0.0
	return max(0.0, min(1.0, float((vm.cpu + vm.ram + vm.swap) / 300.0)))


def score_migration_candidate(
	candidate: MigrationCandidate,
	host_metrics: Iterable[HostMetricSnapshot],
	vm_inventory: Iterable[VMInventory],
) -> MigrationCandidate:
	host_metric_map = {metric.host: metric for metric in host_metrics}
	vm_map = {vm.vm_id: vm for vm in vm_inventory}
	vm = vm_map.get(candidate.vm_id)
	source_load = _normalized_load(host_metric_map.get(candidate.source_host))
	target_load = _normalized_load(host_metric_map.get(candidate.target_host))
	vm_size = _vm_size_score(vm)

	cost = (0.55 * target_load) + (0.3 * vm_size) + (0.15 * (1.0 - source_load))
	breakdown = dict(candidate.score_breakdown)
	net_benefit = float(breakdown.get("net_benefit", 0.0))
	breakdown.update(
		{
			"source_load": source_load,
			"target_load": target_load,
			"vm_size": vm_size,
			"migration_cost": cost,
			"ranking_score": net_benefit,
		}
	)
	return candidate.model_copy(update={"migration_cost": cost, "score_breakdown": breakdown})


def rank_candidates(
	candidates: list[MigrationCandidate],
	host_metrics: Iterable[HostMetricSnapshot],
	vm_inventory: Iterable[VMInventory],
) -> list[MigrationCandidate]:
	scored_candidates = [score_migration_candidate(candidate, host_metrics, vm_inventory) for candidate in candidates]
	return sorted(
		scored_candidates,
		key=lambda candidate: (
			-float(candidate.score_breakdown.get("net_benefit", 0.0)),
			candidate.migration_cost,
		),
	)
