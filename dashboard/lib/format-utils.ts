export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return "N/A";
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

export function formatPercent(value: number): string {
  return (value * 100).toFixed(1) + "%";
}

export function formatNumber(value: number, decimals: number = 2): string {
  return value.toFixed(decimals);
}

export function getStatusColor(
  status: string
): string {
  switch (status) {
    case "running":
    case "migration_planned":
    case "migration_executed":
      return "text-blue-600 bg-blue-50";
    case "completed":
    case "current_balanced":
    case "predicted_balanced":
      return "text-green-600 bg-green-50";
    case "failed":
    case "error":
    case "migration_failed":
      return "text-red-600 bg-red-50";
    case "paused":
    case "skipped_by_event":
      return "text-yellow-600 bg-yellow-50";
    case "idle":
    case "reevaluating":
    case "current_imbalanced":
    case "predicted_imbalanced":
      return "text-gray-600 bg-gray-50";
    default:
      return "text-gray-600 bg-gray-50";
  }
}

export function getStatusBadgeVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "running":
    case "migration_planned":
    case "migration_executed":
      return "default";
    case "completed":
    case "current_balanced":
    case "predicted_balanced":
      return "secondary";
    case "failed":
    case "error":
    case "migration_failed":
      return "destructive";
    case "paused":
    case "idle":
    case "skipped_by_event":
    case "reevaluating":
    case "current_imbalanced":
    case "predicted_imbalanced":
      return "outline";
    default:
      return "default";
  }
}

export function formatStatusLabel(status: string): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
