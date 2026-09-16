"use client";

import { useRouter } from "next/navigation";
import { ShieldAlert, PlusCircle, RefreshCw, ArrowRight, ShieldCheck } from "lucide-react";
import { useSecurityProjects, useSecurityScans, useSecurityFindings } from "@/lib/hooks";
import KPI from "@/components/ui/KPI";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/shared/PageHeader";

const severityVariant: Record<string, "danger" | "warn" | "info" | "neutral"> = {
  critical: "danger", high: "warn", medium: "info", low: "neutral", informational: "neutral",
};

export default function SecurityDashboardPage() {
  const router = useRouter();
  const { data: projects } = useSecurityProjects();
  const { data: scans } = useSecurityScans();
  const { data: findings } = useSecurityFindings();

  const activeScans = (scans || []).filter((s) => s.status === "queued" || s.status === "running").length;
  const openFindings = (findings || []).filter((f) => f.status === "open");
  const openCritical = openFindings.filter((f) => f.severity === "critical").length;
  const openHigh = openFindings.filter((f) => f.severity === "high").length;

  const recentScans = [...(scans || [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  ).slice(0, 5);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Security Checker"
        description="Scan repositories and live apps for vulnerabilities, then triage findings."
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => router.refresh()}>
              <RefreshCw size={14} /> Refresh
            </Button>
            <Button variant="primary" size="sm" onClick={() => router.push("/security/new")}>
              <PlusCircle size={14} /> New Scan
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Projects Monitored" value={projects?.length ?? 0} />
        <KPI
          label="Risk Posture (Critical)"
          value={openCritical}
          change={{ value: `${openHigh} high severity`, down: openCritical > 0 || openHigh > 0 }}
        />
        <KPI label="Total Open Findings" value={openFindings.length} />
        <KPI
          label="Active Scans"
          value={activeScans}
          change={{ value: activeScans > 0 ? "in progress" : "idle", up: activeScans > 0 }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
            <h3 className="text-[14px] font-semibold flex items-center gap-2">
              <ShieldCheck size={16} className="text-accent" />
              Recent Scans
            </h3>
            <a href="/security/history" className="text-[12px] text-accent hover:underline">View History</a>
          </div>
          {recentScans.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-8 text-text-tertiary">
              <p className="text-[13px]">No scans recorded.</p>
            </div>
          ) : (
            <div className="space-y-2 flex-1">
              {recentScans.map((s) => (
                <div key={s.id} onClick={() => router.push(`/security/scans/${s.id}`)} className="flex items-center justify-between p-3 rounded-md bg-surface-elevated border border-border-soft cursor-pointer hover:border-border-strong transition-colors">
                  <div className="min-w-0 pr-4">
                    <div className="text-[13px] font-medium text-text-primary truncate">{s.repo_url}</div>
                    <div className="text-[11px] text-text-secondary font-mono mt-0.5">{new Date(s.created_at).toLocaleString()}</div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Badge variant={s.status === 'completed' ? 'success' : s.status === 'failed' ? 'danger' : 'warn'}>{s.status}</Badge>
                    <ArrowRight size={14} className="text-text-tertiary" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="flex flex-col">
          <div className="flex items-center justify-between mb-4 border-b border-border-soft pb-3">
            <h3 className="text-[14px] font-semibold flex items-center gap-2">
              <ShieldAlert size={16} className="text-status-critical" />
              Top Actionable Findings
            </h3>
            <a href="/security/findings" className="text-[12px] text-accent hover:underline">View All</a>
          </div>
          {openFindings.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-8 text-text-tertiary">
              <p className="text-[13px]">No open findings.</p>
            </div>
          ) : (
            <div className="space-y-2 flex-1">
              {openFindings.sort((a) => (a.severity === 'critical' ? -1 : 1)).slice(0, 5).map((f) => (
                <div key={f.id} className="p-3 rounded-md bg-surface-elevated border border-border-soft">
                  <div className="flex items-start justify-between gap-3 mb-1.5">
                    <div className="text-[13px] font-medium text-text-primary line-clamp-2">{f.title || f.description}</div>
                    <Badge variant={severityVariant[f.severity] || "neutral"}>{f.severity}</Badge>
                  </div>
                  <div className="text-[11px] text-text-tertiary font-mono truncate">{f.file}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
