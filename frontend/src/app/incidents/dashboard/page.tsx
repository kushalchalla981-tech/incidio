"use client";

import { useMemo, useState } from "react";
import { RefreshCw, Activity, BarChart3 } from "lucide-react";
import Link from "next/link";
import KPI from "@/components/ui/KPI";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import LiveBadge from "@/components/shared/LiveBadge";
import ErrorState from "@/components/shared/ErrorState";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import ServiceHealth from "@/components/dashboard/ServiceHealth";
import QuickActions from "@/components/dashboard/QuickActions";
import RecentIncidents from "@/components/dashboard/RecentIncidents";
import IncidentTrend from "@/components/dashboard/IncidentTrend";
import { useIncidents } from "@/lib/hooks";

const RANGES = [
  { value: "7d", label: "Last 7 days", days: 7 },
  { value: "14d", label: "Last 14 days", days: 14 },
  { value: "30d", label: "Last 30 days", days: 30 },
  { value: "all", label: "All time", days: Infinity },
] as const;

function mttrMinutes(incidents: { start_time: string; end_time?: string | null }[]) {
  const durations = incidents
    .filter((i) => i.end_time)
    .map((i) => (new Date(i.end_time!).getTime() - new Date(i.start_time).getTime()) / 60000)
    .filter((m) => m >= 0);
  if (durations.length === 0) return null;
  return Math.round(durations.reduce((a, b) => a + b, 0) / durations.length);
}

export default function DashboardPage() {
  const [range, setRange] = useState<(typeof RANGES)[number]["value"]>("14d");
  const { data: incidents, isLoading, isError, error, refetch, isFetching } = useIncidents();

  const days = RANGES.find((r) => r.value === range)?.days ?? Infinity;
  const since = days === Infinity ? null : Date.now() - days * 24 * 60 * 60 * 1000;

  const filtered = useMemo(
    () => (incidents || []).filter((i) => !since || new Date(i.start_time).getTime() >= since),
    [incidents, since]
  );

  const active = (incidents || []).filter((i) => i.status === "open" || i.status === "investigating");
  const criticalActive = active.filter((i) => i.severity === "critical").length;

  const resolvedSince = (incidents || []).filter(
    (i) => (i.status === "resolved" || i.status === "closed") && i.end_time && (!since || new Date(i.start_time).getTime() >= since)
  );
  const resolvedToday = (incidents || []).filter(
    (i) => i.status === "resolved" && new Date(i.updated_at).toDateString() === new Date().toDateString()
  ).length;
  const avgMttr = mttrMinutes(resolvedSince);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-[20px] font-semibold tracking-tight text-text-primary">Dashboard</h1>
          <LiveBadge />
        </div>
        <div className="flex items-center gap-3">
          <Select
            className="w-40"
            value={range}
            onChange={(e) => setRange(e.target.value as (typeof RANGES)[number]["value"])}
            options={RANGES.map((r) => ({ value: r.value, label: r.label }))}
          />
          <Button variant="secondary" size="sm" onClick={() => refetch()} loading={isFetching}>
            <RefreshCw size={14} /> Refresh
          </Button>
        </div>
      </div>

      {isError && <ErrorState title="Failed to load incidents" message={error?.message} />}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI
          label="Active Incidents"
          value={active.length}
          loading={isLoading}
          change={active.length > 0 ? { value: "Open or investigating", up: active.length > 0 } : undefined}
        />
        <KPI
          label="Critical Alerts"
          value={criticalActive}
          loading={isLoading}
          change={{ value: "Need immediate attention", down: criticalActive > 0 }}
        />
        <KPI
          label="Resolved Today"
          value={resolvedToday}
          loading={isLoading}
          change={resolvedToday > 0 ? { value: "Confirmed via timeline", up: true } : undefined}
        />
        <KPI
          label="MTTR (all time)"
          value={avgMttr ?? 0}
          suffix="m"
          loading={isLoading}
          change={{
            value: avgMttr === null ? "No resolved incidents yet" : `${resolvedSince.length} incidents analyzed`,
            up: true,
          }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
              <h3 className="text-[14px] font-semibold flex items-center gap-2">
                <BarChart3 size={16} className="text-accent" />
                Incident Trend
              </h3>
              <Link href="/incidents">
                <Button variant="ghost" size="sm">View All</Button>
              </Link>
            </div>
            {isLoading ? (
              <LoadingSkeleton className="h-40 w-full" />
            ) : (
              <IncidentTrend incidents={filtered} days={days === Infinity ? 30 : days} />
            )}
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
              <h3 className="text-[14px] font-semibold flex items-center gap-2">
                <Activity size={16} className="text-status-high" />
                Recent Incidents
              </h3>
              <Link href="/incidents">
                <Button variant="ghost" size="sm">View All</Button>
              </Link>
            </div>
            <RecentIncidents incidents={incidents} isLoading={isLoading} />
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
              <h3 className="text-[14px] font-semibold flex items-center gap-2">
                <Activity size={16} className="text-status-success" />
                Service Health
              </h3>
            </div>
            {isLoading ? <LoadingSkeleton className="h-40 w-full" /> : <ServiceHealth incidents={incidents || []} />}
          </Card>

          <Card>
            <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-3">Quick Actions</h3>
            <QuickActions />
          </Card>
        </div>
      </div>
    </div>
  );
}