import { Badge } from "@/components/ui/badge";
import { formatStatusLabel, getStatusBadgeVariant } from "@/lib/format-utils";

interface StatusBadgeProps {
  status: string;
  withDot?: boolean;
}

export function StatusBadge({ status, withDot = true }: StatusBadgeProps) {
  const variant = getStatusBadgeVariant(status);
  const label = formatStatusLabel(status);

  return (
    <Badge variant={variant} className="gap-2">
      {withDot && (
        <span
          className="w-2 h-2 rounded-full animate-pulse"
          style={{
            backgroundColor:
              status === "running"
                ? "#2563eb"
                : status === "completed" || status === "current_balanced" || status === "predicted_balanced"
                  ? "#16a34a"
                  : status === "failed" || status === "error" || status === "migration_failed"
                    ? "#dc2626"
                    : "#eab308",
          }}
        ></span>
      )}
      {label}
    </Badge>
  );
}
