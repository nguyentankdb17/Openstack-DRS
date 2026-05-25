"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardHeader } from "@/components/dashboard/header";
import { ConstraintForm } from "@/components/dashboard/constraint-form";
import {
  fetchConstraintOptions,
  fetchConstraints,
  removeConstraint,
  toggleConstraint,
  upsertConstraint,
} from "@/lib/api";
import { ConstraintInventoryOptions, MigrationConstraint } from "@/lib/types";
import { formatDate } from "@/lib/format-utils";
import { Trash2, Edit2, Plus, ToggleLeft } from "lucide-react";

function getConstraintTypeLabel(ruleType: MigrationConstraint["rule_type"]): string {
  if (ruleType === "vm_host") {
    return "VM to Host";
  }
  if (ruleType === "vm_vm") {
    return "VM to VM";
  }
  return "Exclude";
}

function getConstraintDetails(constraint: MigrationConstraint): string {
  if (constraint.rule_type === "vm_host") {
    const parts = [
      constraint.vm_id ? `VM ${constraint.vm_id}` : "",
      constraint.allowed_hosts?.length ? `allowed: ${constraint.allowed_hosts.join(", ")}` : "",
      constraint.forbidden_hosts?.length ? `forbidden: ${constraint.forbidden_hosts.join(", ")}` : "",
    ].filter(Boolean);
    return parts.join(" | ") || "-";
  }

  if (constraint.rule_type === "vm_vm") {
    const vmIds = constraint.vm_ids?.join(", ") || "-";
    return `${constraint.policy ?? "must_separate"}: ${vmIds}`;
  }

  const parts = [
    constraint.vm_ids?.length ? `VMs: ${constraint.vm_ids.join(", ")}` : "",
    constraint.host_ids?.length ? `Hosts: ${constraint.host_ids.join(", ")}` : "",
  ].filter(Boolean);
  return parts.join(" | ") || "-";
}

export default function ConstraintsPage() {
  const [constraints, setConstraints] = useState<MigrationConstraint[]>([]);
  const [constraintOptions, setConstraintOptions] = useState<ConstraintInventoryOptions>({
    vms: [],
    hosts: [],
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isOptionsLoading, setIsOptionsLoading] = useState(false);
  const [showMessage, setShowMessage] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setIsLoading(true);
        setIsOptionsLoading(true);
        const [constraintsResult, optionsResult] = await Promise.allSettled([
          fetchConstraints(),
          fetchConstraintOptions(),
        ]);

        if (constraintsResult.status === "rejected") {
          throw constraintsResult.reason;
        }

        setConstraints(constraintsResult.value);
        if (optionsResult.status === "fulfilled") {
          setConstraintOptions(optionsResult.value);
        } else {
          setShowMessage({
            type: "error",
            message:
              optionsResult.reason instanceof Error
                ? optionsResult.reason.message
                : "Failed to load OpenStack VM and host options",
          });
        }
      } catch (loadError) {
        setShowMessage({
          type: "error",
          message: loadError instanceof Error ? loadError.message : "Failed to load constraints",
        });
      } finally {
        setIsLoading(false);
        setIsOptionsLoading(false);
      }
    };

    void load();
  }, []);

  const handleCreateNew = () => {
    setIsCreating(true);
    setEditingId(null);
  };

  const handleSaveConstraint = async (
    data: Omit<MigrationConstraint, "created_at" | "updated_at">
  ) => {
    try {
      setIsLoading(true);
      const saved = await upsertConstraint({
        ...data,
        created_at: new Date(),
        updated_at: new Date(),
      });

      setConstraints((prev) => {
        const exists = prev.some((item) => item.id === saved.id);
        if (exists) {
          return prev.map((item) => (item.id === saved.id ? saved : item));
        }
        return [saved, ...prev];
      });

      setShowMessage({
        type: "success",
        message: isCreating ? "Constraint created successfully" : "Constraint updated successfully",
      });
    } catch (saveError) {
      setShowMessage({
        type: "error",
        message: saveError instanceof Error ? saveError.message : "Failed to save constraint",
      });
    } finally {
      setIsLoading(false);
    }

    setIsCreating(false);
    setEditingId(null);
    setTimeout(() => setShowMessage(null), 3000);
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this constraint?")) {
      try {
        setIsLoading(true);
        await removeConstraint(id);
        setConstraints((prev) => prev.filter((c) => c.id !== id));
        setShowMessage({ type: "success", message: "Constraint deleted successfully" });
      } catch (deleteError) {
        setShowMessage({
          type: "error",
          message: deleteError instanceof Error ? deleteError.message : "Failed to delete constraint",
        });
      } finally {
        setIsLoading(false);
        setTimeout(() => setShowMessage(null), 3000);
      }
    }
  };

  const handleToggle = async (id: string) => {
    const current = constraints.find((item) => item.id === id);
    if (!current) {
      return;
    }

    try {
      setIsLoading(true);
      await toggleConstraint(id, !current.enabled);
      setConstraints((prev) =>
        prev.map((c) =>
          c.id === id ? { ...c, enabled: !c.enabled, updated_at: new Date() } : c
        )
      );
    } catch (toggleError) {
      setShowMessage({
        type: "error",
        message: toggleError instanceof Error ? toggleError.message : "Failed to update constraint",
      });
      setTimeout(() => setShowMessage(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <DashboardHeader
        title="Migration Constraints"
        description="Create and manage migration rules and constraints"
        action={
          !isCreating && !editingId && (
            <Button
              onClick={handleCreateNew}
              className="bg-blue-600 hover:bg-blue-700"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Constraint
            </Button>
          )
        }
      />

      {showMessage && (
        <div
          className={`mb-8 p-4 rounded-lg ${
            showMessage.type === "success"
              ? "bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800"
              : "bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800"
          }`}
        >
          <p
            className={`text-sm ${
              showMessage.type === "success"
                ? "text-green-800 dark:text-green-200"
                : "text-red-800 dark:text-red-200"
            }`}
          >
            ✓ {showMessage.message}
          </p>
        </div>
      )}

      {isCreating || editingId ? (
        <Card className="p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            {isCreating ? "Create New Constraint" : "Edit Constraint"}
          </h2>
          <ConstraintForm
            constraint={
              editingId
                ? constraints.find((c) => c.id === editingId)
                : undefined
            }
            options={constraintOptions}
            onSave={handleSaveConstraint}
            isLoading={isLoading}
            isOptionsLoading={isOptionsLoading}
            onCancel={() => {
              setIsCreating(false);
              setEditingId(null);
            }}
          />
        </Card>
      ) : null}

      {/* Constraints Table */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Active Constraints ({constraints.length})
        </h2>
        {isLoading && (
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">Syncing constraints...</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Name
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Type
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Description
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Scope
                </th>
                <th className="text-center py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Updated
                </th>
                <th className="text-center py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {constraints.map((constraint) => (
                <tr
                  key={constraint.id}
                  className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <td className="py-3 px-4 font-medium text-gray-900 dark:text-white">
                    {constraint.name}
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-block px-3 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
                      {getConstraintTypeLabel(constraint.rule_type)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                    {constraint.description || "-"}
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-600 dark:text-gray-400 max-w-xs">
                    <span className="block truncate" title={getConstraintDetails(constraint)}>
                      {getConstraintDetails(constraint)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                        constraint.enabled
                          ? "bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200"
                          : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200"
                      }`}
                    >
                      {constraint.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-600 dark:text-gray-400">
                    {formatDate(constraint.updated_at).split(" ")[0]}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex gap-2 justify-center">
                      <button
                        onClick={() => void handleToggle(constraint.id)}
                        className="p-2 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title={
                          constraint.enabled ? "Disable" : "Enable"
                        }
                      >
                        <ToggleLeft className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setEditingId(constraint.id)}
                        className="p-2 text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => void handleDelete(constraint.id)}
                        className="p-2 text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {constraints.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-500 dark:text-gray-400">
              No constraints found. Create one to get started.
            </p>
          </div>
        )}
      </Card>
    </>
  );
}
