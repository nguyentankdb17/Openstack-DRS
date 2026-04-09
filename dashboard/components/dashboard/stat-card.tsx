import { Card } from "@/components/ui/card";
import React from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger";
}

export function StatCard({
  label,
  value,
  subtext,
  icon,
  variant = "default",
}: StatCardProps) {
  const variantClasses = {
    default: "border-l-4 border-l-blue-500",
    success: "border-l-4 border-l-green-500",
    warning: "border-l-4 border-l-yellow-500",
    danger: "border-l-4 border-l-red-500",
  };

  return (
    <Card className={`p-6 ${variantClasses[variant]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {label}
          </p>
          <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {subtext && (
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
              {subtext}
            </p>
          )}
        </div>
        {icon && <div className="text-gray-400">{icon}</div>}
      </div>
    </Card>
  );
}
