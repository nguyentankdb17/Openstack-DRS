import {
  ClusterDecision,
  Cycle,
  CycleMetrics,
  JobConfiguration,
  JobStatus,
  LatestPredictionHistory,
  MetricPoint,
  MigrationCandidate,
  MigrationConstraint,
  PendingPlan,
  PredictionResults,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

async function request<T>(
  path: string,
  method: HttpMethod = "GET",
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}

function asDate(value: string | null | undefined): Date | null {
  return value ? parseApiDate(value) : null;
}

function parseApiDate(value: Date | string): Date {
  if (value instanceof Date) {
    return value;
  }

  const normalized = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)
    ? `${value}Z`
    : value;
  return new Date(normalized);
}

function mapCandidate(candidate: MigrationCandidate): MigrationCandidate {
  return {
    ...candidate,
    vm_name: candidate.vm_name ?? candidate.vm_id,
    reason:
      candidate.reason ??
      candidate.policy_reasons?.join(", ") ??
      "Planned by migration planner",
    estimated_duration: candidate.estimated_duration ?? 60,
    cpu_cores: candidate.cpu_cores ?? candidate.score_breakdown?.source_load,
    memory_gb: candidate.memory_gb ?? candidate.score_breakdown?.vm_size,
  };
}

function mapCycle(cycle: Cycle): Cycle {
  return {
    ...cycle,
    cycle_started_at: parseApiDate(cycle.cycle_started_at),
    cycle_finished_at: asDate(cycle.cycle_finished_at as string | null),
    created_at: parseApiDate(cycle.created_at),
    planned_candidates: (cycle.planned_candidates ?? []).map(mapCandidate),
    executed_candidates: (cycle.executed_candidates ?? []).map(mapCandidate),
    prediction_results: normalizePredictionResults(cycle.prediction_results),
  };
}

function normalizePredictionResults(results?: PredictionResults): PredictionResults {
  const normalized: PredictionResults = {};
  Object.entries(results ?? {}).forEach(([mode, result]) => {
    normalized[mode] = {
      ...result,
      rows: (result.rows ?? []).map((row) => ({
        ...row,
        timestamp: parseApiDate(row.timestamp),
        cpu: Number(row.cpu ?? 0),
        ram: Number(row.ram ?? 0),
        swap: Number(row.swap ?? 0),
      })),
    };
  });
  return normalized;
}

function normalizeJobStatus(data: Record<string, unknown>): JobStatus {
  const paused = Boolean(data.paused);
  const running = Boolean(data.scheduler_running);

  let status: JobStatus["status"] = "idle";
  if (!running) {
    status = "idle";
  } else if (paused) {
    status = "paused";
  } else {
    status = "running";
  }

  return {
    id: String(data.job_id ?? "monitor_cluster_job"),
    status,
    last_cycle_id: null,
    last_cycle_time: null,
    next_execution: asDate((data.next_run_time as string | null) ?? null),
    job_exists: Boolean(data.job_exists),
    scheduler_running: running,
    paused,
  };
}

export async function fetchLatestMonitorDecision(): Promise<ClusterDecision> {
  const response = await request<{ data: ClusterDecision }>("/monitor/latest");
  return {
    ...response.data,
    timestamp: parseApiDate(response.data.timestamp),
    execution_result: response.data.execution_result
      ? {
          ...response.data.execution_result,
          executed_at: parseApiDate(response.data.execution_result.executed_at),
        }
      : null,
    planned_candidates: (response.data.planned_candidates ?? []).map(mapCandidate),
    selected_candidate: response.data.selected_candidate
      ? mapCandidate(response.data.selected_candidate)
      : null,
  };
}

export async function fetchCycleHistory(limit = 50): Promise<Cycle[]> {
  const cycles = await request<Cycle[]>(`/cycles/history?limit=${limit}`);
  return cycles.map(mapCycle);
}

export async function fetchCycleById(id: number): Promise<Cycle | null> {
  const cycles = await fetchCycleHistory(500);
  return cycles.find((cycle) => cycle.id === id) ?? null;
}

export async function fetchLatestPredictionHistory(): Promise<LatestPredictionHistory> {
  const response = await request<LatestPredictionHistory>("/cycles/history/latest-predict");
  return {
    ...response,
    cycle_started_at: response.cycle_started_at ? parseApiDate(response.cycle_started_at) : null,
    prediction_results: normalizePredictionResults(response.prediction_results),
  };
}

export async function fetchMonitorJobStatus(): Promise<JobStatus> {
  const response = await request<{ data: Record<string, unknown> }>(
    "/admin/jobs/monitor"
  );
  return normalizeJobStatus(response.data);
}

export async function pauseMonitorJob(): Promise<JobStatus> {
  const response = await request<{ data: Record<string, unknown> }>(
    "/admin/jobs/monitor/pause",
    "POST"
  );
  return normalizeJobStatus(response.data);
}

export async function restartMonitorJob(runNow = false): Promise<JobStatus> {
  const response = await request<{ data: Record<string, unknown> }>(
    `/admin/jobs/monitor/restart?run_now=${runNow}`,
    "POST"
  );
  return normalizeJobStatus(response.data);
}

function mapConfigToJobConfiguration(config: Record<string, unknown>): JobConfiguration {
  return {
    scheduler_interval_minutes: Number(config.SCHEDULER_INTERVAL_MINUTES ?? 5),
    cluster_imbalance_threshold: Number(config.CLUSTER_IMBALANCE_THRESHOLD ?? 0.15),
    max_migration_per_cycle: Number(config.MAX_MIGRATIONS_PER_CYCLE ?? 1),
    prometheus_base_url: String(config.PROMETHEUS_BASE_URL ?? ""),
    prometheus_username: String(config.PROMETHEUS_USERNAME ?? ""),
    prometheus_password: String(config.PROMETHEUS_PASSWORD ?? ""),
    check_event_lookback_minutes: Number(config.CHECK_EVENT_LOOKBACK_MINUTES ?? 5),
    history_lookback_minutes: Number(config.HISTORY_LOOKBACK_MINUTES ?? 180),
    prediction_horizon_minutes: Number(config.PREDICTION_HORIZON_MINUTES ?? 5),
  };
}

function mapJobConfigurationToUpdates(data: JobConfiguration): Record<string, unknown> {
  return {
    SCHEDULER_INTERVAL_MINUTES: data.scheduler_interval_minutes,
    CLUSTER_IMBALANCE_THRESHOLD: data.cluster_imbalance_threshold,
    MAX_MIGRATIONS_PER_CYCLE: data.max_migration_per_cycle,
    PROMETHEUS_BASE_URL: data.prometheus_base_url,
    PROMETHEUS_USERNAME: data.prometheus_username,
    PROMETHEUS_PASSWORD: data.prometheus_password,
    CHECK_EVENT_LOOKBACK_MINUTES: data.check_event_lookback_minutes,
    HISTORY_LOOKBACK_MINUTES: data.history_lookback_minutes,
    PREDICTION_HORIZON_MINUTES: data.prediction_horizon_minutes,
  };
}

export async function fetchRuntimeConfiguration(): Promise<JobConfiguration> {
  const response = await request<{ data: Record<string, unknown> }>("/admin/config");
  return mapConfigToJobConfiguration(response.data);
}

export async function updateRuntimeConfiguration(
  data: JobConfiguration
): Promise<JobConfiguration> {
  const response = await request<{ data: Record<string, unknown> }>(
    "/admin/config",
    "PATCH",
    {
      updates: mapJobConfigurationToUpdates(data),
    }
  );
  return mapConfigToJobConfiguration(response.data);
}

export async function fetchConstraints(): Promise<MigrationConstraint[]> {
  const constraints = await request<
    Array<{
      rule_name: string;
      description: string;
      constraint_type: "vm_host" | "vm_vm" | "exclude";
      vm_id: string | null;
      policy: "must_together" | "must_separate" | null;
      vm_ids: string[];
      allowed_hosts: string[];
      forbidden_hosts: string[];
      host_ids?: string[];
      is_enabled: boolean;
      created_at: string;
      updated_at: string;
    }>
  >("/constraints");

  return constraints.map((item) => ({
    id: item.rule_name,
    rule_name: item.rule_name,
    name: item.rule_name,
    rule_type: item.constraint_type,
    description: item.description,
    enabled: item.is_enabled,
    vm_id: item.vm_id ?? undefined,
    vm_ids: item.vm_ids,
    policy: item.policy ?? undefined,
    allowed_hosts: item.allowed_hosts,
    forbidden_hosts: item.forbidden_hosts,
    host_ids: item.host_ids ?? item.forbidden_hosts,
    created_at: new Date(item.created_at),
    updated_at: new Date(item.updated_at),
  }));
}

export async function upsertConstraint(constraint: MigrationConstraint): Promise<MigrationConstraint> {
  if (constraint.rule_type === "vm_host") {
    await request("/constraints/vm-host", "POST", {
      rule_name: constraint.rule_name,
      description: constraint.description ?? "",
      vm_id: constraint.vm_id ?? "",
      allowed_hosts: constraint.allowed_hosts ?? [],
      forbidden_hosts: constraint.forbidden_hosts ?? [],
      is_enabled: constraint.enabled,
    });
  } else if (constraint.rule_type === "vm_vm") {
    await request("/constraints/vm-vm", "POST", {
      rule_name: constraint.rule_name,
      description: constraint.description ?? "",
      vm_ids: constraint.vm_ids ?? [],
      policy: constraint.policy ?? "must_separate",
      is_enabled: constraint.enabled,
    });
  } else {
    await request("/constraints/exclude", "POST", {
      rule_name: constraint.rule_name,
      description: constraint.description ?? "",
      vm_ids: constraint.vm_ids ?? [],
      host_ids: constraint.host_ids ?? [],
      is_enabled: constraint.enabled,
    });
  }

  const latest = await request<{
    rule_name: string;
    description: string;
    constraint_type: "vm_host" | "vm_vm" | "exclude";
    vm_id: string | null;
    policy: "must_together" | "must_separate" | null;
    vm_ids: string[];
    allowed_hosts: string[];
    forbidden_hosts: string[];
    host_ids?: string[];
    is_enabled: boolean;
    created_at: string;
    updated_at: string;
  }>(`/constraints/${constraint.rule_name}`);

  return {
    id: latest.rule_name,
    rule_name: latest.rule_name,
    name: latest.rule_name,
    rule_type: latest.constraint_type,
    description: latest.description,
    enabled: latest.is_enabled,
    vm_id: latest.vm_id ?? undefined,
    vm_ids: latest.vm_ids,
    policy: latest.policy ?? undefined,
    allowed_hosts: latest.allowed_hosts,
    forbidden_hosts: latest.forbidden_hosts,
    host_ids: latest.host_ids ?? latest.forbidden_hosts,
    created_at: new Date(latest.created_at),
    updated_at: new Date(latest.updated_at),
  };
}

export async function toggleConstraint(ruleName: string, enabled: boolean): Promise<void> {
  await request(`/constraints/${ruleName}/enable?enabled=${enabled}`, "PATCH");
}

export async function removeConstraint(ruleName: string): Promise<void> {
  await request(`/constraints/${ruleName}`, "DELETE");
}

export function buildMetricsFromCycles(cycles: Cycle[]): CycleMetrics {
  const sortedCycles = [...cycles].sort(
    (a, b) =>
      new Date(a.cycle_started_at).getTime() - new Date(b.cycle_started_at).getTime()
  );

  const imbalanceTrend: MetricPoint[] = sortedCycles
    .filter((cycle) => cycle.current_cluster_imbalance !== null)
    .map((cycle) => ({
      timestamp: new Date(cycle.cycle_started_at),
      value: cycle.current_cluster_imbalance ?? 0,
    }));

  const migrationStatuses = sortedCycles.filter(
    (cycle) =>
      cycle.status === "migration_executed" ||
      cycle.status === "migration_failed" ||
      cycle.status === "completed" ||
      cycle.status === "failed"
  );

  const successCount = migrationStatuses.filter(
    (cycle) => cycle.status === "migration_executed" || cycle.status === "completed"
  ).length;
  const totalCount = migrationStatuses.length;

  const migrationDurations = sortedCycles
    .filter((cycle) => cycle.cycle_finished_at)
    .map((cycle) => {
      const start = new Date(cycle.cycle_started_at).getTime();
      const end = new Date(cycle.cycle_finished_at as Date).getTime();
      return Math.max(1, Math.round((end - start) / 1000));
    });

  const averageMigrationDuration =
    migrationDurations.length > 0
      ? Math.round(
          migrationDurations.reduce((acc, value) => acc + value, 0) /
            migrationDurations.length
        )
      : 0;

  const now = Date.now();
  const oneHourAgo = now - 60 * 60 * 1000;
  const cyclesPerHour = sortedCycles.filter(
    (cycle) => new Date(cycle.cycle_started_at).getTime() >= oneHourAgo
  ).length;

  const successRate = totalCount > 0 ? successCount / totalCount : 0;

  return {
    imbalance_trend: imbalanceTrend,
    migration_success_rate: successRate,
    migration_failure_rate: 1 - successRate,
    average_migration_duration: averageMigrationDuration,
    cycles_per_hour: cyclesPerHour,
  };
}

export async function fetchPendingPlan(): Promise<PendingPlan | null> {
  const response = await request<{ pending: boolean; plan: PendingPlan | null }>(
    "/plan/pending"
  );
  if (!response.pending || !response.plan) return null;
  return {
    ...response.plan,
    created_at: new Date(response.plan.created_at as string),
    candidates: (response.plan.candidates ?? []).map(mapCandidate),
  };
}

export async function approvePendingPlan(
  candidateIds: string[] = []
): Promise<void> {
  await request("/plan/approve", "POST", { candidate_ids: candidateIds });
}

export async function rejectPendingPlan(): Promise<void> {
  await request("/plan/pending", "DELETE");
}
