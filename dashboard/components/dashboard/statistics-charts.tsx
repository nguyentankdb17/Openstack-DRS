"use client";

import { Card } from "@/components/ui/card";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { CycleMetrics } from "@/lib/types";
import { formatPercent, formatTime } from "@/lib/format-utils";

interface MetricsChartsProps {
  metrics: CycleMetrics;
}

export function MetricsCharts({ metrics }: MetricsChartsProps) {
  // Format data for imbalance trend
  const imbalanceData = metrics.imbalance_trend.map((point) => ({
    time: formatTime(point.timestamp),
    imbalance: Math.round(point.value * 100),
  }));

  // Success/Failure rate data
  const successRateData = [
    {
      name: "Success",
      value: Math.round(metrics.migration_success_rate * 100),
      fill: "#10b981",
    },
    {
      name: "Failure",
      value: Math.round(metrics.migration_failure_rate * 100),
      fill: "#ef4444",
    },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Cluster Imbalance Trend */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Cluster Imbalance Trend (Last 24h)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={imbalanceData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              stroke="#6b7280"
              style={{ fontSize: "12px" }}
            />
            <YAxis
              stroke="#6b7280"
              style={{ fontSize: "12px" }}
              label={{ value: "Imbalance %", angle: -90, position: "insideLeft" }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "1px solid #374151",
              }}
              labelStyle={{ color: "#f3f4f6" }}
              formatter={(value: number) => `${value}%`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="imbalance"
              stroke="#2563eb"
              dot={false}
              isAnimationActive={false}
              name="Imbalance %"
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Migration Success/Failure Rate */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Migration Success Rate
        </h3>
        <div className="flex flex-col items-center justify-center space-y-6">
          <div className="flex gap-8">
            {successRateData.map((item) => (
              <div key={item.name} className="text-center">
                <div className="relative w-24 h-24 flex items-center justify-center mb-2">
                  <div className="w-20 h-20 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: item.fill + "20" }}>
                    <span className="text-2xl font-bold" style={{ color: item.fill }}>
                      {item.value}%
                    </span>
                  </div>
                </div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {item.name}
                </p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Key Statistics */}
      <Card className="p-6 lg:col-span-2">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Key Statistics
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              Avg Migration Time
            </p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {metrics.average_migration_duration}s
            </p>
          </div>
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              Success Rate
            </p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatPercent(metrics.migration_success_rate)}
            </p>
          </div>
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              Failure Rate
            </p>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formatPercent(metrics.migration_failure_rate)}
            </p>
          </div>
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              Cycles/Hour
            </p>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {metrics.cycles_per_hour}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
