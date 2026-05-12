"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, ChevronDown, ChevronUp, Clock, Loader2, ServerIcon, XCircle } from "lucide-react";
import { approvePendingPlan, fetchPendingPlan, rejectPendingPlan } from "@/lib/api";
import { PendingPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 10_000;

export function ActiveJobPanel() {
  const [plan, setPlan] = useState<PendingPlan | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const pending = await fetchPendingPlan();
      setPlan(pending);
      if (pending) setExpanded(true); // auto-expand when a new plan arrives
    } catch {
      // silently ignore polling errors
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const handleApprove = async () => {
    setIsBusy(true);
    setFeedback(null);
    try {
      await approvePendingPlan();
      setFeedback({ ok: true, msg: "Migration approved and executed." });
      setPlan(null);
    } catch (e) {
      setFeedback({ ok: false, msg: e instanceof Error ? e.message : "Approve failed." });
    } finally {
      setIsBusy(false);
    }
  };

  const handleReject = async () => {
    setIsBusy(true);
    setFeedback(null);
    try {
      await rejectPendingPlan();
      setFeedback({ ok: true, msg: "Plan rejected." });
      setPlan(null);
    } catch (e) {
      setFeedback({ ok: false, msg: e instanceof Error ? e.message : "Reject failed." });
    } finally {
      setIsBusy(false);
    }
  };

  // No plan → show idle state
  if (!plan) {
    return (
      <div className="mx-3 mb-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="relative flex h-2 w-2">
            <span className="inline-flex rounded-full h-2 w-2 bg-gray-400 dark:bg-gray-600" />
          </span>
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            Active Job
          </p>
        </div>
        {feedback && (
          <p className={cn(
            "text-xs mt-1 px-1",
            feedback.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
          )}>
            {feedback.msg}
          </p>
        )}
        <p className="text-xs text-gray-400 dark:text-gray-600 mt-1 px-1">No pending plan</p>
      </div>
    );
  }

  return (
    <div className="mx-3 mb-3 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 overflow-hidden">
      {/* Header */}
      <button
        id="active-job-panel-toggle"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          {/* Pulsing dot */}
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
          </span>
          <span className="text-xs font-semibold text-amber-800 dark:text-amber-300 uppercase tracking-wide">
            Active Job
          </span>
          <span className="text-xs bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200 rounded px-1.5 py-0.5 font-medium">
            {plan.candidates.length} candidate{plan.candidates.length !== 1 ? "s" : ""}
          </span>
        </div>
        {expanded
          ? <ChevronUp className="w-3 h-3 text-amber-600 dark:text-amber-400" />
          : <ChevronDown className="w-3 h-3 text-amber-600 dark:text-amber-400" />
        }
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {/* Meta */}
          <div className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
            <Clock className="w-3 h-3 shrink-0" />
            <span className="truncate">
              Triggered by <strong>{plan.trigger_source}</strong>
            </span>
          </div>

          {plan.current_cluster_imbalance !== null && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              Imbalance:{" "}
              <strong>{(plan.current_cluster_imbalance * 100).toFixed(1)}%</strong>
            </p>
          )}

          {/* Candidate list */}
          <div className="space-y-1 max-h-36 overflow-y-auto pr-0.5">
            {plan.candidates.map((c) => (
              <div
                key={c.vm_id}
                className="rounded bg-white dark:bg-gray-900 border border-amber-200 dark:border-amber-800 px-2 py-1.5"
              >
                <div className="flex items-center gap-1 mb-0.5">
                  <ServerIcon className="w-3 h-3 text-amber-500 shrink-0" />
                  <span className="text-xs font-mono font-medium text-gray-800 dark:text-gray-200 truncate max-w-[140px]">
                    {c.vm_name ?? c.vm_id}
                  </span>
                </div>
                <p className="text-[10px] text-gray-500 dark:text-gray-400 truncate">
                  {c.source_host} → {c.target_host}
                </p>
              </div>
            ))}
          </div>

          {feedback && (
            <p className={cn(
              "text-xs px-1",
              feedback.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
            )}>
              {feedback.msg}
            </p>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 pt-1">
            <button
              id="active-job-approve-btn"
              disabled={isBusy}
              onClick={() => void handleApprove()}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-semibold transition-colors",
                "bg-emerald-600 hover:bg-emerald-700 text-white",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {isBusy
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <CheckCircle className="w-3 h-3" />
              }
              Approve
            </button>
            <button
              id="active-job-reject-btn"
              disabled={isBusy}
              onClick={() => void handleReject()}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-semibold transition-colors",
                "bg-red-100 hover:bg-red-200 dark:bg-red-900/40 dark:hover:bg-red-900/60 text-red-700 dark:text-red-300",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              <XCircle className="w-3 h-3" />
              Reject
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
