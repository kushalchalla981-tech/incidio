export const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;
export const STATUS_ORDER = ["open", "investigating", "resolved", "closed"] as const;

export const severityVariant: Record<string, "danger" | "warn" | "info" | "neutral"> = {
  critical: "danger",
  high: "warn",
  medium: "info",
  low: "neutral",
};

export const statusVariant: Record<string, "danger" | "warn" | "success" | "neutral"> = {
  open: "danger",
  investigating: "warn",
  resolved: "success",
  closed: "neutral",
};