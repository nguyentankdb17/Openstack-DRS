from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app import config
from app.scoring.cluster_imbalance import compute_cluster_imbalance
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _to_float(value: Any) -> float:
	if value in (None, ""):
		return 0.0
	try:
		return float(value)
	except (TypeError, ValueError):
		return 0.0


def _inventory_to_metrics_df(inventory: list[dict[str, Any]]) -> pd.DataFrame:
	rows: list[dict[str, Any]] = []
	for host_payload in inventory:
		rows.append(
			{
				"host": str(host_payload.get("hostname", "")),
				"cpu": _to_float(host_payload.get("cpu_usage")),
				"ram": _to_float(host_payload.get("memory_usage")),
				"swap": _to_float(host_payload.get("swap_usage")),
			}
		)
	return pd.DataFrame(rows)


def compute_inventory_imbalance(inventory: list[dict[str, Any]]) -> float:
	metrics_df = _inventory_to_metrics_df(inventory)
	if metrics_df.empty:
		logger.debug("compute_inventory_imbalance: empty inventory payload")
		return 0.0
	imbalance = float(compute_cluster_imbalance(metrics_df))
	logger.debug(
		"compute_inventory_imbalance: hosts=%d imbalance=%.6f",
		len(inventory),
		imbalance,
	)
	return imbalance


def _find_host(inventory: list[dict[str, Any]], host_name: str) -> dict[str, Any] | None:
	for host_payload in inventory:
		if str(host_payload.get("hostname", "")) == host_name:
			return host_payload
	return None


def _estimate_vm_usage_percent(vm: dict[str, Any], host_payload: dict[str, Any], *, usage_key: str, allocated_key: str) -> float:
	direct_usage = _to_float(vm.get(usage_key))
	if direct_usage > 0:
		return direct_usage

	host_usage = _to_float(host_payload.get("cpu_usage" if usage_key == "vcpu_usage" else "memory_usage"))
	return max(0.0, host_usage)


def _usage_delta_percent(
	*,
	vm_usage_percent: float,
	vm_allocated: float,
	host_allocated: float,
	allocation_ratio: float,
) -> float:
	ratio = allocation_ratio if allocation_ratio > 0 else 1.0
	effective_capacity = max(0.0, host_allocated * ratio)
	if effective_capacity <= 0:
		return 0.0
	allocation_share = max(0.0, vm_allocated / effective_capacity)
	return max(0.0, vm_usage_percent * allocation_share)


@dataclass(slots=True)
class MigrationSimulationResult:
	cluster_imbalance: float
	inventory: list[dict[str, Any]]


def simulate_migration(
	inventory: list[dict[str, Any]],
	vm_id: str,
	source_host: str,
	target_host: str,
) -> MigrationSimulationResult | None:
	if source_host == target_host:
		logger.debug(
			"simulate_migration skipped: source and target are the same host=%s vm_id=%s",
			source_host,
			vm_id,
		)
		return None

	new_inventory = deepcopy(inventory)
	source_payload = _find_host(new_inventory, source_host)
	target_payload = _find_host(new_inventory, target_host)
	if source_payload is None or target_payload is None:
		logger.debug(
			"simulate_migration skipped: host not found vm_id=%s source_host=%s target_host=%s",
			vm_id,
			source_host,
			target_host,
		)
		return None

	source_vms = source_payload.get("vm", [])
	vm_index = next((idx for idx, vm in enumerate(source_vms) if str(vm.get("uuid", "")) == vm_id), None)
	if vm_index is None:
		logger.debug(
			"simulate_migration skipped: vm not found on source vm_id=%s source_host=%s",
			vm_id,
			source_host,
		)
		return None

	vm_payload = source_vms.pop(vm_index)
	target_payload.setdefault("vm", []).append(vm_payload)

	vm_cpu_usage = _estimate_vm_usage_percent(vm_payload, source_payload, usage_key="vcpu_usage", allocated_key="vcpu_allocated")
	vm_memory_usage = _estimate_vm_usage_percent(vm_payload, source_payload, usage_key="memory_usage", allocated_key="memory_allocated")

	cpu_delta = _usage_delta_percent(
		vm_usage_percent=vm_cpu_usage,
		vm_allocated=_to_float(vm_payload.get("vcpu_allocated")),
		host_allocated=_to_float(source_payload.get("cpu_allocated")),
		allocation_ratio=float(config.CPU_ALLOCATION_RATIO),
	)
	memory_delta = _usage_delta_percent(
		vm_usage_percent=vm_memory_usage,
		vm_allocated=_to_float(vm_payload.get("memory_allocated")),
		host_allocated=_to_float(source_payload.get("memory_allocated")),
		allocation_ratio=float(config.RAM_ALLOCATION_RATIO),
	)

	source_payload["cpu_usage"] = max(0.0, _to_float(source_payload.get("cpu_usage")) - cpu_delta)
	target_payload["cpu_usage"] = _to_float(target_payload.get("cpu_usage")) + cpu_delta
	source_payload["memory_usage"] = max(0.0, _to_float(source_payload.get("memory_usage")) - memory_delta)
	target_payload["memory_usage"] = _to_float(target_payload.get("memory_usage")) + memory_delta

	source_payload["cpu_allocated"] = max(0.0, _to_float(source_payload.get("cpu_allocated")) - _to_float(vm_payload.get("vcpu_allocated")))
	target_payload["cpu_allocated"] = _to_float(target_payload.get("cpu_allocated")) + _to_float(vm_payload.get("vcpu_allocated"))
	source_payload["memory_allocated"] = max(0.0, _to_float(source_payload.get("memory_allocated")) - _to_float(vm_payload.get("memory_allocated")))
	target_payload["memory_allocated"] = _to_float(target_payload.get("memory_allocated")) + _to_float(vm_payload.get("memory_allocated"))

	logger.debug(
		"simulate_migration applied: vm_id=%s source=%s target=%s cpu_delta=%.6f memory_delta=%.6f cpu_ratio=%.2f ram_ratio=%.2f",
		vm_id,
		source_host,
		target_host,
		cpu_delta,
		memory_delta,
		float(config.CPU_ALLOCATION_RATIO),
		float(config.RAM_ALLOCATION_RATIO),
	)

	return MigrationSimulationResult(
		cluster_imbalance=compute_inventory_imbalance(new_inventory),
		inventory=new_inventory,
	)
