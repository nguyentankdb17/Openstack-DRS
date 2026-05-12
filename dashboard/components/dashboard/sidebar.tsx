"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  BarChart3,
  LayoutDashboard,
  History,
  Cog,
  Lock,
} from "lucide-react";
import { ActiveJobPanel } from "@/components/dashboard/active-job-panel";

const navItems = [
  {
    label: "Home",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    label: "History",
    href: "/history",
    icon: History,
  },
  {
    label: "Statistics",
    href: "/statistics",
    icon: BarChart3,
  },
  {
    label: "Job Management",
    href: "/jobs",
    icon: Cog,
  },
  {
    label: "Constraints",
    href: "/constraints",
    icon: Lock,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950 flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          OpenStack DRS
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Distributed Resource Scheduler
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200"
                  : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
              )}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Active Job Panel */}
      <ActiveJobPanel />

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          v2.1.0 • Live Monitoring
        </p>
      </div>
    </div>
  );
}
