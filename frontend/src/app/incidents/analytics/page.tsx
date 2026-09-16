"use client";

import { useMemo } from "react";
import { TrendingUp, Clock, Activity, AlertTriangle } from "lucide-react";
import Card from "@/components/ui/Card";
import KPI from "@/components/ui/KPI";
import PageHeader from "@/components/shared/PageHeader";
import ErrorState from "@/components/shared/ErrorState";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import IncidentTrend from "@/components/dashboard/IncidentTrend";
import { useIncidents } from "@/lib/hooks";

function minutesBetween(a: string, b?: string | null) {
  if (!b) return null;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return ms >= 0 ? ms / 60000 : null;
}

const SEVERITY_META = [
  { key: "critical", label: "Critical", color: "var(--status-critical)" },
  { key: "high", label: "High", color: "var(--status-high)" },
  { key: "medium", label: "Medium", color: "var(--status-medium)" },
  { key: "low", label: "Low", color: "var(--status-low)" },
] as const;

export default function AnalyticsPage() {
  const { data: incidents, isLoading, isError, error } = useIncidents();

  const metrics = useMemo(() => {
    const list = incidents || [];
    const resolved = list.filter((i) => (i.status === "resolved" || i.status === "closed") && i.end_time);
    const mttrs = resolved.map((i) => minutesBetween(i.start_time, i.end_time)).filter((m): m is number => m !== null);
    const avgMttr = mttrs.length ? mttrs.reduce((a, b) => a + b, 0) / mttrs.length : null;

    const active = list.filter((i) => i.status === "open" || i.status === "investigating").length;
    const severity = { critical: 0, high: 0, medium: 0, low: 0 };
    list.forEach((i) => { if (i.severity in severity) (severity as Record<string, number>)[i.severity] += 1; });

    const perService = new Map<string, number>();
    list.forEach((i) => (i.affected_services || []).forEach((s) => perService.set(s, (perService.get(s) || 0) + 1)));
    const topServices = Array.from(perService.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6);

    const byWeek = new Map<string, number>();
    list.forEach((i) => {
      const d = new Date(i.start_time);
      const w = new Date(d.getTime() - ((d.getDay() + 6) % 7) * 24 * 60 * 60 * 1000);
      const key = w.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      byWeek.set(key, (byWeek.get(key) || 0) + 1);
    });
    const weekly = Math.round(list.length / Math.max(byWeek.size, 1) * 10) / 10;
    const peak = Array.from(byWeek.entries()).sort((a, b) => b[1] - a[1])[0];

    return { avgMttr, active, severity, topServices, weekly, peak, total: list.length };
  }, [incidents]);

  if (isError) return <ErrorState title="Failed to load analytics" message={error?.message} />;

  const maxSev = Math.max(...Object.values(metrics.severity), 1);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Computed live from your incident data."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI
          label="Mean Time to Resolve"
          value={metrics.avgMttr ? Math.round(metrics.avgMttr / 60 * 10) / 10 : 0}
          decimals={metrics.avgMttr && metrics.avgMttr >= 60 ? 1 : 0}
          suffix={metrics.avgMttr ? "h" : ""}
          loading={isLoading}
          change={{ value: metrics.avgMttr ? "Across resolved incidents" : "No resolved incidents yet", up: !!metrics.avgMttr }}
        />
        <KPI
          label="Active Incidents"
          value={metrics.active}
          loading={isLoading}
          change={{ value: "Open or investigating", up: true }}
        />
        <KPI
          label="Weekly Frequency"
          value={metrics.weekly}
          decimals={1}
          loading={isLoading}
          change={{ value: metrics.peak ? `Peak week: ${metrics.peak[0]} (${metrics.peak[1]})` : "No data yet", up: true }}
        />
        <KPI
          label="Total Incidents"
          value={metrics.total}
          loading={isLoading}
          change={{ value: "In this workspace", up: true }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
            <h3 className="text-[14px] font-semibold flex items-center gap-2">
              <TrendingUp size={16} className="text-accent" /> Incident Frequency
            </h3>
          </div>
          {isLoading ? (
            <LoadingSkeleton className="h-40 w-full" />
          ) : (
            <IncidentTrend incidents={incidents || []} days={14} />
          )}
        </Card>

        <Card>
          <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-status-critical" /> Severity Mix
          </h3>
          <div className="space-y-4">
            {SEVERITY_META.map(({ key, label, color }) => {
              const count = metrics.severity[key];
              return (
                <div key={key}>
                  <div className="flex items-center justify-between text-[13px] mb-1">
                    <span className="text-text-secondary">{label}</span>
                    <span className="font-semibold text-text-primary tabular-nums">{count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
                    <div
                      className="h-full rounded-full transition-[width] duration-500"
                      style={{ width: `${(count / maxSev) * 100}%`, backgroundColor: color }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-3 flex items-center gap-2">
          <Activity size={16} className="text-accent" /> Top Affected Services
        </h3>
        {isLoading ? (
          <LoadingSkeleton className="h-32 w-full" />
        ) : metrics.topServices.length === 0 ? (
          <p className="text-sm text-text-secondary py-6 text-center">No services tracked yet.</p>
        ) : (
          <div className="overflow-x-auto -mx-5 px-5">
            <table className="w-full text-[13px] min-w-[480px]">
              <thead>
                <tr>
                  <th className="text-left py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Service</th>
                  <th className="text-right py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Incidents</th>
                </tr>
              </thead>
              <tbody>
                {metrics.topServices.map(([service, count]) => (
                  <tr key={service} className="border-t border-border-soft">
                    <td className="py-2.5 font-mono text-text-primary">{service}</td>
                    <td className="py-2.5 text-right tabular-nums text-text-secondary">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="flex items-center justify-center gap-3 pb-2 text-text-tertiary">
        <Clock size={13} />
        <span className="text-[12px]">All metrics update automatically from live incident data.</span>
      </div>
    </div>
  );
}