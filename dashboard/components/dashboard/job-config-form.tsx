"use client";

import { useState } from "react";
import { useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { JobConfiguration } from "@/lib/types";
import { Eye, EyeOff } from "lucide-react";

interface JobConfigFormProps {
  initialData: JobConfiguration;
  onSave?: (data: JobConfiguration) => void;
}

export function JobConfigForm({ initialData, onSave }: JobConfigFormProps) {
  const [formData, setFormData] = useState(initialData);
  const [showPasswords, setShowPasswords] = useState({
    prometheus_password: false,
  });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setFormData(initialData);
  }, [initialData]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]:
        name.includes("minutes") || name.includes("max_migration")
        ? parseInt(value) || 0
        : name.includes("threshold")
          ? parseFloat(value) || 0
          : value,
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    // Simulate save delay
    await new Promise((resolve) => setTimeout(resolve, 1000));
    onSave?.(formData);
    setIsSaving(false);
  };

  const togglePasswordVisibility = (field: "prometheus_password") => {
    setShowPasswords((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  return (
    <Card className="p-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
        Job Configuration
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Scheduler Settings */}
        <div className="lg:col-span-2">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            Scheduler Settings
          </h3>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Scheduler Interval (minutes)
          </label>
          <Input
            type="number"
            name="scheduler_interval_minutes"
            value={formData.scheduler_interval_minutes}
            onChange={handleChange}
            className="w-full"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Time between scheduled checks in minutes
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Cluster Imbalance Threshold
          </label>
          <Input
            type="number"
            name="cluster_imbalance_threshold"
            value={formData.cluster_imbalance_threshold}
            onChange={handleChange}
            step="0.01"
            min="0"
            max="1"
            className="w-full"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Value between 0 and 1 (e.g., 0.75 = 75%)
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Max Migrations Per Cycle
          </label>
          <Input
            type="number"
            name="max_migration_per_cycle"
            value={formData.max_migration_per_cycle}
            onChange={handleChange}
            min="1"
            className="w-full"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Maximum number of concurrent migrations
          </p>
        </div>

        {/* Prometheus Settings */}
        <div className="lg:col-span-2 border-t border-gray-200 dark:border-gray-700 pt-6 mt-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            Prometheus Configuration
          </h3>
        </div>

        <div className="lg:col-span-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Base URL
          </label>
          <Input
            type="text"
            name="prometheus_base_url"
            value={formData.prometheus_base_url}
            onChange={handleChange}
            className="w-full"
            placeholder="http://prometheus:9090"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Username
          </label>
          <Input
            type="text"
            name="prometheus_username"
            value={formData.prometheus_username}
            onChange={handleChange}
            className="w-full"
            placeholder="optional"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Check Event Lookback (minutes)
          </label>
          <Input
            type="number"
            name="check_event_lookback_minutes"
            value={formData.check_event_lookback_minutes}
            onChange={handleChange}
            className="w-full"
            min="1"
          />
        </div>

        <div className="lg:col-span-2">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Password
          </label>
          <div className="relative">
            <Input
              type={showPasswords.prometheus_password ? "text" : "password"}
              name="prometheus_password"
              value={formData.prometheus_password}
              onChange={handleChange}
              className="w-full pr-10"
            />
            <button
              type="button"
              onClick={() => togglePasswordVisibility("prometheus_password")}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              {showPasswords.prometheus_password ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Prediction Settings */}
        <div className="lg:col-span-2 border-t border-gray-200 dark:border-gray-700 pt-6 mt-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            Prediction Settings
          </h3>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Prediction Horizon (minutes)
          </label>
          <Input
            type="number"
            name="prediction_horizon_minutes"
            value={formData.prediction_horizon_minutes}
            onChange={handleChange}
            className="w-full"
            min="1"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end border-t border-gray-200 dark:border-gray-700 pt-6">
        <Button variant="outline">Cancel</Button>
        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="bg-blue-600 hover:bg-blue-700"
        >
          {isSaving ? "Saving..." : "Save Configuration"}
        </Button>
      </div>
    </Card>
  );
}
