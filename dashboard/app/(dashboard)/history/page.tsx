"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { fetchCycleHistory } from "@/lib/api";
import { formatDate, formatPercent } from "@/lib/format-utils";
import { Cycle } from "@/lib/types";
import { ChevronRight } from "lucide-react";

export default function HistoryPage() {
  const ITEMS_PER_PAGE = 20;
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(cycles.length / ITEMS_PER_PAGE));
  const paginatedCycles = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return cycles.slice(start, start + ITEMS_PER_PAGE);
  }, [cycles, currentPage]);

  const pageNumbers = useMemo(() => {
    const pages = Array.from({ length: totalPages }, (_, index) => index + 1);
    if (totalPages <= 7) return pages;

    if (currentPage <= 4) {
      return [1, 2, 3, 4, 5, -1, totalPages];
    }

    if (currentPage >= totalPages - 3) {
      return [1, -1, totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    }

    return [1, -1, currentPage - 1, currentPage, currentPage + 1, -1, totalPages];
  }, [currentPage, totalPages]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCycleHistory(100);
        setCycles(data);
        setCurrentPage(1);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load cycle history");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  return (
    <>
      <DashboardHeader
        title="Cycle History"
        description="View all cluster rebalancing cycles and their results"
      />

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      <Card className="p-6">
        {loading ? (
          <p className="text-sm text-gray-600 dark:text-gray-400">Loading cycle history...</p>
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  ID
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Started
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Finished
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Imbalance
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Threshold
                </th>
                <th className="text-left py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Migrations
                </th>
                <th className="text-center py-3 px-4 text-gray-700 dark:text-gray-300 font-medium">
                  Details
                </th>
              </tr>
            </thead>
            <tbody>
              {paginatedCycles.map((cycle) => (
                <tr
                  key={cycle.id}
                  className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  <td className="py-3 px-4 text-gray-900 dark:text-white font-medium">
                    #{cycle.id}
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400 text-xs">
                    {formatDate(cycle.cycle_started_at)}
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400 text-xs">
                    {cycle.cycle_finished_at
                      ? formatDate(cycle.cycle_finished_at)
                      : "In Progress"}
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={cycle.status} withDot={false} />
                  </td>
                  <td className="py-3 px-4 text-gray-900 dark:text-white">
                    {cycle.current_cluster_imbalance !== null
                      ? formatPercent(cycle.current_cluster_imbalance)
                      : "N/A"}
                  </td>
                  <td className="py-3 px-4 text-gray-900 dark:text-white">
                    {cycle.threshold ? formatPercent(cycle.threshold) : "N/A"}
                  </td>
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                    {cycle.executed_candidates.length} /{" "}
                    {cycle.planned_candidates.length}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <Link
                      href={`/history/${cycle.id}`}
                      className="inline-flex items-center text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {cycles.length > 0 && (
            <div className="mt-4 flex flex-col gap-3 border-t border-gray-200 pt-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-gray-600 dark:text-gray-400">
                Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}
                -{Math.min(currentPage * ITEMS_PER_PAGE, cycles.length)} of {cycles.length} cycles
              </p>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                >
                  Previous
                </button>

                {pageNumbers.map((pageNumber, index) =>
                  pageNumber === -1 ? (
                    <span
                      key={`ellipsis-${index}`}
                      className="px-2 text-xs text-gray-500 dark:text-gray-400"
                    >
                      ...
                    </span>
                  ) : (
                    <button
                      key={pageNumber}
                      type="button"
                      onClick={() => setCurrentPage(pageNumber)}
                      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                        currentPage === pageNumber
                          ? "border-blue-600 bg-blue-600 text-white"
                          : "border-gray-300 text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                      }`}
                    >
                      {pageNumber}
                    </button>
                  )
                )}

                <button
                  type="button"
                  onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
        )}
      </Card>
    </>
  );
}
