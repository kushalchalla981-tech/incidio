"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { ReactNode } from "react";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";

interface Props {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  change?: { value: string; up?: boolean; down?: boolean };
  loading?: boolean;
  children?: ReactNode;
  className?: string;
}

export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function KPI({
  label,
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  change,
  loading = false,
  children,
  className,
}: Props) {
  const [display, setDisplay] = useState(value);
  const ref = useRef<HTMLDivElement>(null);
  const animated = useRef(false);

  useEffect(() => {
    if (animated.current) return;
    const el = ref.current;
    if (!el || prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !animated.current) {
          animated.current = true;
          const dur = 600;
          const start = performance.now();
          setDisplay(0);
          const tick = (now: number) => {
            const p = Math.min((now - start) / dur, 1);
            const ease = 1 - Math.pow(1 - p, 3);
            setDisplay(value * ease);
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const formatted = decimals > 0 ? display.toFixed(decimals) : Math.round(display).toLocaleString();

  return (
    <div
      ref={ref}
      className={clsx(
        "bg-surface-base border border-border-soft rounded-lg p-4 shadow-sm transition-colors duration-150 hover:border-border-strong",
        className
      )}
    >
      <div className="text-xs font-medium text-text-secondary mb-2">{label}</div>
      {loading ? (
        <LoadingSkeleton className="h-[26px] w-16" />
      ) : (
        <div className="font-display text-[26px] font-semibold tracking-tight leading-none text-text-primary tabular-nums">
          {prefix}{formatted}{suffix}
        </div>
      )}
      {change && (
        <div
          className={clsx(
            "text-xs mt-2 font-medium",
            change.up && "text-status-success",
            change.down && "text-status-critical",
            !change.up && !change.down && "text-text-secondary"
          )}
        >
          {change.up ? "↑ " : change.down ? "↓ " : ""}{change.value}
        </div>
      )}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}