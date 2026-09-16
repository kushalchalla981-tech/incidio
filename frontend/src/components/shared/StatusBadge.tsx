import Badge from "@/components/ui/Badge";
import { severityVariant, statusVariant } from "@/lib/status";

export function SeverityBadge({ severity, className }: { severity: string; className?: string }) {
  return (
    <Badge variant={severityVariant[severity] || "neutral"} className={className}>
      {severity}
    </Badge>
  );
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge variant={statusVariant[status] || "neutral"} className={className}>
      {status}
    </Badge>
  );
}