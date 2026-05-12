export type DateLike = Date | string;

export interface MigrationCandidate {
  vm_id: string;
  vm_name?: string;
  source_host: string;
  target_host: string;
  reason?: string;
  estimated_duration?: number; // seconds
  cpu_cores?: number;
  memory_gb?: number;
  migration_cost?: number;
  policy_reasons?: string[];
  score_breakdown?: Record<string, number>;
}

export interface Cycle {
  id: number;
  cycle_started_at: DateLike;
  cycle_finished_at: DateLike | null;
  trigger_source: string;
  status: string;
  current_cluster_imbalance: number | null;
  predicted_cluster_imbalance: number | null;
  threshold: number | null;
  planned_candidates: MigrationCandidate[];
  executed_candidates: MigrationCandidate[];
  details: string | null;
  decision_payload: Record<string, unknown>;
  error_message: string | null;
  created_at: DateLike;
}

export interface JobConfiguration {
  scheduler_interval_minutes: number;
  cluster_imbalance_threshold: number;
  max_migration_per_cycle: number;
  prometheus_base_url: string;
  prometheus_username: string;
  prometheus_password: string;
  check_event_lookback_minutes: number;
  prediction_horizon_minutes: number;
}

export interface MigrationConstraint {
  id: string;
  rule_name: string;
  name: string;
  rule_type: "vm_host" | "vm_vm";
  description?: string;
  enabled: boolean;
  vm_id?: string;
  vm_ids?: string[];
  policy?: "must_together" | "must_separate";
  allowed_hosts?: string[];
  forbidden_hosts?: string[];
  created_at: DateLike;
  updated_at: DateLike;
}

export interface JobStatus {
  id: string;
  status: "running" | "paused" | "idle" | "error";
  last_cycle_id: number | null;
  last_cycle_time: DateLike | null;
  next_execution: DateLike | null;
  error_message?: string;
  job_exists?: boolean;
  scheduler_running?: boolean;
  paused?: boolean;
}

export interface MetricPoint {
  timestamp: DateLike;
  value: number;
}

export interface CycleMetrics {
  imbalance_trend: MetricPoint[];
  migration_success_rate: number;
  migration_failure_rate: number;
  average_migration_duration: number;
  cycles_per_hour: number;
}

export interface ClusterDecision {
  status: string;
  timestamp: DateLike;
  current_cluster_imbalance: number | null;
  predicted_cluster_imbalance: number | null;
  threshold: number | null;
  recent_events: string[];
  planned_candidates: MigrationCandidate[];
  selected_candidate: MigrationCandidate | null;
  execution_result: {
    vm_id: string;
    source_host: string;
    target_host: string;
    success: boolean;
    message: string | null;
    executed_at: DateLike;
    metadata: Record<string, string>;
  } | null;
  details: string | null;
}

export interface PendingPlan {
  plan_id: string;
  created_at: DateLike;
  trigger_source: string;
  candidates: MigrationCandidate[];
  current_cluster_imbalance: number | null;
  details: string | null;
}
