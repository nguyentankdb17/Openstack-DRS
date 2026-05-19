import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: str = "false") -> bool:
    value = os.getenv(key, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int_tuple(key: str, default: str = "64,32") -> tuple[int, ...]:
    raw_value = os.getenv(key, default)
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    values = tuple(int(part) for part in parts if int(part) > 0)
    return values or (64, 32)

PROMETHEUS_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://localhost:9090")
PROMETHEUS_USERNAME = os.getenv("PROMETHEUS_USERNAME", "admin")
PROMETHEUS_PASSWORD = os.getenv("PROMETHEUS_PASSWORD", "admin")
PROMETHEUS_TIMEOUT_SECONDS = int(os.getenv("PROMETHEUS_TIMEOUT_SECONDS", "20"))

SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))
SCHEDULER_START_MODE = os.getenv("SCHEDULER_START_MODE", "lazy").strip().lower()
SCHEDULER_STARTUP_DELAY_SECONDS = int(os.getenv("SCHEDULER_STARTUP_DELAY_SECONDS", "0"))
SCHEDULER_MISFIRE_GRACE_SECONDS = int(os.getenv("SCHEDULER_MISFIRE_GRACE_SECONDS", "900"))
CHECK_EVENT_LOOKBACK_MINUTES = int(os.getenv("CHECK_EVENT_LOOKBACK_MINUTES", "5"))
HISTORY_LOOKBACK_MINUTES = int(os.getenv("HISTORY_LOOKBACK_MINUTES", "180"))
PREDICTION_HORIZON_MINUTES = int(os.getenv("PREDICTION_HORIZON_MINUTES", "5"))
PREDICTION_STEP_SECONDS = int(os.getenv("PREDICTION_STEP_SECONDS", "15"))

CLUSTER_IMBALANCE_THRESHOLD = float(os.getenv("CLUSTER_IMBALANCE_THRESHOLD", "0.15"))

CPU_WEIGHT = float(os.getenv("CPU_WEIGHT", "0.5"))
RAM_WEIGHT = float(os.getenv("RAM_WEIGHT", "0.3"))
SWAP_WEIGHT = float(os.getenv("SWAP_WEIGHT", "0.2"))

MIGRATION_TARGET_MAX_CPU_USAGE = float(os.getenv("MIGRATION_TARGET_MAX_CPU_USAGE", "85"))
MIGRATION_TARGET_MAX_RAM_USAGE = float(os.getenv("MIGRATION_TARGET_MAX_RAM_USAGE", "85"))
MIGRATION_TARGET_MAX_SWAP_USAGE = float(os.getenv("MIGRATION_TARGET_MAX_SWAP_USAGE", "80"))
MIGRATION_MIN_NET_BENEFIT = float(os.getenv("MIGRATION_MIN_NET_BENEFIT", "0.1"))
MIGRATION_MIN_IMBALANCE_REDUCTION = float(os.getenv("MIGRATION_MIN_IMBALANCE_REDUCTION", "0.01"))
MAX_MIGRATIONS_PER_CYCLE = int(os.getenv("MAX_MIGRATIONS_PER_CYCLE", "1"))

# Alertmanager webhook integration
# ALERTMANAGER_WEBHOOK_TOKEN: shared secret sent in X-Webhook-Token or Authorization: Bearer header.
#   Leave empty to disable token auth (not recommended for production).
# ALERTMANAGER_TRIGGER_ALERTS: comma-separated alert names that trigger the decision flow.
#   Leave empty to trigger on ANY firing alert.
ALERTMANAGER_WEBHOOK_TOKEN = os.getenv("ALERTMANAGER_WEBHOOK_TOKEN", "")
ALERTMANAGER_TRIGGER_ALERTS = os.getenv("ALERTMANAGER_TRIGGER_ALERTS", "")

# Migration approval mode: "manual" (default) or "auto"
# - manual: system builds a plan but waits for human approval via POST /api/v1/plan/approve
# - auto:   system executes migrations immediately after planning
APPROVAL_MODE = os.getenv("APPROVAL_MODE", "manual").strip().lower()
CPU_ALLOCATION_RATIO = float(os.getenv("CPU_ALLOCATION_RATIO", "4"))
RAM_ALLOCATION_RATIO = float(os.getenv("RAM_ALLOCATION_RATIO", "1"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

CHRONOS_MODEL_NAME = os.getenv("CHRONOS_MODEL_NAME", "amazon/chronos-2")
CHRONOS_DEVICE = os.getenv("CHRONOS_DEVICE", "cpu")
CHRONOS_FINETUNED_MODEL_PATH = os.getenv("CHRONOS_FINETUNED_MODEL_PATH", "")

OPENSTACK_AUTH_URL = os.getenv("OPENSTACK_AUTH_URL", "")
OPENSTACK_USERNAME = os.getenv("OPENSTACK_USERNAME", "")
OPENSTACK_PASSWORD = os.getenv("OPENSTACK_PASSWORD", "")
OPENSTACK_PROJECT_NAME = os.getenv("OPENSTACK_PROJECT_NAME", "")
OPENSTACK_USER_DOMAIN_NAME = os.getenv("OPENSTACK_USER_DOMAIN_NAME", "Default")
OPENSTACK_PROJECT_DOMAIN_NAME = os.getenv("OPENSTACK_PROJECT_DOMAIN_NAME", "Default")
OPENSTACK_REGION_NAME = os.getenv("OPENSTACK_REGION_NAME", "RegionOne")

NOVA_DB_HOST = os.getenv("NOVA_DB_HOST", "")
NOVA_DB_PORT = int(os.getenv("NOVA_DB_PORT", "3306"))
NOVA_DB_NAME = os.getenv("NOVA_DB_NAME", "nova")
NOVA_DB_USER = os.getenv("NOVA_DB_USER", "")
NOVA_DB_PASSWORD = os.getenv("NOVA_DB_PASSWORD", "")
NOVA_DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("NOVA_DB_CONNECT_TIMEOUT_SECONDS", "5"))

# The window placeholder is replaced by collector methods.
HOST_CPU_QUERY = os.getenv(
    "HOST_CPU_QUERY",
    '100 - avg by (instance) (irate(node_cpu_seconds_total{job="compute-node-exporter",mode="idle"}[{window}])) * 100',
)

HOST_MEM_QUERY = os.getenv(
    "HOST_MEM_QUERY",
    '((node_memory_MemTotal_bytes{job="compute-node-exporter"} - (node_memory_MemFree_bytes{job="compute-node-exporter"} + node_memory_Buffers_bytes{job="compute-node-exporter"} + node_memory_Cached_bytes{job="compute-node-exporter"})) / node_memory_MemTotal_bytes{job="compute-node-exporter"}) * 100',
)

HOST_SWAP_QUERY = os.getenv(
    "HOST_SWAP_QUERY",
    '((node_memory_SwapTotal_bytes{job="compute-node-exporter"} - node_memory_SwapFree_bytes{job="compute-node-exporter"}) / clamp_min(node_memory_SwapTotal_bytes{job="compute-node-exporter"}, 1)) * 100',
)

HOST_RUNNING_VM_QUERY = os.getenv(
    "HOST_RUNNING_VM_QUERY",
    'count by (instance) (libvirt_domain_info_state{job="libvirt-exporter"} == 1)',
)

HOST_TOTAL_CPU_QUERY = os.getenv(
    "HOST_TOTAL_CPU_QUERY",
    'count by (instance) (node_cpu_seconds_total{job="compute-node-exporter",mode="idle"})',
)

HOST_TOTAL_MEM_QUERY = os.getenv(
    "HOST_TOTAL_MEM_QUERY",
    'node_memory_MemTotal_bytes{job="compute-node-exporter"} / 1024 / 1024',
)

HOST_TOTAL_SWAP_QUERY = os.getenv(
    "HOST_TOTAL_SWAP_QUERY",
    'node_memory_SwapTotal_bytes{job="compute-node-exporter"} / 1024 / 1024',
)

VM_CPU_QUERY = os.getenv(
    "VM_CPU_QUERY",
    'rate(libvirt_domain_info_cpu_time_seconds_total{job="libvirt-exporter"}[{window}]) * 100',
)

VM_MEM_QUERY = os.getenv(
    "VM_MEM_QUERY",
    '((libvirt_domain_info_maximum_memory_bytes{job="libvirt-exporter"} - avg_over_time(libvirt_domain_memory_stats_unused_bytes{job="libvirt-exporter"}[{window}]))/ libvirt_domain_info_maximum_memory_bytes{job="libvirt-exporter"}) * 100',
)
