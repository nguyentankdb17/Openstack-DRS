"use client";

interface DashboardHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
}

export function DashboardHeader({
  title,
  description,
  action,
  compact = false,
}: DashboardHeaderProps) {
  return (
    <div className={`${compact ? "mb-3" : "mb-8"} flex items-center justify-between`}>
      <div>
        <h1 className={`${compact ? "text-2xl" : "text-3xl"} font-bold text-gray-900 dark:text-white`}>
          {title}
        </h1>
        {description && (
          <p className={`${compact ? "mt-1 text-sm" : "mt-2"} text-gray-600 dark:text-gray-400`}>
            {description}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
