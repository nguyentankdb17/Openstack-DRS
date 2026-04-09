"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { fetchCycleById } from "@/lib/api";
import { formatDate, formatDuration, formatPercent } from "@/lib/format-utils";
import { Cycle } from "@/lib/types";
import { ArrowLeft } from "lucide-react";

export default function CycleDetailPage() {
  const params = useParams();
  const cycleId = Number(params.id);
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCycleById(cycleId);
        setCycle(data);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load cycle details");
      } finally {
        setLoading(false);
      }
    };

    if (!Number.isFinite(cycleId)) {
      setError("Invalid cycle id");
      setLoading(false);
      return;
    }

    void load();
  }, [cycleId]);

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
      <div className="mb-8">
        <Link href="/history" className="inline-flex items-center text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to History
        </Link>
        <DashboardHeader
          title={`Cycle #${cycle.id}`}
          description="Detailed view of cluster rebalancing cycle"
        />
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 mb-8">
        <Card className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Status
          </p>
          <div className="flex items-center justify-between">
            {/* <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {cycle.status.charAt(0).toUpperCase() + cycle.status.slice(1)}
            </p> */}
            <StatusBadge status={cycle.status} />
          </div>
        </Card>

        <Card className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Current Imbalance
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {cycle.current_cluster_imbalance !== null
              ? formatPercent(cycle.current_cluster_imbalance)
              : "N/A"}
          </p>
        </Card>

        <Card className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Predicted Imbalance
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {cycle.predicted_cluster_imbalance !== null
              ? formatPercent(cycle.predicted_cluster_imbalance)
              : "N/A"}
          </p>
        </Card>

        <Card className="p-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Threshold
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {cycle.threshold ? formatPercent(cycle.threshold) : "N/A"}
          </p>
        </Card>
      </div>

      {/* Timeline */}
      <Card className="p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Timeline
        </h2>
        <div className="space-y-4">
          <div className="flex items-start">
            <div className="flex flex-col items-center mr-4">
              <div className="w-4 h-4 bg-blue-600 rounded-full mt-2"></div>
              <div className="w-1 h-12 bg-blue-200 dark:bg-blue-800"></div>
            </div>
            <div>
              <p className="font-medium text-gray-900 dark:text-white">
                Cycle Started
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {formatDate(cycle.cycle_started_at)}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                Trigger: {cycle.trigger_source}
              </p>
            </div>
          </div>

          <div className="flex items-start">
            {cycle.cycle_finished_at ? (
              <>
                <div className="flex flex-col items-center mr-4">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      cycle.status === "completed" ? "bg-green-600" : "bg-red-600"
                    }`}
                  ></div>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    Cycle Ended
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {formatDate(cycle.cycle_finished_at)}
                  </p>
                  {duration && (
                    <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                      Duration: {formatDuration(duration)}
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="flex flex-col items-center mr-4">
                  <div className="w-4 h-4 bg-yellow-600 rounded-full animate-pulse"></div>
                </div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    Cycle In Progress
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                    Waiting for completion...
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </Card>

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
