"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { ArrowUpRight, Radar, ShieldCheck, Siren, CircleDot, Activity } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import LiveBadge from "@/components/shared/LiveBadge";
import MotionBackground from "@/components/shared/MotionBackground";
import { useHealth, useIncidents, useSecurityScans, useSecurityProjects, useSecurityFindings } from "@/lib/hooks";
import type { Product } from "@/components/layout/ProductSwitcher";

type IconType = LucideIcon;

const productMeta: Record<
  Product,
  { name: string; description: string; words: string[]; Icon: IconType; dashHref: string; altLabel: string; altHref: string }
> = {
  incidents: {
    name: "Incident Manager",
    description: "Tune how incidents, alerts, and collaboration work for your team. Your changes are stored on this device and apply instantly.",
    words: ["Respond & resolve", "Stay on alert", "Learn & improve"],
    Icon: Siren,
    dashHref: "/incidents/dashboard",
    altLabel: "View logs",
    altHref: "/incidents/logs",
  },
  security: {
    name: "Security Checker",
    description: "Control how public repos are scanned and analyzed. Everything here applies to your next scan, immediately.",
    words: ["Scan & triage", "Ship securely", "Watch repos"],
    Icon: ShieldCheck,
    dashHref: "/security",
    altLabel: "New scan",
    altHref: "/security/new",
  },
};

function usePrefersReducedMotion() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduce(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduce(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduce;
}

function RotatingWord({ words, className }: { words: string[]; className?: string }) {
  const reduce = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setIndex((v) => (v + 1) % words.length), 2600);
    return () => clearInterval(id);
  }, [reduce, words.length]);

  return (
    <span className={clsx("inline-grid", className)}>
      {words.map((word, i) => (
        <span
          key={word}
          aria-hidden={i !== index}
          className={clsx(
            "col-start-1 row-start-1 transition-opacity duration-500",
            i === index ? "opacity-100" : "opacity-0"
          )}
        >
          {word}
        </span>
      ))}
    </span>
  );
}

function Stat({ label, value, icon: Icon, tone = "text-text-secondary" }: { label: string; value: string; icon: IconType; tone?: string }) {
  return (
    <div className="inline-flex items-center gap-2.5 rounded-lg border border-border-soft bg-surface-sunken px-3 py-2">
      <Icon size={15} className={tone} />
      <div className="flex flex-col leading-tight">
        <span className="font-mono text-[13px] font-semibold text-text-primary tabular-nums">{value}</span>
        <span className="text-[10px] text-text-tertiary uppercase tracking-wide">{label}</span>
      </div>
    </div>
  );
}

export default function SettingsHero({ product }: { product: Product }) {
  const meta = productMeta[product];
  const { data: health } = useHealth();
  const online = health?.status === "ok";

  const { data: incidents, isLoading: incidentsLoading } = useIncidents({ limit: 500 });
  const { data: projects } = useSecurityProjects();
  const { data: scans } = useSecurityScans();
  const { data: findings } = useSecurityFindings();

  const activeCount = (incidents || []).filter((i) => i.status === "open" || i.status === "investigating").length;
  const resolvedCount = (incidents || []).filter((i) => i.status === "resolved" || i.status === "closed").length;
  const criticalCount = (incidents || []).filter((i) => i.severity === "critical").length;

  const resolvedWithTiming = (incidents || []).filter((i) => i.status === "resolved" && i.start_time && i.end_time);
  const avgMttrMs = resolvedWithTiming.length
    ? resolvedWithTiming.reduce((acc, i) => acc + (new Date(i.end_time as string).getTime() - new Date(i.start_time as string).getTime()), 0) /
      resolvedWithTiming.length
    : 0;
  const mttrLabel =
    avgMttrMs >= 3600000
      ? `~${Math.round(avgMttrMs / 3600000)}h`
      : avgMttrMs > 0
        ? `~${Math.max(1, Math.round(avgMttrMs / 60000))}m`
        : "—";

  const incidentsStats = [
    { label: "Active", value: incidentsLoading ? "…" : String(activeCount), icon: Radar, tone: "text-accent" },
    { label: "Critical", value: incidentsLoading ? "…" : String(criticalCount), icon: Siren, tone: "text-status-critical" },
    { label: "Resolved", value: incidentsLoading ? "…" : String(resolvedCount), icon: ArrowUpRight, tone: "text-status-success" },
    { label: "MTTR", value: incidentsLoading ? "…" : mttrLabel, icon: Activity, tone: "text-text-secondary" },
  ];

  const securityStats = [
    { label: "Projects", value: String(projects?.length ?? 0), icon: ShieldCheck, tone: "text-accent" },
    { label: "Scans", value: String(scans?.length ?? 0), icon: Radar, tone: "text-text-secondary" },
    { label: "Findings", value: String(findings?.length ?? 0), icon: Siren, tone: "text-status-high" },
  ];

  const stats = product === "security" ? securityStats : incidentsStats;

  return (
    <section className="relative overflow-hidden rounded-xl border border-border-strong bg-surface-base shadow-card">
      <MotionBackground />
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -right-12 -top-14 w-44 h-44 rounded-full border border-dashed border-accent-border animate-spin-slow motion-reduce:animate-none" />
        <div className="absolute right-8 top-10 hidden sm:grid place-items-center w-24 h-24 rotate-3 rounded-2xl bg-accent-soft text-accent animate-float-a motion-reduce:animate-none">
          <meta.Icon size={38} strokeWidth={1.5} />
        </div>
        <div className="absolute right-32 bottom-8 hidden md:block w-10 h-10 rounded-xl bg-accent-border/25 animate-float-b motion-reduce:animate-none" />
        <div className="absolute right-48 top-2 hidden lg:block">
          <span className="relative flex w-3 h-3">
            <span className="absolute inline-flex h-full w-full rounded-full bg-status-success opacity-50 animate-ping" />
            <span className="relative inline-flex rounded-full w-3 h-3 bg-status-success" />
          </span>
        </div>
        <div className="absolute -left-8 top-16 hidden md:block w-28 h-28 rounded-full bg-accent-soft animate-float-b motion-reduce:animate-none" />
      </div>

      <div className="relative grid gap-8 p-6 sm:p-10 lg:grid-cols-[1.25fr_1fr] lg:items-center">
        <div className="animate-fade-up">
          <div className="flex items-center gap-2 flex-wrap">
            <LiveBadge label="Live" />
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-border-soft bg-surface-sunken text-[11px] font-medium",
                online ? "text-text-secondary" : "text-status-critical"
              )}
            >
              <CircleDot size={12} className={online ? "text-status-success" : "text-status-critical"} />
              {online ? "All systems normal" : "Backend offline"}
            </span>
          </div>

          <h1 className="mt-4 text-3xl sm:text-4xl font-semibold tracking-tight text-text-primary leading-tight">
            {meta.name}{" "}
            <span className="text-text-tertiary font-normal">settings</span>
          </h1>

          <div className="mt-2.5 min-h-[1.75rem]">
            <RotatingWord words={meta.words} className="text-[17px] sm:text-xl font-medium text-accent leading-snug" />
          </div>

          <p className="mt-3 max-w-[46ch] text-[14px] text-text-secondary">{meta.description}</p>

          <div className="mt-6 flex flex-wrap gap-2.5">
            {stats.map((s) => (
              <Stat key={s.label} {...s} />
            ))}
          </div>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              href={meta.dashHref}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-accent text-white text-[13px] font-medium shadow-sm hover:brightness-95 active:scale-[0.98] transition-all duration-150"
            >
              Open {product === "security" ? "security dashboard" : "incident dashboard"}
              <ArrowUpRight size={14} />
            </Link>
            <Link
              href={meta.altHref}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md border border-border-strong text-text-primary text-[13px] font-medium bg-surface-base shadow-sm hover:border-text-tertiary hover:bg-surface-sunken transition-all duration-150"
            >
              {meta.altLabel}
            </Link>
          </div>
        </div>

        <div className="relative hidden lg:flex items-center justify-center h-60" aria-hidden>
          <div className="absolute w-52 h-52 rounded-full border border-dashed border-accent-border animate-spin-slow motion-reduce:animate-none" />
          <div className="absolute w-52 h-52 rounded-full border border-border-soft" />
          <div className="absolute grid place-items-center w-24 h-24 rounded-2xl bg-accent text-white shadow-lg animate-float-a motion-reduce:animate-none">
            <meta.Icon size={40} strokeWidth={1.5} />
          </div>
          <div className="absolute -top-2 right-10 px-3 py-1.5 rounded-lg border border-border-strong bg-surface-base shadow-card text-[11px] font-medium text-text-secondary animate-float-b motion-reduce:animate-none">
            {online ? "99.9% uptime" : "reconnecting…"}
          </div>
          <div className="absolute bottom-5 left-8 px-3 py-1.5 rounded-lg border border-border-strong bg-surface-base shadow-card text-[11px] font-medium text-accent animate-float-b motion-reduce:animate-none">
            24/7 watch
          </div>
        </div>
      </div>
    </section>
  );
}