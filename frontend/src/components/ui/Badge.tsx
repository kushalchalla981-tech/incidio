import clsx from "clsx";
import type { ReactNode } from "react";

type Variant = "success" | "warn" | "danger" | "info" | "neutral";

const variants: Record<Variant, string> = {
  success: "bg-status-success/10 text-status-success border border-status-success/25",
  warn: "bg-status-high/10 text-status-high border border-status-high/25",
  danger: "bg-status-critical/10 text-status-critical border border-status-critical/25",
  info: "bg-status-medium/10 text-status-medium border border-status-medium/25",
  neutral: "bg-surface-elevated text-text-secondary border border-border-strong",
};

export default function Badge({
  children,
  variant = "info",
  className,
}: {
  children: ReactNode;
  variant?: Variant;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}