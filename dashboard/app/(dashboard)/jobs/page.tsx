"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { StatCard } from "@/components/dashboard/stat-card";
import { JobConfigForm } from "@/components/dashboard/job-config-form";
import {
  fetchCycleHistory,
  fetchMonitorJobStatus,
  fetchRuntimeConfiguration,
  pauseMonitorJob,
  restartMonitorJob,
  updateRuntimeConfiguration,
} from "@/lib/api";
import { formatDate } from "@/lib/format-utils";
import { JobConfiguration, JobStatus } from "@/lib/types";
import { Pause, Play, AlertCircle, Clock } from "lucide-react";

export default function JobsPage() {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [config, setConfig] = useState<JobConfiguration | null>(null);
  const [showSaveMessage, setShowSaveMessage] = useState(false);
  const [message, setMessage] = useState<string>("Changes saved successfully");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const [monitorStatus, runtimeConfig, history] = await Promise.all([
          fetchMonitorJobStatus(),
          fetchRuntimeConfiguration(),
          fetchCycleHistory(1),
        ]);

        setJobStatus({
          ...monitorStatus,
          last_cycle_id: history[0]?.id ?? null,
          last_cycle_time: history[0]?.cycle_started_at ?? null,
        });
        setConfig(runtimeConfig);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load job data");
      }
    };

    void load();
  }, []);

  const showMessage = (text: string) => {
    setMessage(text);
    setShowSaveMessage(true);
    setTimeout(() => setShowSaveMessage(false), 3000);
  };

  const jobStateLabel = useMemo(() => {
    if (!jobStatus) {
      return "Unknown";
    }

    return jobStatus.status.charAt(0).toUpperCase() + jobStatus.status.slice(1);
  }, [jobStatus]);

  const handlePause = async () => {
    try {
      setIsBusy(true);
      const updatedStatus = await pauseMonitorJob();
      setJobStatus((prev) => ({
        ...updatedStatus,
        last_cycle_id: prev?.last_cycle_id ?? null,
        last_cycle_time: prev?.last_cycle_time ?? null,
      }));
      showMessage("Monitor job paused successfully");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to pause job");
    } finally {
      setIsBusy(false);
    }
  };

  const handleStart = async (runNow: boolean) => {
    try {
      setIsBusy(true);
      const updatedStatus = await restartMonitorJob(runNow);
      setJobStatus((prev) => ({
        ...updatedStatus,
        last_cycle_id: prev?.last_cycle_id ?? null,
        last_cycle_time: prev?.last_cycle_time ?? null,
      }));
      showMessage(runNow ? "Job restarted and scheduled immediately" : "Monitor job resumed successfully");
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to restart job");
    } finally {
      setIsBusy(false);
    }
  };

  const handleConfigSave = async (data: JobConfiguration) => {
    try {
      setIsBusy(true);
      setError(null);
      const updated = await updateRuntimeConfiguration(data);
      setConfig(updated);
      showMessage("Runtime configuration updated successfully");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update configuration");
    } finally {
      setIsBusy(false);
    }
  };

  if (!jobStatus || !config) {
    return <p className="text-sm text-gray-600 dark:text-gray-400">Loading job management data...</p>;
  }

  return (
    <>
      <DashboardHeader
        title="Job Management"
        description="Configure and manage your OpenStack DRS job"
      />

      {error && (
        <div className="mb-8 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          label="Job Status"
          value={jobStateLabel}
          subtext={`Last cycle: ${jobStatus.last_cycle_id ? "#" + jobStatus.last_cycle_id : "Never"}`}
          icon={<AlertCircle className="w-8 h-8" />}
        />
        <StatCard
          label="Last Execution"
          value={
            jobStatus.last_cycle_time
              ? formatDate(jobStatus.last_cycle_time).split(", ").slice(0,2).join(", ")
              : "Never"
          }
          subtext={
            jobStatus.last_cycle_time
              ? formatDate(jobStatus.last_cycle_time).split(", ")[2]
              : ""
          }
          icon={<Clock className="w-8 h-8" />}
        />
        <StatCard
          label="Next Execution"
          value={
            jobStatus.next_execution
              ? formatDate(jobStatus.next_execution).split(", ").slice(0,2).join(", ")
              : "N/A"
          }
          subtext={
            jobStatus.next_execution
              ? formatDate(jobStatus.next_execution).split(", ")[2]
              : ""
          }
          icon={<Clock className="w-8 h-8" />}
        />
        <Card className="p-6 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Status Badge
            </p>
            <div className="mt-2">
              <StatusBadge status={jobStatus.status} />
            </div>
          </div>
        </Card>
      </div>

      {/* Save Message */}
      {showSaveMessage && (
        <div className="mb-8 p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg">
          <p className="text-sm text-green-800 dark:text-green-200">
            ✓ {message}
          </p>
        </div>
      )}

      {/* Job Control */}
      <Card className="p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
          Job Control
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button
            onClick={() => void handleStart(false)}
            disabled={jobStatus.status === "running"}
            className="bg-green-600 hover:bg-green-700"
          >
            <Play className="w-4 h-4 mr-2" />
            Start Job
          </Button>
          <Button
            onClick={handlePause}
            disabled={jobStatus.status === "paused"}
            variant="outline"
          >
            <Pause className="w-4 h-4 mr-2" />
            Pause Job
          </Button>
          <Button
            onClick={() => void handleStart(false)}
            disabled={isBusy}
            variant="outline"
          >
            Resume Job
          </Button>
          <Button variant="destructive" onClick={() => void handleStart(true)} disabled={isBusy}>
            Restart Now
          </Button>
        </div>
      </Card>

      {/* Configuration Form */}
      <JobConfigForm initialData={config} onSave={handleConfigSave} />

      {/* Additional Info */}
      <Card className="p-6 mt-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Configuration Info
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div>
            <p className="text-gray-600 dark:text-gray-400 mb-2">Created At</p>
            <p className="font-medium text-gray-900 dark:text-white">
              Runtime configuration is dynamic
            </p>
          </div>
          <div>
            <p className="text-gray-600 dark:text-gray-400 mb-2">Last Updated</p>
            <p className="font-medium text-gray-900 dark:text-white">
              {formatDate(new Date())}
            </p>
          </div>
          <div>
            <p className="text-gray-600 dark:text-gray-400 mb-2">Job ID</p>
            <p className="font-medium text-gray-900 dark:text-white font-mono text-xs">
              {jobStatus.id}
            </p>
          </div>
          <div>
            <p className="text-gray-600 dark:text-gray-400 mb-2">Configuration Version</p>
            <p className="font-medium text-gray-900 dark:text-white">
              v2.1.0
            </p>
          </div>
        </div>
      </Card>
    </>
  );
}
