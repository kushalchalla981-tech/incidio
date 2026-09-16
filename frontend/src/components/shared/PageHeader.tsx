import clsx from "clsx";
import type { ReactNode } from "react";

interface Props {
  title: string;
  description?: string;
  badge?: { label: string; tone?: "severity" | "neutral" };
  actions?: ReactNode;
  className?: string;
}

export default function PageHeader({ title, description, badge, actions, className }: Props) {
  return (
    <div
      className={clsx(
        "flex flex-col lg:flex-row lg:items-center justify-between gap-3 border-b border-border-soft pb-4 mb-5",
        className
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary truncate">{title}</h1>
          {badge && (
            <span
              className={clsx(
                "inline-flex items-center px-2 py-0.5 rounded-full text-[12px] font-medium whitespace-nowrap",
                badge.tone === "neutral"
                  ? "bg-surface-elevated text-text-secondary"
                  : "bg-status-critical/10 text-status-critical"
              )}
            >
              {badge.label}
            </span>
          )}
        </div>
        {description && <p className="mt-1 text-sm text-text-secondary">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap shrink-0">{actions}</div>}
    </div>
  );
}