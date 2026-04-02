import os
from dotenv import load_dotenv

load_dotenv()

PROMETHEUS_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://localhost:9090")
PROMETHEUS_USERNAME = os.getenv("PROMETHEUS_USERNAME", "admin")
PROMETHEUS_PASSWORD = os.getenv("PROMETHEUS_PASSWORD", "admin")
PROMETHEUS_TIMEOUT_SECONDS = int(os.getenv("PROMETHEUS_TIMEOUT_SECONDS", "20"))

SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "5"))
CHECK_EVENT_LOOKBACK_MINUTES = int(os.getenv("CHECK_EVENT_LOOKBACK_MINUTES", "5"))
HISTORY_LOOKBACK_MINUTES = int(os.getenv("HISTORY_LOOKBACK_MINUTES", "30"))
PREDICTION_HORIZON_MINUTES = int(os.getenv("PREDICTION_HORIZON_MINUTES", "5"))
PREDICTION_STEP_SECONDS = int(os.getenv("PREDICTION_STEP_SECONDS", "15"))

CLUSTER_IMBALANCE_THRESHOLD = float(os.getenv("CLUSTER_IMBALANCE_THRESHOLD", "0.15"))
UNBALANCED_TOP_K = int(os.getenv("UNBALANCED_TOP_K", "5"))

CPU_WEIGHT = float(os.getenv("CPU_WEIGHT", "0.5"))
RAM_WEIGHT = float(os.getenv("RAM_WEIGHT", "0.3"))
SWAP_WEIGHT = float(os.getenv("SWAP_WEIGHT", "0.2"))

CHRONOS_MODEL_NAME = os.getenv("CHRONOS_MODEL_NAME", "amazon/chronos-2")
CHRONOS_DEVICE = os.getenv("CHRONOS_DEVICE", "cpu")

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