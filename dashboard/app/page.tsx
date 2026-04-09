"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatCard } from "@/components/dashboard/stat-card";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Sidebar } from "@/components/dashboard/sidebar";
import {
  buildMetricsFromCycles,
  fetchCycleHistory,
  fetchLatestMonitorDecision,
  fetchMonitorJobStatus,
} from "@/lib/api";
import { formatDate, formatPercent } from "@/lib/format-utils";
import { ClusterDecision, Cycle, JobStatus } from "@/lib/types";
import { Activity, AlertCircle, TrendingDown, Zap } from "lucide-react";

export default function Home() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [decision, setDecision] = useState<ClusterDecision | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [history, latestDecision, monitorStatus] = await Promise.all([
          fetchCycleHistory(20),
          fetchLatestMonitorDecision(),
          fetchMonitorJobStatus(),
        ]);

        const normalizedStatus: JobStatus = {
          ...monitorStatus,
          last_cycle_id: history[0]?.id ?? null,
          last_cycle_time: history[0]?.cycle_started_at ?? null,
        };

        setCycles(history);
        setDecision(latestDecision);
        setJobStatus(normalizedStatus);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard data");
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, []);

  const metrics = useMemo(() => buildMetricsFromCycles(cycles), [cycles]);

  const latestCycle = useMemo(() => {
    if (cycles.length > 0) {
      return cycles[0];
    }

    if (!decision) {
      return null;
    }

    return {
      id: 0,
      cycle_started_at: decision.timestamp,
      cycle_finished_at: null,
      trigger_source: "monitor",
      status: decision.status,
      current_cluster_imbalance: decision.current_cluster_imbalance,
      predicted_cluster_imbalance: decision.predicted_cluster_imbalance,
      threshold: decision.threshold,
      planned_candidates: decision.planned_candidates,
      executed_candidates: decision.execution_result ? [decision.selected_candidate].filter(Boolean) : [],
      details: decision.details,
      decision_payload: {},
      error_message: decision.status === "error" ? decision.details : null,
      created_at: decision.timestamp,
    } as Cycle;
  }, [cycles, decision]);

  if (isLoading || !latestCycle || !jobStatus) {
    return (
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <div className="p-8 text-gray-600 dark:text-gray-300">Loading dashboard data...</div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-8">
          <DashboardHeader
            title="Dashboard"
            description="Real-time monitoring of OpenStack cluster rebalancing cycles"
          />

          {error && (
            <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
              {error}
            </div>
          )}

          {/* Status Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard
              label="Job Status"
              value={
                jobStatus.status.charAt(0).toUpperCase() +
                jobStatus.status.slice(1)
              }
              subtext={`Last: ${formatDate(jobStatus.last_cycle_time)}`}
              icon={<Activity className="w-8 h-8" />}
              variant="success"
            />
            <StatCard
              label="Current Imbalance"
              value={
                latestCycle.current_cluster_imbalance !== null
                  ? formatPercent(latestCycle.current_cluster_imbalance)
                  : "N/A"
              }
              subtext={`Threshold: ${latestCycle.threshold ? formatPercent(latestCycle.threshold) : "N/A"}`}
              icon={<TrendingDown className="w-8 h-8" />}
              variant={
                latestCycle.current_cluster_imbalance !== null &&
                latestCycle.threshold !== null &&
                latestCycle.current_cluster_imbalance > latestCycle.threshold
                  ? "danger"
                  : "default"
              }
            />
            <StatCard
              label="Planned Migrations"
              value={latestCycle.planned_candidates.length}
              subtext="In current cycle"
              icon={<Zap className="w-8 h-8" />}
            />
            <StatCard
              label="Success Rate"
              value={formatPercent(metrics.migration_success_rate)}
              subtext="Last 24 hours"
              icon={<AlertCircle className="w-8 h-8" />}
              variant="success"
            />
          </div>

          {/* Latest Cycle Card */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <Card className="lg:col-span-2 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Latest Cycle (#{latestCycle.id})
                </h2>
                <StatusBadge status={latestCycle.status} />
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Started
                    </p>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {formatDate(latestCycle.cycle_started_at)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Status
                    </p>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {latestCycle.status === "running"
                        ? "In Progress"
                        : latestCycle.status === "completed"
                          ? "Completed"
                          : "Failed"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Predicted Imbalance
                    </p>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {latestCycle.predicted_cluster_imbalance !== null
                        ? formatPercent(latestCycle.predicted_cluster_imbalance)
                        : "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Executed
                    </p>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {latestCycle.executed_candidates.length} /{" "}
                      {latestCycle.planned_candidates.length}
                    </p>
                  </div>
                </div>

                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    Details
                  </p>
                  <p className="text-gray-900 dark:text-white">
                    {latestCycle.details ||
                      "No details available for this cycle."}
                  </p>
                </div>

                {latestCycle.error_message && (
                  <div className="border-t border-red-200 dark:border-red-800 pt-4 bg-red-50 dark:bg-red-950 p-3 rounded">
                    <p className="text-sm text-red-700 dark:text-red-200">
                      <strong>Error:</strong> {latestCycle.error_message}
                    </p>
                  </div>
                )}
              </div>
            </Card>

            {/* Quick Actions */}
            <Card className="p-6 flex flex-col">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Quick Actions
              </h3>
              <div className="space-y-3 flex-1 flex flex-col justify-center">
                <Link href="/history">
                  <Button className="w-full bg-blue-600 hover:bg-blue-700">
                    View History
                  </Button>
                </Link>
                <Link href="/statistics">
                  <Button className="w-full" variant="outline">
                    View Statistics
                  </Button>
                </Link>
                <Link href="/jobs">
                  <Button className="w-full" variant="outline">
                    Update Configuration
                  </Button>
                </Link>
                <Link href="/constraints">
                  <Button className="w-full" variant="outline">
                    Manage Constraints
                  </Button>
                </Link>
              </div>
            </Card>
          </div>

          {/* Recent Cycles Summary */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Recent Cycles
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                      ID
                    </th>
                    <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                      Started
                    </th>
                    <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                      Imbalance
                    </th>
                    <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                      Migrations
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {cycles.slice(0, 5).map((cycle) => (
                    <tr
                      key={cycle.id}
                      className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      <td className="py-3 px-4 text-gray-900 dark:text-white font-medium">
                        <Link
                          href={`/history/${cycle.id}`}
                          className="text-blue-600 hover:text-blue-700 dark:text-blue-400"
                        >
                          #{cycle.id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                        {formatDate(cycle.cycle_started_at)}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={cycle.status} withDot={false} />
                      </td>
                      <td className="py-3 px-4 text-gray-900 dark:text-white">
                        {cycle.current_cluster_imbalance !== null
                          ? formatPercent(cycle.current_cluster_imbalance)
                          : "N/A"}
                      </td>
                      <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                        {cycle.executed_candidates.length} /{" "}
                        {cycle.planned_candidates.length}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
