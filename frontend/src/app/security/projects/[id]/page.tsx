"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, FolderGit2, GitCompareArrows, AlertTriangle, RefreshCw, PlusCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSecurityProject, useCompareScans, useRerunSecurityScan } from "@/lib/hooks";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Select from "@/components/ui/Select";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";

const statusVariant: Record<string, "warn" | "success" | "danger" | "neutral"> = {
  queued: "warn", running: "warn", completed: "success", failed: "danger",
};

const severityVariant: Record<string, "danger" | "warn" | "info" | "neutral"> = {
  critical: "danger", high: "warn", medium: "info", low: "neutral", informational: "neutral",
};

const gradeColor: Record<string, string> = {
  A: "text-status-success", B: "text-accent", C: "text-status-high", D: "text-status-high", F: "text-status-critical",
};

export default function SecurityProjectDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { data: project, isLoading, isError } = useSecurityProject(params.id);
  const [baseId, setBaseId] = useState("");
  const [targetId, setTargetId] = useState("");
  const rerun = useRerunSecurityScan();

  const scans = project?.scans ?? [];
  const scanOptions = scans.map((s) => ({
    value: s.id,
    label: `${new Date(s.created_at).toLocaleDateString()} · ${s.status} · ${s.score ?? "—"}/100`,
  }));

  const compare = useCompareScans(params.id, baseId, targetId);

  const stack = project?.tech_stack && typeof project.tech_stack === "object"
    ? project.tech_stack as { language?: string; framework?: string; package_managers?: { manager: string }[] }
    : null;

  if (isLoading) return <LoadingSkeleton className="h-64 w-full rounded-lg" />;

  if (isError || !project) {
    return (
      <Card className="text-center py-16">
        <AlertTriangle size={24} className="mx-auto mb-3 text-text-tertiary" />
        <h2 className="text-[16px] font-semibold mb-1">Project not found</h2>
        <Link href="/security/projects"><Button variant="secondary" size="sm" className="mt-4">Back to Projects</Button></Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4 border-b border-border-soft pb-4">
        <Link href="/security/projects" className="inline-flex items-center gap-2 text-[13px] text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft size={14} /> Back to Projects
        </Link>
        <Button variant="primary" size="sm" onClick={() => router.push("/security/new")}>
          <PlusCircle size={14} /> New Scan
        </Button>
      </div>

      <div className="bg-surface-base border border-border-soft rounded-lg p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <FolderGit2 size={20} className="text-accent" />
              <h1 className="text-[20px] font-semibold text-text-primary">{project.name || project.source_ref}</h1>
              <Badge variant="neutral">{project.source_type}</Badge>
            </div>
            <p className="text-[13px] text-text-secondary font-mono">{project.source_ref}</p>
            {stack && (
              <div className="flex items-center gap-2 mt-3 text-[12px] text-text-tertiary">
                <span className="px-2 py-0.5 bg-surface-elevated border border-border-strong rounded">
                   {[stack.language, stack.framework].filter(Boolean).join(" · ") || "Stack unknown"}
                </span>
              </div>
            )}
          </div>
          {project.last_scan_grade && (
            <div className="text-right bg-surface-elevated p-4 rounded-lg border border-border-strong">
              <div className="text-[11px] uppercase tracking-wider text-text-secondary mb-1">Latest Score</div>
              <div className="flex items-baseline gap-2 justify-end">
                 <div className={`font-mono text-[32px] font-bold leading-none ${gradeColor[project.last_scan_grade]}`}>
                   {project.last_scan_grade}
                 </div>
                 <div className="text-[14px] text-text-secondary font-mono">
                   {project.last_scan_score ?? "—"}/100
                 </div>
              </div>
              <div className="mt-2 text-[11px] font-mono text-text-tertiary flex justify-end gap-2 items-center">
                 <Badge variant={statusVariant[project.last_scan_status!] || "neutral"}>{project.last_scan_status}</Badge>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card className="flex flex-col h-[500px]">
          <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-2 flex-shrink-0">Scan History</h3>
          <div className="flex-1 overflow-y-auto pr-2">
            {scans.length === 0 ? (
              <div className="text-center py-16 text-text-tertiary text-[13px]">No scans yet.</div>
            ) : (
              <div className="space-y-2">
                {scans.map((s) => (
                  <div key={s.id} className="flex items-center gap-4 px-3 py-2.5 rounded-md bg-surface-elevated border border-border-soft hover:border-border-strong transition-colors">
                    <button
                      onClick={() => router.push(`/security/scans/${s.id}`)}
                      className="flex-1 min-w-0 text-left group"
                    >
                      <div className="text-[13px] font-medium text-text-primary group-hover:text-accent transition-colors truncate">
                        {new Date(s.created_at).toLocaleString()}
                      </div>
                      <div className="text-[11px] text-text-secondary font-mono mt-0.5">
                        {s.total_files} files · {s.finding_count} findings
                      </div>
                    </button>
                    {s.score !== null && <span className={`font-mono text-[14px] font-semibold tabular-nums ${gradeColor[s.grade ?? "F"]}`}>{s.score}</span>}
                    <Badge variant={statusVariant[s.status] || "neutral"}>{s.status}</Badge>
                    <button
                      title="Re-run this scan"
                      disabled={rerun.isPending || s.status === "queued" || s.status === "running"}
                      onClick={() => rerun.mutate(s.id)}
                      className="p-1.5 rounded bg-surface-base border border-border-strong text-text-secondary hover:text-accent hover:border-accent transition-colors disabled:opacity-40"
                    >
                      {rerun.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card className="flex flex-col h-[500px]">
          <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-2 flex items-center gap-2 flex-shrink-0">
            <GitCompareArrows size={16} className="text-accent" />
            Compare Scans
          </h3>
          <div className="grid grid-cols-2 gap-3 mb-4 flex-shrink-0">
            <Select options={[{ value: "", label: "Base scan..." }, ...scanOptions]} value={baseId} onChange={(e) => setBaseId(e.target.value)} />
            <Select options={[{ value: "", label: "Target scan..." }, ...scanOptions]} value={targetId} onChange={(e) => setTargetId(e.target.value)} />
          </div>

          <div className="flex-1 overflow-y-auto bg-page-bg rounded-md border border-border-soft p-3">
             {compare.data ? (
               <div className="space-y-4 text-[13px]">
                 <div className="flex items-center gap-2 flex-wrap pb-3 border-b border-border-soft">
                   <span className="px-2 py-0.5 rounded bg-status-critical/10 text-status-critical font-mono text-[11px]">+{compare.data.added.length} Added</span>
                   <span className="px-2 py-0.5 rounded bg-status-success/10 text-status-success font-mono text-[11px] border border-status-success/20">-{compare.data.removed.length} Removed</span>
                   <span className="px-2 py-0.5 rounded bg-status-high/10 text-status-high font-mono text-[11px] border border-status-high/20">~{compare.data.status_changed.length} Changed</span>
                   <span className="text-[11px] text-text-tertiary ml-auto">{compare.data.unchanged} unchanged</span>
                 </div>

                 {(compare.data.added.length > 0 || compare.data.removed.length > 0 || compare.data.status_changed.length > 0) ? (
                   <div className="space-y-1.5">
                     {compare.data.added.map((i) => (
                       <div key={i.key} className="flex items-center gap-2 px-3 py-2 rounded bg-status-critical/5 border border-status-critical/10">
                         <span className="text-status-critical font-mono font-bold">+</span>
                         <span className="flex-1 truncate text-text-primary text-[12px]">{i.title || i.key}</span>
                         <Badge variant={severityVariant[i.severity] || "neutral"}>{i.severity}</Badge>
                       </div>
                     ))}
                     {compare.data.status_changed.map((i) => (
                       <div key={i.key} className="flex items-center gap-2 px-3 py-2 rounded bg-status-high/5 border border-status-high/10">
                         <span className="text-status-high font-mono font-bold">~</span>
                         <span className="flex-1 truncate text-text-primary text-[12px]">{i.title || i.key}</span>
                         <span className="font-mono text-text-secondary text-[11px]">{i.base_status} &rarr; {i.target_status}</span>
                       </div>
                     ))}
                     {compare.data.removed.map((i) => (
                       <div key={i.key} className="flex items-center gap-2 px-3 py-2 rounded bg-status-success/5 border border-status-success/10">
                         <span className="text-status-success font-mono font-bold">-</span>
                         <span className="flex-1 truncate text-text-primary text-[12px] line-through opacity-70">{i.title || i.key}</span>
                       </div>
                     ))}
                   </div>
                 ) : (
                    <div className="text-center py-8 text-text-tertiary text-[12px]">No differences found between these scans.</div>
                 )}
               </div>
             ) : compare.isLoading ? (
               <div className="flex items-center justify-center h-full text-text-secondary text-[13px] gap-2">
                 <Loader2 size={14} className="animate-spin" /> Comparing...
               </div>
             ) : (
               <div className="flex items-center justify-center h-full text-text-tertiary text-[13px] text-center px-4">
                 Select a base scan and a target scan from the dropdowns above to see what vulnerabilities were added, removed, or changed.
               </div>
             )}
          </div>
        </Card>
      </div>
    </div>
  );
}
