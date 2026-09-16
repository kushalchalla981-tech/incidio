import clsx from "clsx";

export default function LoadingSkeleton({ className }: { className?: string }) {
  return <div className={clsx("rounded-md bg-surface-elevated skeleton-pulse", className)} aria-hidden="true" />;
}