"use client";

import { useState } from "react";
import { Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ConstraintHostOption,
  ConstraintInventoryOptions,
  ConstraintVMOption,
  MigrationConstraint,
} from "@/lib/types";

type ConstraintRuleType = MigrationConstraint["rule_type"];
type ExcludeScope = "vm" | "host";
type MultiSelectField = "vm_ids" | "allowed_hosts" | "forbidden_hosts" | "host_ids";

interface PickerOption {
  id: string;
  primary: string;
  secondary?: string;
  badge?: string;
}

interface ConstraintFormProps {
  constraint?: MigrationConstraint;
  options: ConstraintInventoryOptions;
  onSave: (data: Omit<MigrationConstraint, "created_at" | "updated_at">) => void;
  onCancel: () => void;
  isLoading?: boolean;
  isOptionsLoading?: boolean;
}

export function ConstraintForm({
  constraint,
  options,
  onSave,
  onCancel,
  isLoading = false,
  isOptionsLoading = false,
}: ConstraintFormProps) {
  const initialRuleType: ConstraintRuleType = constraint?.rule_type || "vm_host";
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
    exclude_scope: initialExcludeScope as ExcludeScope,
    description: constraint?.description || "",
    enabled: constraint?.enabled ?? true,
    vm_id: constraint?.vm_id || "",
    vm_ids: constraint?.vm_ids || [],
    policy: constraint?.policy || "must_separate",
    allowed_hosts: constraint?.allowed_hosts || [],
    forbidden_hosts: constraint?.forbidden_hosts || [],
    host_ids: constraint?.host_ids || constraint?.forbidden_hosts || [],
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

  const setSelectedValues = (name: MultiSelectField, values: string[]) => {
    setFormData((prev) => ({
      ...prev,
      [name]: values,
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
          : undefined,
      policy: formData.rule_type === "vm_vm" ? formData.policy : undefined,
      allowed_hosts:
        formData.rule_type === "vm_host"
          ? formData.allowed_hosts
          : undefined,
      forbidden_hosts:
        formData.rule_type === "vm_host"
          ? formData.forbidden_hosts
          : undefined,
      host_ids:
        formData.rule_type === "exclude" && formData.exclude_scope === "host"
          ? formData.host_ids
          : undefined,
    });
  };

  const vmOptions = mergeSelectedVMOptions(options.vms, [
    formData.vm_id,
    ...formData.vm_ids,
  ]);
  const hostOptions = mergeSelectedHostOptions(options.hosts, [
    ...formData.allowed_hosts,
    ...formData.forbidden_hosts,
    ...formData.host_ids,
  ]);
  const controlsDisabled = isLoading || isOptionsLoading;
  const vmPickerOptions = vmOptions.map(toVMOption);
  const hostPickerOptions = hostOptions.map(toHostOption);

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
              VM
            </label>
            <select
              name="vm_id"
              value={formData.vm_id}
              onChange={handleChange}
              disabled={controlsDisabled}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              required
            >
              <option value="">{isOptionsLoading ? "Loading VMs..." : "Select a VM"}</option>
              {vmOptions.map((vm) => (
                <option key={vm.id} value={vm.id}>
                  {formatVMOption(vm)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Allowed Hosts
            </label>
            <OptionMultiPicker
              options={hostPickerOptions}
              selectedIds={formData.allowed_hosts}
              onChange={(values) => setSelectedValues("allowed_hosts", values)}
              disabled={controlsDisabled}
              loading={isOptionsLoading}
              emptyText="No hosts found"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Forbidden Hosts
            </label>
            <OptionMultiPicker
              options={hostPickerOptions}
              selectedIds={formData.forbidden_hosts}
              onChange={(values) => setSelectedValues("forbidden_hosts", values)}
              disabled={controlsDisabled}
              loading={isOptionsLoading}
              emptyText="No hosts found"
            />
          </div>
        </>
      ) : formData.rule_type === "vm_vm" ? (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              VMs
            </label>
            <OptionMultiPicker
              options={vmPickerOptions}
              selectedIds={formData.vm_ids}
              onChange={(values) => setSelectedValues("vm_ids", values)}
              disabled={controlsDisabled}
              loading={isOptionsLoading}
              emptyText="No VMs found"
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
                Excluded VMs
              </label>
              <OptionMultiPicker
                options={vmPickerOptions}
                selectedIds={formData.vm_ids}
                onChange={(values) => setSelectedValues("vm_ids", values)}
                disabled={controlsDisabled}
                loading={isOptionsLoading}
                emptyText="No VMs found"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Excluded Hosts
              </label>
              <OptionMultiPicker
                options={hostPickerOptions}
                selectedIds={formData.host_ids}
                onChange={(values) => setSelectedValues("host_ids", values)}
                disabled={controlsDisabled}
                loading={isOptionsLoading}
                emptyText="No hosts found"
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

function OptionMultiPicker({
  options,
  selectedIds,
  onChange,
  disabled = false,
  loading = false,
  emptyText,
}: {
  options: PickerOption[];
  selectedIds: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
  loading?: boolean;
  emptyText: string;
}) {
  const [query, setQuery] = useState("");
  const selectedSet = new Set(selectedIds);
  const selectedOptions = selectedIds.map(
    (id) => options.find((option) => option.id === id) ?? {
      id,
      primary: id,
    }
  );
  const normalizedQuery = query.trim().toLowerCase();
  const filteredOptions = options.filter((option) => {
    if (!normalizedQuery) {
      return true;
    }
    return [option.primary, option.secondary, option.badge, option.id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalizedQuery));
  });

  const toggleOption = (id: string) => {
    if (disabled) {
      return;
    }
    if (selectedSet.has(id)) {
      onChange(selectedIds.filter((selectedId) => selectedId !== id));
      return;
    }
    onChange([...selectedIds, id]);
  };

  const removeOption = (id: string) => {
    if (!disabled) {
      onChange(selectedIds.filter((selectedId) => selectedId !== id));
    }
  };

  return (
    <div className="rounded-md border border-gray-300 bg-white shadow-sm dark:border-gray-600 dark:bg-gray-800">
      <div className="border-b border-gray-200 p-3 dark:border-gray-700">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            disabled={disabled}
            placeholder={loading ? "Loading..." : "Search"}
            className="h-9 pl-9"
          />
        </div>
        {selectedOptions.length > 0 ? (
          <div className="mt-3 flex max-h-20 flex-wrap gap-2 overflow-y-auto">
            {selectedOptions.map((option) => (
              <Badge
                key={option.id}
                variant="secondary"
                className="max-w-full justify-start gap-1.5 rounded-md bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
              >
                <span className="truncate">{option.primary}</span>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    removeOption(option.id);
                  }}
                  disabled={disabled}
                  className="rounded-sm text-blue-500 hover:text-blue-800 disabled:opacity-50 dark:text-blue-300 dark:hover:text-blue-100"
                  aria-label={`Remove ${option.primary}`}
                >
                  <X className="size-3" />
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      <div className="max-h-64 overflow-y-auto">
        {filteredOptions.length > 0 ? (
          filteredOptions.map((option) => {
            const checked = selectedSet.has(option.id);
            return (
              <div
                key={option.id}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-disabled={disabled}
                onClick={() => toggleOption(option.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggleOption(option.id);
                  }
                }}
                className={`flex w-full items-center gap-3 border-b border-gray-100 px-3 py-2.5 text-left last:border-b-0 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/60 ${
                  disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  readOnly
                  disabled={disabled}
                  tabIndex={-1}
                  aria-hidden="true"
                  className="size-4 shrink-0 rounded border-gray-300 text-blue-600"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-900 dark:text-white">
                    {option.primary}
                  </span>
                  {option.secondary ? (
                    <span className="block truncate text-xs text-gray-500 dark:text-gray-400">
                      {option.secondary}
                    </span>
                  ) : null}
                </span>
                {option.badge ? (
                  <span className="shrink-0 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                    {option.badge}
                  </span>
                ) : null}
              </div>
            );
          })
        ) : (
          <div className="px-3 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
            {loading ? "Loading..." : emptyText}
          </div>
        )}
      </div>
    </div>
  );
}

function mergeSelectedVMOptions(
  options: ConstraintVMOption[],
  selectedIds: string[]
): ConstraintVMOption[] {
  const byId = new Map(options.map((option) => [option.id, option]));
  selectedIds.filter(Boolean).forEach((id) => {
    if (!byId.has(id)) {
      byId.set(id, { id, name: null, current_host: "unknown" });
    }
  });
  return Array.from(byId.values());
}

function mergeSelectedHostOptions(
  options: ConstraintHostOption[],
  selectedIds: string[]
): ConstraintHostOption[] {
  const byId = new Map(options.map((option) => [option.id, option]));
  selectedIds.filter(Boolean).forEach((id) => {
    if (!byId.has(id)) {
      byId.set(id, { id, name: id, state: null, status: null });
    }
  });
  return Array.from(byId.values());
}

function formatVMOption(vm: ConstraintVMOption): string {
  const label = vm.name ? `${vm.name} (${vm.id})` : vm.id;
  return `${label} - ${vm.current_host}`;
}

function formatHostOption(host: ConstraintHostOption): string {
  const label = host.name && host.name !== host.id ? `${host.name} (${host.id})` : host.id;
  const state = [host.state, host.status].filter(Boolean).join("/");
  return state ? `${label} - ${state}` : label;
}

function toVMOption(vm: ConstraintVMOption): PickerOption {
  return {
    id: vm.id,
    primary: vm.name || vm.id,
    secondary: vm.name ? vm.id : undefined,
    badge: vm.current_host,
  };
}

function toHostOption(host: ConstraintHostOption): PickerOption {
  const state = [host.state, host.status].filter(Boolean).join("/");
  return {
    id: host.id,
    primary: host.name || host.id,
    secondary: host.name && host.name !== host.id ? host.id : undefined,
    badge: state || undefined,
  };
}
