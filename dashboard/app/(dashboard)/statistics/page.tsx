"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardHeader } from "@/components/dashboard/header";
import { MetricsCharts } from "@/components/dashboard/statistics-charts";
import { buildMetricsFromCycles, fetchCycleHistory } from "@/lib/api";
import { formatTimeWithSeconds } from "@/lib/format-utils";
import { Cycle } from "@/lib/types";
import { RefreshCw, Download } from "lucide-react";

export default function StatisticsPage() {
  const [refreshInterval, setRefreshInterval] = useState<number>(30);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const metrics = useMemo(() => buildMetricsFromCycles(cycles), [cycles]);

  const loadMetrics = async () => {
    try {
      setError(null);
      const data = await fetchCycleHistory(200);
      setCycles(data);
      setLastUpdated(new Date());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load metrics");
    }
  };

  useEffect(() => {
    void loadMetrics();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadMetrics();
    }, refreshInterval * 1000);

    return () => window.clearInterval(timer);
  }, [refreshInterval]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadMetrics();
    setIsRefreshing(false);
  };

  const handleExport = () => {
    const data = JSON.stringify(metrics, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `metrics-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  return (
    <>
      <DashboardHeader
        title="Statistics"
        description="Monitor cluster rebalancing trends and performance statistics"
        action={
          <div className="flex gap-2">
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
            >
              <option value={10}>Refresh: 10s</option>
              <option value={30}>Refresh: 30s</option>
              <option value={60}>Refresh: 1m</option>
              <option value={300}>Refresh: 5m</option>
            </select>
            <Button
              onClick={handleRefresh}
              disabled={isRefreshing}
              variant="outline"
              className="gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </Button>
            <Button
              onClick={handleExport}
              variant="outline"
              className="gap-2"
            >
              <Download className="w-4 h-4" />
              Export
            </Button>
          </div>
        }
      />

      {error && (
        <div className="mb-8 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Time Range Info */}
      <Card className="p-4 mb-8 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
        <p className="text-sm text-blue-900 dark:text-blue-100">
          <strong>Auto-refresh enabled:</strong> Statistics refresh every {refreshInterval} seconds.
          Last updated: {formatTimeWithSeconds(lastUpdated)} GMT+07
        </p>
      </Card>

      {/* Charts */}
      <MetricsCharts metrics={metrics} />
    </>
  );
}
