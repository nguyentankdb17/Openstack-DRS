"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MigrationConstraint } from "@/lib/types";

interface ConstraintFormProps {
  constraint?: MigrationConstraint;
  onSave: (data: Omit<MigrationConstraint, "created_at" | "updated_at">) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ConstraintForm({
  constraint,
  onSave,
  onCancel,
  isLoading = false,
}: ConstraintFormProps) {
  const initialRuleType = constraint?.rule_type || "vm_host";
  const initialExcludeScope =
    constraint?.rule_type === "exclude" &&
    (constraint.host_ids?.length || (!constraint.vm_ids?.length && constraint.forbidden_hosts?.length))
      ? "host"
      : "vm";
  const [formData, setFormData] = useState({
    id: constraint?.id || constraint?.rule_name || "",
    rule_name: constraint?.rule_name || "",
    name: constraint?.name || constraint?.rule_name || "",
    rule_type: initialRuleType,
    exclude_scope: initialExcludeScope,
    description: constraint?.description || "",
    enabled: constraint?.enabled ?? true,
    vm_id: constraint?.vm_id || "",
    vm_ids: (constraint?.vm_ids || []).join(", "),
    policy: constraint?.policy || "must_separate",
    allowed_hosts: (constraint?.allowed_hosts || []).join(", "),
    forbidden_hosts: (constraint?.forbidden_hosts || []).join(", "),
    host_ids: (constraint?.host_ids || constraint?.forbidden_hosts || []).join(", "),
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const normalizedRuleName = formData.rule_name.trim() || formData.name.trim();
    onSave({
      id: normalizedRuleName,
      rule_name: normalizedRuleName,
      name: formData.name.trim() || normalizedRuleName,
      rule_type: formData.rule_type,
      description: formData.description,
      enabled: formData.enabled,
      vm_id: formData.rule_type === "vm_host" ? formData.vm_id.trim() : undefined,
      vm_ids:
        formData.rule_type === "vm_vm" || (formData.rule_type === "exclude" && formData.exclude_scope === "vm")
          ? formData.vm_ids
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined,
      policy: formData.rule_type === "vm_vm" ? formData.policy : undefined,
      allowed_hosts:
        formData.rule_type === "vm_host"
          ? formData.allowed_hosts
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined,
      forbidden_hosts:
        formData.rule_type === "vm_host"
          ? formData.forbidden_hosts
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined,
      host_ids:
        formData.rule_type === "exclude" && formData.exclude_scope === "host"
          ? formData.host_ids
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Rule Name
        </label>
        <Input
          type="text"
          name="rule_name"
          value={formData.rule_name}
          onChange={handleChange}
          placeholder="e.g., avoid-db-host-01"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Display Name
        </label>
        <Input
          type="text"
          name="name"
          value={formData.name}
          onChange={handleChange}
          placeholder="e.g., Avoid production DB hosts"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Rule Type
        </label>
        <select
          name="rule_type"
          value={formData.rule_type}
          onChange={handleChange}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="vm_host">VM to Host Constraint</option>
          <option value="vm_vm">VM to VM Affinity Constraint</option>
          <option value="exclude">Exclude VM/Host Constraint</option>
        </select>
      </div>

      {formData.rule_type === "vm_host" ? (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              VM ID
            </label>
            <Input
              type="text"
              name="vm_id"
              value={formData.vm_id}
              onChange={handleChange}
              placeholder="UUID of VM to constrain"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Allowed Hosts (comma-separated)
            </label>
            <Input
              type="text"
              name="allowed_hosts"
              value={formData.allowed_hosts}
              onChange={handleChange}
              placeholder="compute-01, compute-02"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Forbidden Hosts (comma-separated)
            </label>
            <Input
              type="text"
              name="forbidden_hosts"
              value={formData.forbidden_hosts}
              onChange={handleChange}
              placeholder="compute-03, compute-04"
            />
          </div>
        </>
      ) : formData.rule_type === "vm_vm" ? (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              VM IDs (comma-separated)
            </label>
            <Input
              type="text"
              name="vm_ids"
              value={formData.vm_ids}
              onChange={handleChange}
              placeholder="vm-uuid-1, vm-uuid-2"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Policy
            </label>
            <select
              name="policy"
              value={formData.policy}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              <option value="must_separate">Must Separate</option>
              <option value="must_together">Must Together</option>
            </select>
          </div>
        </>
      ) : (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Exclude Scope
            </label>
            <select
              name="exclude_scope"
              value={formData.exclude_scope}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              <option value="vm">VM only</option>
              <option value="host">Host only</option>
            </select>
          </div>

          {formData.exclude_scope === "vm" ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Excluded VM IDs (comma-separated)
              </label>
              <Input
                type="text"
                name="vm_ids"
                value={formData.vm_ids}
                onChange={handleChange}
                placeholder="vm-uuid-1, vm-uuid-2"
                required
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Excluded Hosts (comma-separated)
              </label>
              <Input
                type="text"
                name="host_ids"
                value={formData.host_ids}
                onChange={handleChange}
                placeholder="compute-01, compute-02"
                required
              />
            </div>
          )}
        </>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Description
        </label>
        <textarea
          name="description"
          value={formData.description}
          onChange={handleChange}
          placeholder="Describe what this constraint prevents or requires"
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        />
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          name="enabled"
          id="enabled"
          checked={formData.enabled}
          onChange={handleChange}
          className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded"
        />
        <label htmlFor="enabled" className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          Enable this constraint
        </label>
      </div>

      <div className="flex gap-3 justify-end pt-4 border-t border-gray-200 dark:border-gray-700">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={isLoading}
          className="bg-blue-600 hover:bg-blue-700"
        >
          {isLoading ? "Saving..." : "Save Constraint"}
        </Button>
      </div>
    </form>
  );
}
