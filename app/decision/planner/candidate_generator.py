from __future__ import annotations

from collections import defaultdict

from app import config
from app.models.schemas import HostMetricSnapshot, MigrationCandidate, VMHostAffinityRule, VMInventory, VMAffinityRule
from app.decision.constraints.affinity_policy import filter_candidates


def _host_metric_map(host_metrics: list[HostMetricSnapshot]) -> dict[str, HostMetricSnapshot]:
	return {metric.host: metric for metric in host_metrics}


def _weighted_pressure(cpu_usage: float, ram_usage: float, swap_usage: float) -> float:
	return float(
		(config.CPU_WEIGHT * cpu_usage)
		+ (config.RAM_WEIGHT * ram_usage)
		+ (config.SWAP_WEIGHT * swap_usage)
	)


def _usage_delta_percent(vm_allocated: float, host_allocated: float) -> float:
	if host_allocated <= 0:
		return 0.0
	return float((vm_allocated / host_allocated) * 100.0)


def _project_source_usage(metric: HostMetricSnapshot, vm: VMInventory) -> tuple[float, float, float]:
	cpu_delta = _usage_delta_percent(vm.cpu, metric.cpu_allocated)
	ram_delta = _usage_delta_percent(vm.ram, metric.ram_allocated)
	swap_delta = _usage_delta_percent(vm.swap, metric.swap_allocated)
	return (
		max(0.0, float(metric.cpu) - cpu_delta),
		max(0.0, float(metric.ram) - ram_delta),
		max(0.0, float(metric.swap) - swap_delta),
	)


def _project_target_usage(metric: HostMetricSnapshot, vm: VMInventory) -> tuple[float, float, float]:
	cpu_delta = _usage_delta_percent(vm.cpu, metric.cpu_allocated)
	ram_delta = _usage_delta_percent(vm.ram, metric.ram_allocated)
	swap_delta = _usage_delta_percent(vm.swap, metric.swap_allocated)
	return (
		float(metric.cpu) + cpu_delta,
		float(metric.ram) + ram_delta,
		float(metric.swap) + swap_delta,
	)


def _target_within_thresholds(cpu_usage: float, ram_usage: float, swap_usage: float) -> bool:
	return (
		cpu_usage <= config.MIGRATION_TARGET_MAX_CPU_USAGE
		and ram_usage <= config.MIGRATION_TARGET_MAX_RAM_USAGE
		and swap_usage <= config.MIGRATION_TARGET_MAX_SWAP_USAGE
	)


def build_candidate_pairs(
	host_metrics: list[HostMetricSnapshot],
	vm_inventory: list[VMInventory],
	vm_host_rules: list[VMHostAffinityRule],
	vm_vm_rules: list[VMAffinityRule],
) -> list[MigrationCandidate]:
	metric_map = _host_metric_map(host_metrics)
	source_host_names = {vm.current_host for vm in vm_inventory}

	if not metric_map or not vm_inventory:
		return []

	host_to_vms: dict[str, list[VMInventory]] = defaultdict(list)
	for vm in vm_inventory:
		host_to_vms[vm.current_host].append(vm)

	if not metric_map:
		return []

	raw_candidates: list[MigrationCandidate] = []
	for source_host in source_host_names:
		source_metric = metric_map.get(source_host)
		if source_metric is None:
			continue
		source_pressure = _weighted_pressure(source_metric.cpu, source_metric.ram, source_metric.swap)
		for vm in host_to_vms.get(source_host, []):
			source_cpu_after, source_ram_after, source_swap_after = _project_source_usage(source_metric, vm)
			source_projected_pressure = _weighted_pressure(source_cpu_after, source_ram_after, source_swap_after)
			for target_host in metric_map:
				if target_host == source_host:
					continue
				target_metric = metric_map.get(target_host)
				if target_metric is None:
					continue

				target_cpu_after, target_ram_after, target_swap_after = _project_target_usage(target_metric, vm)
				if not _target_within_thresholds(target_cpu_after, target_ram_after, target_swap_after):
					continue

				target_pressure = _weighted_pressure(target_metric.cpu, target_metric.ram, target_metric.swap)
				target_projected_pressure = _weighted_pressure(target_cpu_after, target_ram_after, target_swap_after)
				source_relief = source_pressure - source_projected_pressure
				target_increase = target_projected_pressure - target_pressure
				net_benefit = source_relief - target_increase
				if net_benefit < config.MIGRATION_MIN_NET_BENEFIT:
					continue

				raw_candidates.append(
					MigrationCandidate(
						vm_id=vm.vm_id,
						source_host=source_host,
						target_host=target_host,
						migration_cost=0,
						policy_reasons=[],
						score_breakdown={
							"source_pressure": source_pressure,
							"target_pressure": target_pressure,
							"source_projected_pressure": source_projected_pressure,
							"target_projected_pressure": target_projected_pressure,
							"source_cpu_after": source_cpu_after,
							"source_ram_after": source_ram_after,
							"source_swap_after": source_swap_after,
							"target_cpu_after": target_cpu_after,
							"target_ram_after": target_ram_after,
							"target_swap_after": target_swap_after,
							"source_relief": source_relief,
							"target_increase": target_increase,
							"net_benefit": net_benefit,
						},
					)
				)

	allowed_candidates, _ = filter_candidates(raw_candidates, vm_inventory, vm_host_rules, vm_vm_rules)
	return allowed_candidates
