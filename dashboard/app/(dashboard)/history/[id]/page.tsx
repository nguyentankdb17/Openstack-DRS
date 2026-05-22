"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { fetchCycleById } from "@/lib/api";
import { formatDate, formatDuration, formatPercent, formatTime, formatTimeWithSeconds } from "@/lib/format-utils";
import { Cycle, PredictionModeResult, PredictionResults } from "@/lib/types";
import { ArrowLeft } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const HISTORY_DETAIL_REFRESH_INTERVAL_MS = 15_000;

export default function CycleDetailPage() {
  const params = useParams();
  const cycleId = Number(params.id);
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const loadCycle = useCallback(
    async ({ showLoading }: { showLoading: boolean }) => {
      try {
        if (showLoading) {
          setLoading(true);
        }
        setError(null);
        const data = await fetchCycleById(cycleId);
        setCycle(data);
        setLastUpdatedAt(new Date());
      } catch (loadError) {
        if (showLoading) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load cycle details");
        }
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [cycleId]
  );

  useEffect(() => {
    if (!Number.isFinite(cycleId)) {
      setError("Invalid cycle id");
      setLoading(false);
      return;
    }

    void loadCycle({ showLoading: true });

    const intervalId = window.setInterval(() => {
      void loadCycle({ showLoading: false });
    }, HISTORY_DETAIL_REFRESH_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [cycleId, loadCycle]);

  const duration = useMemo(() => {
    if (!cycle?.cycle_finished_at) {
      return null;
    }

    return (
      (new Date(cycle.cycle_finished_at).getTime() -
        new Date(cycle.cycle_started_at).getTime()) /
      1000
    );
  }, [cycle]);

  if (loading) {
    return <p className="text-sm text-gray-600 dark:text-gray-400">Loading cycle details...</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
        {error}
      </div>
    );
  }

  if (!cycle) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Cycle Not Found
        </h2>
        <Link href="/history">
          <Button variant="outline">Back to History</Button>
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="mb-4">
        <Link href="/history" className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 mb-1">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to History
        </Link>
        <DashboardHeader
          title={`Cycle #${cycle.id}`}
          description="Detailed view of cluster rebalancing cycle"
          compact
          action={
            lastUpdatedAt ? (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Updated {formatTimeWithSeconds(lastUpdatedAt)} GMT+07
              </span>
            ) : null
          }
        />
      </div>

      {/* Cycle Summary */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5 mb-4">
        <Card className="flex min-h-[112px] flex-col items-center justify-center p-3 text-center">
          <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            Status
          </p>
          <div className="flex items-center justify-center">
            <StatusBadge status={cycle.status} />
          </div>
        </Card>

        <Card className="flex min-h-[112px] flex-col items-center justify-center p-3 text-center">
          <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            Current Imbalance
          </p>
          <p className="text-xl font-bold leading-none text-gray-900 dark:text-white">
            {cycle.current_cluster_imbalance !== null
              ? formatPercent(cycle.current_cluster_imbalance)
              : "N/A"}
          </p>
        </Card>

        <Card className="flex min-h-[112px] flex-col items-center justify-center p-3 text-center">
          <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            Predicted Imbalance
          </p>
          <p className="text-xl font-bold leading-none text-gray-900 dark:text-white">
            {cycle.predicted_cluster_imbalance !== null
              ? formatPercent(cycle.predicted_cluster_imbalance)
              : "N/A"}
          </p>
        </Card>

        <Card className="flex min-h-[112px] flex-col items-center justify-center p-3 text-center">
          <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            Threshold
          </p>
          <p className="text-xl font-bold leading-none text-gray-900 dark:text-white">
            {cycle.threshold ? formatPercent(cycle.threshold) : "N/A"}
          </p>
        </Card>

        <Card className="flex min-h-[112px] flex-col items-center justify-center p-3 text-center md:col-span-2 xl:col-span-1">
          <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            Timeline
          </p>
          <div className="grid grid-cols-1 justify-items-center gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <div className="flex items-start justify-center gap-2">
              <div className="mt-1.5 h-2 w-2 rounded-full bg-blue-600" />
              <div className="min-w-0 text-center">
                <p className="text-xs font-medium leading-tight text-gray-900 dark:text-white">
                  Started
                </p>
                <p className="truncate text-xs text-gray-600 dark:text-gray-400">
                  {formatDate(cycle.cycle_started_at)}
                </p>
                <p className="truncate text-xs text-gray-500 dark:text-gray-500">
                  {cycle.trigger_source}
                </p>
              </div>
            </div>

            {cycle.cycle_finished_at ? (
              <div className="flex items-start justify-center gap-2">
                <div
                  className={`mt-1.5 h-2 w-2 rounded-full ${
                    cycle.status === "completed" ? "bg-green-600" : "bg-red-600"
                  }`}
                />
                <div className="min-w-0 text-center">
                  <p className="text-xs font-medium leading-tight text-gray-900 dark:text-white">
                    Ended
                  </p>
                  <p className="truncate text-xs text-gray-600 dark:text-gray-400">
                    {formatDate(cycle.cycle_finished_at)}
                  </p>
                  {duration && (
                    <p className="text-xs text-gray-500 dark:text-gray-500">
                      {formatDuration(duration)}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-center gap-2">
                <div className="mt-1.5 h-2 w-2 animate-pulse rounded-full bg-yellow-600" />
                <div className="text-center">
                  <p className="text-xs font-medium leading-tight text-gray-900 dark:text-white">
                    In Progress
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-500">
                    Waiting for completion...
                  </p>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      <PredictionResultCard predictionResults={cycle.prediction_results} />

      {/* Migrations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        {/* Planned Migrations */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Planned Migrations ({cycle.planned_candidates.length})
          </h2>
          {cycle.planned_candidates.length > 0 ? (
            <div className="space-y-4">
              {cycle.planned_candidates.map((candidate, idx) => (
                <div
                  key={idx}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">
                        {candidate.vm_name ?? candidate.vm_id}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ID: {candidate.vm_id}
                      </p>
                    </div>
                  </div>
                  <div className="text-sm space-y-1">
                    <p className="text-gray-600 dark:text-gray-400">
                      <span className="font-medium">From:</span>{" "}
                      {candidate.source_host}
                    </p>
                    <p className="text-gray-600 dark:text-gray-400">
                      <span className="font-medium">To:</span>{" "}
                      {candidate.target_host}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400">
              No migrations planned for this cycle
            </p>
          )}
        </Card>

        {/* Executed Migrations */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Executed Migrations ({cycle.executed_candidates.length})
          </h2>
          {cycle.executed_candidates.length > 0 ? (
            <div className="space-y-4">
              {cycle.executed_candidates.map((candidate, idx) => (
                <div
                  key={idx}
                  className="border border-green-200 dark:border-green-800 rounded-lg p-4 bg-green-50 dark:bg-green-950"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">
                        {candidate.vm_name ?? candidate.vm_id}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        ID: {candidate.vm_id}
                      </p>
                    </div>
                    <span className="text-xs font-medium text-green-700 dark:text-green-300">
                      SUCCESS
                    </span>
                  </div>
                  <div className="text-sm space-y-1">
                    <p className="text-gray-600 dark:text-gray-400">
                      <span className="font-medium">From:</span>{" "}
                      {candidate.source_host}
                    </p>
                    <p className="text-gray-600 dark:text-gray-400">
                      <span className="font-medium">To:</span>{" "}
                      {candidate.target_host}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400">
              No migrations executed for this cycle
            </p>
          )}
        </Card>
      </div>

      {/* Details & Payload */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Details */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Details
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            {cycle.details || "No details available for this cycle."}
          </p>
          {cycle.error_message && (
            <div className="mt-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-sm font-medium text-red-700 dark:text-red-200 mb-2">
                Error
              </p>
              <p className="text-sm text-red-600 dark:text-red-300">
                {cycle.error_message}
              </p>
            </div>
          )}
        </Card>

        {/* Decision Payload */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Decision Payload
          </h2>
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-auto text-gray-800 dark:text-gray-200">
            {JSON.stringify(cycle.decision_payload, null, 2)}
          </pre>
        </Card>
      </div>
    </>
  );
}

function PredictionResultCard({
  predictionResults,
}: {
  predictionResults: PredictionResults;
}) {
  const modes = useMemo(
    () => Object.keys(predictionResults ?? {}).filter((mode) => (predictionResults[mode]?.rows ?? []).length > 0),
    [predictionResults]
  );
  const activeMode = useMemo(() => {
    const selectedMode = modes.find((item) => predictionResults[item]?.selected);
    return selectedMode ?? modes[0];
  }, [modes, predictionResults]);
  const result = activeMode ? predictionResults[activeMode] : null;
  const hosts = useMemo(() => {
    const hostSet = new Set((result?.rows ?? []).map((row) => row.host).filter(Boolean));
    return Array.from(hostSet).sort();
  }, [result]);
  const [host, setHost] = useState("");
  const activeHost = hosts.includes(host) ? host : hosts[0];

  const chartData = useMemo(() => {
    if (!result || !activeHost) {
      return [];
    }

    return result.rows
      .filter((row) => row.host === activeHost)
      .map((row) => ({
        time: formatTime(row.timestamp),
        cpu: Number(row.cpu.toFixed(2)),
        ram: Number(row.ram.toFixed(2)),
        swap: Number(row.swap.toFixed(2)),
      }));
  }, [activeHost, result]);

  if (modes.length === 0 || !result) {
    return null;
  }

  return (
    <Card className="p-4 mb-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Predict Result
          </h2>
          <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-400">
            {formatPredictionMeta(result)}
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Select value={activeHost} onValueChange={setHost}>
            <SelectTrigger className="h-9 w-[180px]">
              <SelectValue placeholder="Select compute" />
            </SelectTrigger>
            <SelectContent>
              {hosts.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 12 }} />
            <YAxis
              stroke="#6b7280"
              tick={{ fontSize: 12 }}
              domain={[0, 100]}
              label={{ value: "Usage %", angle: -90, position: "insideLeft" }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#111827",
                border: "1px solid #374151",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "#f9fafb" }}
              formatter={(value: number, name: string) => [
                `${Number(value).toFixed(2)}%`,
                name.toUpperCase(),
              ]}
            />
            <Line type="monotone" dataKey="cpu" stroke="#2563eb" dot={false} name="CPU" />
            <Line type="monotone" dataKey="ram" stroke="#059669" dot={false} name="RAM" />
            <Line type="monotone" dataKey="swap" stroke="#dc2626" dot={false} name="Swap" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function formatPredictionMeta(result: PredictionModeResult) {
  const score =
    result.predicted_cluster_imbalance !== null
      ? `imbalance ${formatPercent(result.predicted_cluster_imbalance)}`
      : "imbalance N/A";
  return `${result.window_minutes}m history lookback · ${score}`;
}
