from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Any

from openstack import connection

from app import config
from app.models.schemas import HostInventory, HostMetricSnapshot, VMInventory, VMMetricSnapshot
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _build_conn() -> connection.Connection | None:
	if not all(
		[
			config.OPENSTACK_AUTH_URL,
			config.OPENSTACK_USERNAME,
			config.OPENSTACK_PASSWORD,
			config.OPENSTACK_PROJECT_NAME,
		]
	):
		logger.warning("OpenStack credentials are not fully configured; inventory datasource disabled")
		return None

	logger.debug(
		"Initializing OpenStack inventory connection auth_url=%s project_name=%s region_name=%s",
		config.OPENSTACK_AUTH_URL,
		config.OPENSTACK_PROJECT_NAME,
		config.OPENSTACK_REGION_NAME,
	)
	return connection.Connection(
		auth_url=config.OPENSTACK_AUTH_URL,
		username=config.OPENSTACK_USERNAME,
		password=config.OPENSTACK_PASSWORD,
		project_name=config.OPENSTACK_PROJECT_NAME,
		user_domain_name=config.OPENSTACK_USER_DOMAIN_NAME,
		project_domain_name=config.OPENSTACK_PROJECT_DOMAIN_NAME,
		region_name=config.OPENSTACK_REGION_NAME,
	)

# Get hostname of the server
def _server_host(server: Any) -> str:
	for attribute_name in ("OS-EXT-SRV-ATTR:host", "hypervisor_hostname", "host", "compute_host"):
		value = getattr(server, attribute_name, None)
		if value:
			return str(value)
	return "unknown"


# Get metadata dictionary from the server, ensuring all keys and values are strings
def _server_metadata(server: Any) -> dict[str, str]:
	metadata = getattr(server, "metadata", None) or {}
	return {str(key): str(value) for key, value in metadata.items()}


def _server_instance_name(server: Any) -> str:
	for attribute_name in ("OS-EXT-SRV-ATTR:instance_name", "instance_name"):
		value = getattr(server, attribute_name, None)
		if value:
			return str(value)
	return ""


def _host_aliases(host: HostInventory) -> set[str]:
	aliases = {host.host}
	for key in ("hostname", "hypervisor_hostname", "host_ip", "service_host", "host"):
		value = host.metadata.get(key)
		if value:
			aliases.add(str(value))

	normalized_aliases: set[str] = set()
	for alias in aliases:
		alias_text = str(alias).strip()
		if not alias_text:
			continue
		normalized_aliases.add(alias_text)
		normalized_aliases.add(alias_text.split(":")[0])
	return normalized_aliases


def _normalize_state(value: str | None) -> str:
	return str(value or "").strip().lower()


def _host_inventory_enabled(host: HostInventory | None) -> bool:
	if host is None:
		return True

	state = _normalize_state(host.state or host.metadata.get("state"))
	status = _normalize_state(host.metadata.get("status"))
	service_state = _normalize_state(host.metadata.get("service_state"))
	service_status = _normalize_state(host.metadata.get("service_status"))
	forced_down = _normalize_state(host.metadata.get("forced_down"))

	if status == "disabled" or service_status == "disabled":
		return False
	if state == "down" or service_state == "down":
		return False
	if forced_down in {"true", "1", "yes"}:
		return False
	return True


def _is_unknown_host(host_name: str) -> bool:
	return not host_name or host_name.strip().lower() == "unknown"


def _server_flavor(server: Any) -> dict[str, Any]:
	flavor = getattr(server, "flavor", None) or {}
	if isinstance(flavor, dict):
		return flavor
	return {
		"vcpus": getattr(flavor, "vcpus", 0),
		"ram": getattr(flavor, "ram", 0),
		"swap": getattr(flavor, "swap", 0),
	}


@dataclass(slots=True)
class OpenStackInventoryDatasource:
	connection: connection.Connection | None = None

	def __post_init__(self) -> None:
		if self.connection is None:
			self.connection = _build_conn()
		if self.connection is None:
			logger.debug("OpenStackInventoryDatasource initialized without active connection")
		else:
			logger.debug("OpenStackInventoryDatasource initialized successfully")

	def is_available(self) -> bool:
		return self.connection is not None

	def list_enabled_host_aliases(self) -> set[str]:
		"""Return aliases for hosts that are eligible for prediction/planning."""
		enabled_aliases: set[str] = set()
		for host in self.list_hosts():
			if _is_unknown_host(host.host) or not _host_inventory_enabled(host):
				continue
			enabled_aliases.update(_host_aliases(host))
		return enabled_aliases

	def _compute_services_by_host(self) -> dict[str, dict[str, str]]:
		if self.connection is None:
			return {}

		services_by_host: dict[str, dict[str, str]] = {}
		try:
			services = self.connection.compute.services(binary="nova-compute")
		except Exception as exc:
			logger.warning("Unable to fetch nova-compute service states: %s", exc)
			return {}

		for service in services:
			host = str(getattr(service, "host", "") or "")
			if not host:
				continue
			service_metadata = {
				"service_state": str(getattr(service, "state", "") or ""),
				"service_status": str(getattr(service, "status", "") or ""),
				"disabled_reason": str(getattr(service, "disabled_reason", "") or ""),
				"forced_down": str(getattr(service, "forced_down", "") or ""),
			}
			for alias in {host, host.split(":")[0], host.split(".")[0]}:
				if alias:
					services_by_host.setdefault(alias, service_metadata)
		return services_by_host

	def list_hosts(self) -> list[HostInventory]:
		if self.connection is None:
			logger.debug("list_hosts skipped: OpenStack connection is unavailable")
			return []

		logger.debug("Building host inventory from OpenStack hypervisors")
		hosts: list[HostInventory] = []
		compute_services_by_host = self._compute_services_by_host()
		for hypervisor in self.connection.compute.hypervisors():
			host_name = getattr(hypervisor, "name", None) or getattr(hypervisor, "hypervisor_hostname", None)
			if not host_name:
				logger.debug("Skipping hypervisor without resolvable name: %s", hypervisor)
				continue
			host_state = str(getattr(hypervisor, "state", ""))
			host_status = str(getattr(hypervisor, "status", ""))
			host_ip = str(getattr(hypervisor, "host_ip", "") or "")
			host_name_text = str(host_name)
			service_metadata = (
				compute_services_by_host.get(host_name_text)
				or compute_services_by_host.get(host_name_text.split(":")[0])
				or compute_services_by_host.get(host_name_text.split(".")[0])
				or {}
			)
			hosts.append(
				HostInventory(
					host=host_name_text,
					state=host_state,
					metadata={
						"state": host_state,
						"status": host_status,
						"hostname": host_name_text,
						"hypervisor_hostname": host_name_text,
						"host_ip": host_ip,
						**service_metadata,
					},
				)
			)
			logger.debug(
				"Host inventory item built host=%s state=%s status=%s",
				host_name,
				host_state,
				host_status,
			)

		logger.debug("Completed host inventory build with %d hosts", len(hosts))
		return hosts

	def list_vms(self) -> list[VMInventory]:
		if self.connection is None:
			logger.debug("list_vms skipped: OpenStack connection is unavailable")
			return []

		logger.debug("Building VM inventory from OpenStack servers")
		vms: list[VMInventory] = []
		for server in self.connection.compute.servers(details=True, all_projects=True):
			current_host = _server_host(server)
			flavor = _server_flavor(server)
			metadata = _server_metadata(server)
			instance_name = _server_instance_name(server)
			if instance_name:
				metadata.setdefault("instance_name", instance_name)
			server_id = str(getattr(server, "id", ""))
			server_name = getattr(server, "name", None)
			cpu = float(flavor.get("vcpus", 0) or 0)
			ram = float(flavor.get("ram", 0) or 0)
			swap = float(flavor.get("swap", 0) or 0)
			vms.append(
				VMInventory(
					vm_id=server_id,
					name=server_name,
					current_host=current_host,
					cpu=cpu,
					ram=ram,
					swap=swap,
					metadata=metadata,
				)
			)
			logger.debug(
				"VM inventory item built vm_id=%s instance_name=%s name=%s host=%s cpu=%s ram=%s swap=%s metadata_keys=%s",
				server_id,
				instance_name,
				server_name,
				current_host,
				cpu,
				ram,
				swap,
				sorted(metadata.keys()),
			)

		logger.debug("Completed VM inventory build with %d VMs", len(vms))
		return vms

	def build_host_inventory(self) -> list[HostInventory]:
		hosts = self.list_hosts()
		logger.debug("build_host_inventory returned %d hosts", len(hosts))
		return hosts

	def build_vm_inventory(self) -> list[VMInventory]:
		vms = self.list_vms()
		logger.debug("build_vm_inventory returned %d VMs", len(vms))
		return vms

	def build_inventory(
		self,
		host_metrics: list[HostMetricSnapshot] | None = None,
		vm_metrics: list[VMMetricSnapshot] | None = None,
	) -> list[dict[str, Any]]:
		"""Build a single inventory payload combining host and VM information.

		The payload shape is designed for JSON serialization:
		[
		  {
		    "hostname": "compute1",
		    "cpu_allocated": 24.0,
		    "cpu_usage": 62.5,
		    "memory_allocated": 49152.0,
		    "memory_usage": 75.1,
		    "swap_allocated": 0.0,
		    "swap_usage": 12.0,
		    "vm": [...]
		  }
		]
		"""
		hosts = self.list_hosts()
		vms = self.list_vms()
		host_metrics = host_metrics or []
		vm_metrics = vm_metrics or []
		if logger.isEnabledFor(10):
			metric_vm_ids = sorted(metric.uuid for metric in vm_metrics)
			logger.debug(
				"VM metrics fetched count=%d sample_vm_ids=%s",
				len(metric_vm_ids),
				metric_vm_ids[:10],
			)

		host_alias_to_canonical: dict[str, str] = {}
		for host in hosts:
			if _is_unknown_host(host.host):
				continue
			for alias in _host_aliases(host):
				host_alias_to_canonical.setdefault(alias, host.host)
		hosts_by_name = {host.host: host for host in hosts if not _is_unknown_host(host.host)}

		metrics_by_host: dict[str, HostMetricSnapshot] = {}
		unmapped_metric_hosts: set[str] = set()
		for metric in host_metrics:
			canonical_host = host_alias_to_canonical.get(metric.host)
			if canonical_host is None:
				canonical_host = metric.host
				unmapped_metric_hosts.add(metric.host)
			if _is_unknown_host(canonical_host):
				continue
			metrics_by_host[canonical_host] = HostMetricSnapshot(
				host=canonical_host,
				cpu=metric.cpu,
				ram=metric.ram,
				swap=metric.swap,
				running_vm=metric.running_vm,
				cpu_allocated=metric.cpu_allocated,
				ram_allocated=metric.ram_allocated,
				swap_allocated=metric.swap_allocated,
			)
		metrics_by_vm = {metric.uuid: metric for metric in vm_metrics}
		vm_by_host: dict[str, list[VMInventory]] = defaultdict(list)
		for vm in vms:
			if _is_unknown_host(vm.current_host):
				continue
			canonical_host = host_alias_to_canonical.get(vm.current_host, vm.current_host)
			vm_by_host[canonical_host].append(vm)

		if unmapped_metric_hosts:
			logger.debug(
				"Unmapped host metric keys from Prometheus: %s",
				sorted(unmapped_metric_hosts),
			)

		host_names = {host.host for host in hosts if not _is_unknown_host(host.host)}
		host_names.update(metrics_by_host.keys())
		host_names.update(vm_by_host.keys())

		combined_inventory: list[dict[str, Any]] = []
		matched_vm_usage = 0
		unmatched_vm_usage = 0
		unmatched_examples: list[dict[str, Any]] = []
		for host_name in sorted(host_names):
			if _is_unknown_host(host_name):
				continue
			host_vms = vm_by_host.get(host_name, [])
			metric = metrics_by_host.get(host_name)
			metrics_available = metric is not None
			host_enabled = _host_inventory_enabled(hosts_by_name.get(host_name))
			exclude_reasons = []
			if not metrics_available:
				exclude_reasons.append("missing_metrics")
			if not host_enabled:
				exclude_reasons.append("host_disabled")
			cpu_allocated = float(metric.cpu_allocated) if metric else 0.0
			memory_allocated = float(metric.ram_allocated) if metric else 0.0
			swap_allocated = float(metric.swap_allocated) if metric else 0.0
			vm_payloads: list[dict[str, Any]] = []
			for vm in host_vms:
				instance_name = str(vm.metadata.get("instance_name", ""))
				metric_lookup_candidates = [instance_name, vm.vm_id]
				vm_metric = None
				for candidate in metric_lookup_candidates:
					if candidate and candidate in metrics_by_vm:
						vm_metric = metrics_by_vm[candidate]
						break

				if vm_metric is not None:
					matched_vm_usage += 1
				else:
					unmatched_vm_usage += 1
					if len(unmatched_examples) < 10:
						unmatched_examples.append(
							{
								"vm_id": vm.vm_id,
								"instance_name": instance_name,
								"vm_name": vm.name,
								"host": vm.current_host,
								"metric_lookup_candidates": metric_lookup_candidates,
							}
						)

				vm_payloads.append(
					{
						"uuid": vm.vm_id,
						"instance_name": instance_name,
						"vcpu_allocated": float(vm.cpu),
						"vcpu_usage": float(vm_metric.cpu) if vm_metric else "",
						"memory_allocated": float(vm.ram),
						"memory_usage": float(vm_metric.ram) if vm_metric else "",
					},
				)

			combined_inventory.append(
				{
					"hostname": host_name,
					"cpu_allocated": cpu_allocated,
					"cpu_usage": float(metric.cpu) if metric else "",
					"memory_allocated": memory_allocated,
					"memory_usage": float(metric.ram) if metric else "",
					"swap_allocated": swap_allocated,
					"swap_usage": float(metric.swap) if metric else "",
					"metrics_available": metrics_available,
					"host_enabled": host_enabled,
					"excluded_from_planning": bool(exclude_reasons),
					"exclude_reason": ",".join(exclude_reasons),
					"vm": vm_payloads,
				}
			)

		logger.debug("build_inventory returned %d hosts", len(combined_inventory))
		logger.debug(
			"VM usage mapping summary matched=%d unmatched=%d unmatched_examples=%s",
			matched_vm_usage,
			unmatched_vm_usage,
			unmatched_examples,
		)
		return combined_inventory

	@staticmethod
	def extract_vm_inventory(combined_inventory: list[dict[str, Any]]) -> list[VMInventory]:
		"""Convert combined inventory payload back to VMInventory for planner compatibility."""
		vms: list[VMInventory] = []
		for host_payload in combined_inventory:
			host_name = str(host_payload.get("hostname", "unknown"))
			for vm_payload in host_payload.get("vm", []):
				vms.append(
					VMInventory(
						vm_id=str(vm_payload.get("uuid", "")),
						name=None,
						current_host=host_name,
						cpu=float(vm_payload.get("cpu_allocated", 0) or 0),
						ram=float(vm_payload.get("memory_allocated", 0) or 0),
						swap=float(vm_payload.get("swap_allocated", 0) or 0),
						metadata={},
					)
				)
		return vms
