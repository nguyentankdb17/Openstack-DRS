import {
  Cycle,
  JobConfiguration,
  MigrationConstraint,
  JobStatus,
  CycleMetrics,
  MetricPoint,
} from "./types";

export const mockCycles: Cycle[] = [
  {
    id: 1,
    cycle_started_at: new Date("2025-04-09T14:30:00"),
    cycle_finished_at: new Date("2025-04-09T14:45:30"),
    trigger_source: "scheduler",
    status: "completed",
    current_cluster_imbalance: 0.65,
    predicted_cluster_imbalance: 0.28,
    threshold: 0.75,
    planned_candidates: [
      {
        vm_id: "vm-001",
        vm_name: "web-server-01",
        source_host: "compute-01",
        target_host: "compute-03",
        reason: "Host overload - CPU > 85%",
        estimated_duration: 45,
        cpu_cores: 4,
        memory_gb: 8,
      },
      {
        vm_id: "vm-002",
        vm_name: "db-replica-02",
        source_host: "compute-02",
        target_host: "compute-04",
        reason: "Memory pressure - RAM > 80%",
        estimated_duration: 120,
        cpu_cores: 8,
        memory_gb: 16,
      },
    ],
    executed_candidates: [
      {
        vm_id: "vm-001",
        vm_name: "web-server-01",
        source_host: "compute-01",
        target_host: "compute-03",
        reason: "Host overload - CPU > 85%",
        estimated_duration: 45,
        cpu_cores: 4,
        memory_gb: 8,
      },
    ],
    details: "Cluster rebalancing completed successfully",
    decision_payload: {
      algorithm_version: "2.1.0",
      optimization_score: 0.92,
      constraints_satisfied: true,
    },
    error_message: null,
    prediction_results: {},
    created_at: new Date("2025-04-09T14:30:00"),
  },
  {
    id: 2,
    cycle_started_at: new Date("2025-04-09T15:00:00"),
    cycle_finished_at: new Date("2025-04-09T15:12:15"),
    trigger_source: "manual",
    status: "completed",
    current_cluster_imbalance: 0.72,
    predicted_cluster_imbalance: 0.35,
    threshold: 0.75,
    planned_candidates: [
      {
        vm_id: "vm-003",
        vm_name: "cache-server-01",
        source_host: "compute-01",
        target_host: "compute-02",
        reason: "Rebalancing",
        estimated_duration: 30,
        cpu_cores: 2,
        memory_gb: 4,
      },
    ],
    executed_candidates: [
      {
        vm_id: "vm-003",
        vm_name: "cache-server-01",
        source_host: "compute-01",
        target_host: "compute-02",
        reason: "Rebalancing",
        estimated_duration: 30,
        cpu_cores: 2,
        memory_gb: 4,
      },
    ],
    details: "Manual rebalancing cycle",
    decision_payload: {
      algorithm_version: "2.1.0",
      optimization_score: 0.88,
      constraints_satisfied: true,
    },
    error_message: null,
    prediction_results: {},
    created_at: new Date("2025-04-09T15:00:00"),
  },
  {
    id: 3,
    cycle_started_at: new Date("2025-04-09T15:30:00"),
    cycle_finished_at: null,
    trigger_source: "scheduler",
    status: "running",
    current_cluster_imbalance: 0.78,
    predicted_cluster_imbalance: 0.42,
    threshold: 0.75,
    planned_candidates: [
      {
        vm_id: "vm-004",
        vm_name: "app-server-01",
        source_host: "compute-04",
        target_host: "compute-01",
        reason: "Host overload - CPU > 85%",
        estimated_duration: 60,
        cpu_cores: 4,
        memory_gb: 8,
      },
      {
        vm_id: "vm-005",
        vm_name: "worker-node-01",
        source_host: "compute-04",
        target_host: "compute-02",
        reason: "Host overload - CPU > 85%",
        estimated_duration: 75,
        cpu_cores: 2,
        memory_gb: 4,
      },
    ],
    executed_candidates: [
      {
        vm_id: "vm-004",
        vm_name: "app-server-01",
        source_host: "compute-04",
        target_host: "compute-01",
        reason: "Host overload - CPU > 85%",
        estimated_duration: 60,
        cpu_cores: 4,
        memory_gb: 8,
      },
    ],
    details: "Currently executing migrations",
    decision_payload: {
      algorithm_version: "2.1.0",
      optimization_score: 0.85,
      constraints_satisfied: true,
    },
    error_message: null,
    prediction_results: {},
    created_at: new Date("2025-04-09T15:30:00"),
  },
  {
    id: 4,
    cycle_started_at: new Date("2025-04-09T14:00:00"),
    cycle_finished_at: new Date("2025-04-09T14:08:00"),
    trigger_source: "threshold_breach",
    status: "failed",
    current_cluster_imbalance: 0.88,
    predicted_cluster_imbalance: null,
    threshold: 0.75,
    planned_candidates: [],
    executed_candidates: [],
    details: "Failed to acquire migration lock",
    decision_payload: {},
    error_message: "Timeout waiting for resource lock on compute-02",
    prediction_results: {},
    created_at: new Date("2025-04-09T14:00:00"),
  },
];

export const mockJobConfiguration: JobConfiguration = {
  scheduler_interval_minutes: 5,
  cluster_imbalance_threshold: 0.75,
  max_migration_per_cycle: 5,
  prometheus_base_url: "http://prometheus:9090",
  prometheus_username: "admin",
  prometheus_password: "admin",
  check_event_lookback_minutes: 5,
  history_lookback_minutes: 180,
  prediction_horizon_minutes: 5,
};

export const mockJobStatus: JobStatus = {
  id: "job-001",
  status: "running",
  last_cycle_id: 3,
  last_cycle_time: new Date("2025-04-09T15:30:00"),
  next_execution: new Date("2025-04-09T15:35:00"),
  error_message: undefined,
};

export const mockConstraints: MigrationConstraint[] = [
  {
    id: "avoid-db-targets",
    rule_name: "avoid-db-targets",
    name: "Avoid database hosts",
    rule_type: "vm_host",
    description: "Keep app VMs away from database hosts",
    enabled: true,
    vm_id: "vm-app-001",
    forbidden_hosts: ["compute-db-01", "compute-db-02"],
    created_at: new Date("2025-01-15T10:00:00"),
    updated_at: new Date("2025-04-08T14:00:00"),
  },
  {
    id: "separate-critical-vms",
    rule_name: "separate-critical-vms",
    name: "Separate critical VMs",
    rule_type: "vm_vm",
    description: "Keep critical workloads on different hosts",
    enabled: true,
    vm_ids: ["vm-api-001", "vm-api-002"],
    policy: "must_separate",
    created_at: new Date("2025-02-01T09:00:00"),
    updated_at: new Date("2025-03-20T11:00:00"),
  },
  {
    id: "exclude-maintenance",
    rule_name: "exclude-maintenance",
    name: "Exclude production database hosts",
    rule_type: "exclude",
    description: "Do not select VMs or hosts under maintenance",
    enabled: true,
    host_ids: ["compute-01"],
    created_at: new Date("2025-02-10T14:30:00"),
    updated_at: new Date("2025-04-01T16:00:00"),
  },
];

// Generate metric data for the last 24 hours
const generateMetricData = (): MetricPoint[] => {
  const data: MetricPoint[] = [];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now);
    time.setHours(time.getHours() - i);
    data.push({
      timestamp: time,
      value: 0.5 + Math.random() * 0.4 + (i < 5 ? 0.2 : 0), // Higher values near current time
    });
  }
  return data;
};

export const mockMetrics: CycleMetrics = {
  imbalance_trend: generateMetricData(),
  migration_success_rate: 0.94,
  migration_failure_rate: 0.06,
  average_migration_duration: 85, // seconds
  cycles_per_hour: 12,
};
