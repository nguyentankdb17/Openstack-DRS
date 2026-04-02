from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


_BASE = Path(__file__).resolve().parent


def _load_module(filename: str, module_name: str) -> ModuleType:
    module_path = _BASE / filename
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_openstack_mod = _load_module("openstack-event.py", "collector.openstack_event")
_prometheus_mod = _load_module("prometheus-collector.py", "collector.prometheus_collector")

has_recent_vm_events = _openstack_mod.has_recent_vm_events
collect_host_metric_averages = _prometheus_mod.collect_host_metric_averages
collect_host_metric_history = _prometheus_mod.collect_host_metric_history
