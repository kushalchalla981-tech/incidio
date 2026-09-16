cat << 'INNER_EOF' > frontend/src/app/security/scans/[id]/page.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, ShieldCheck, Loader2, RefreshCw } from "lucide-react";
import { useSecurityScan, useRerunSecurityScan, useUpdateFindingStatus } from "@/lib/hooks";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import type { ScanFinding, FindingStatus } from "@/lib/types";

const severityVariant: Record<string, "danger" | "warn" | "info" | "neutral"> = {
  critical: "danger", high: "warn", medium: "info", low: "neutral", informational: "neutral",
};

const statusVariant: Record<string, "success" | "warn" | "danger" | "neutral"> = {
  completed: "success", failed: "danger", running: "warn", queued: "neutral",
};

const findingStatuses: FindingStatus[] = ["open", "resolved", "accepted", "false_positive"];

function FindingRow({ finding, scanId }: { finding: ScanFinding; scanId: string }) {
  const [expanded, setExpanded] = useState(false);
  const update = useUpdateFindingStatus();

  return (
    <div className="border-b border-border-soft last:border-b-0">
      <div className="flex items-start gap-4 px-4 py-3 hover:bg-surface-elevated transition-colors cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <Badge variant={severityVariant[finding.severity] || "neutral"} className="mt-0.5">{finding.severity}</Badge>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-text-primary">{finding.title || finding.description}</div>
          <div className="text-[11px] text-text-tertiary font-mono mt-1 truncate">
            {finding.file}{finding.line ? `:${finding.line}` : ""} • {finding.category} • CWE: {finding.cwe || "None"}
          </div>
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
           <select
              className="appearance-none px-2 py-1 rounded border border-border-strong bg-surface-base text-[11px] text-text-secondary outline-none"
              value={finding.status}
              onChange={(e) => update.mutate({ id: finding.id, update: { status: e.target.value as FindingStatus } })}
            >
              {findingStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-1 bg-surface-elevated/30">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div>
                <h4 className="text-[11px] uppercase tracking-wide text-text-secondary font-mono mb-1">Description</h4>
                <p className="text-[13px] text-text-primary leading-relaxed">{finding.description}</p>
              </div>
              {finding.remediation && (
                <div>
                  <h4 className="text-[11px] uppercase tracking-wide text-text-secondary font-mono mb-1">Remediation</h4>
                  <p className="text-[13px] text-status-success leading-relaxed">{finding.remediation}</p>
                </div>
              )}
            </div>
            <div>
               <h4 className="text-[11px] uppercase tracking-wide text-text-secondary font-mono mb-1">Evidence</h4>
               <pre className="p-3 bg-page-bg border border-border-soft rounded-md text-[11px] text-text-secondary font-mono overflow-x-auto whitespace-pre-wrap">
                  {finding.evidence || "No exact evidence available."}
               </pre>
               {finding.impact && (<div className="mt-3"><h4 className="text-[11px] uppercase tracking-wide text-text-secondary font-mono mb-1">Impact</h4><p className="text-[13px] text-text-primary leading-relaxed">{finding.impact}</p></div>)}
               {finding.attack_scenario && (<div className="mt-3"><h4 className="text-[11px] uppercase tracking-wide text-text-secondary font-mono mb-1">Attack Scenario</h4><p className="text-[13px] text-text-primary leading-relaxed">{finding.attack_scenario}</p></div>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SecurityScanDetailPage({ params }: { params: { id: string } }) {
  const { data: scan, isLoading, isError, error } = useSecurityScan(params.id);
  const rerun = useRerunSecurityScan();
  const isNotFound = isError && (error as { status?: number } | null)?.status === 404;

  if (isLoading) return <LoadingSkeleton className="h-64 w-full rounded-lg" />;
  if (isNotFound) return <Card className="text-center py-16"><AlertTriangle className="mx-auto mb-3 text-text-tertiary" />Scan not found.</Card>;
  if (!scan) return null;

  const criticalCount = scan.findings.filter(f => f.severity === 'critical' && f.status === 'open').length;
  const highCount = scan.findings.filter(f => f.severity === 'high' && f.status === 'open').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4 border-b border-border-soft pb-4">
        <Link href="/security/history" className="inline-flex items-center gap-2 text-[13px] text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft size={14} /> Back to History
        </Link>
        <div className="flex items-center gap-2">
          {scan.source_type !== "zip" && (
            <Button
              variant="secondary"
              size="sm"
              disabled={rerun.isPending || scan.status === "queued" || scan.status === "running"}
              onClick={() => rerun.mutate(scan.id)}
            >
              {rerun.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Re-run
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <div className="flex items-center gap-3 mb-4">
              <ShieldCheck size={20} className="text-accent" />
              <h1 className="text-[16px] font-semibold truncate text-text-primary">{scan.name || scan.repo_url}</h1>
            </div>
            <div className="space-y-3 text-[13px]">
               <div className="flex justify-between"><span className="text-text-tertiary">Status</span><Badge variant={statusVariant[scan.status] || "neutral"}>{scan.status}</Badge></div>
               <div className="flex justify-between"><span className="text-text-tertiary">Source</span><span className="text-text-primary">{scan.source_type}</span></div>
               <div className="flex justify-between"><span className="text-text-tertiary">Files Scanned</span><span className="text-text-primary font-mono tabular-nums">{scan.total_files}</span></div>
               <div className="flex justify-between"><span className="text-text-tertiary">Started</span><span className="text-text-primary tabular-nums">{new Date(scan.created_at).toLocaleString()}</span></div>
            </div>
          </Card>

          <Card>
            <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-2 text-text-primary">Risk Posture</h3>
            {scan.status === "completed" ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-center">
                  <div className="bg-surface-elevated border border-border-strong rounded-md p-3">
                     <div className="text-[20px] font-mono font-semibold text-status-critical tabular-nums">{criticalCount}</div>
                     <div className="text-[11px] text-text-tertiary uppercase tracking-wide mt-1">Critical</div>
                  </div>
                  <div className="bg-surface-elevated border border-border-strong rounded-md p-3">
                     <div className="text-[20px] font-mono font-semibold text-status-high tabular-nums">{highCount}</div>
                     <div className="text-[11px] text-text-tertiary uppercase tracking-wide mt-1">High</div>
                  </div>
                </div>
                {scan.summary && <p className="text-[13px] text-text-secondary leading-relaxed pt-2 border-t border-border-soft">{scan.summary}</p>}
                {scan.metadata?.sub_scores && typeof scan.metadata.sub_scores === "object" && (
                   <div className="grid grid-cols-3 gap-2 mt-4 text-center border-t border-border-soft pt-4">
                     {Object.entries(scan.metadata.sub_scores as Record<string, number>).map(([key, value]) => (
                        <div key={key} className="bg-surface-base border border-border-soft rounded p-2">
                          <div className="text-[14px] font-mono font-semibold text-text-primary tabular-nums">{Math.round(value as number)}</div>
                          <div className="text-[10px] text-text-tertiary uppercase tracking-wide mt-0.5">{key.replace(/_score$/, "").replace(/_/g, " ")}</div>
                        </div>
                     ))}
                   </div>
                )}
              </div>
            ) : scan.status === "failed" ? (
              <div className="text-[13px] text-status-critical">{scan.error || "Scan failed"}</div>
            ) : (
              <div className="text-[13px] text-text-secondary flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Scanning in progress...</div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Card className="p-0 overflow-hidden h-full flex flex-col">
            <div className="p-4 border-b border-border-strong flex items-center justify-between bg-surface-base">
               <h3 className="text-[15px] font-semibold text-text-primary">Actionable Findings</h3>
               <span className="text-[12px] text-text-secondary font-mono bg-surface-elevated px-2 py-0.5 rounded border border-border-soft">{scan.findings.length} Total</span>
            </div>
            <div className="flex-1 overflow-y-auto bg-page-bg">
              {scan.findings.length === 0 ? (
                <div className="text-center py-16 text-text-tertiary text-[13px]">No findings discovered in this scan.</div>
              ) : (
                <div className="flex flex-col">
                  {scan.findings.map((f) => <FindingRow key={f.id} finding={f} scanId={scan.id} />)}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
INNER_EOF
