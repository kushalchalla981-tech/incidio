"use client";

import { useState } from "react";
import { ListChecks } from "lucide-react";
import { useSecurityFindings, useUpdateFindingStatus } from "@/lib/hooks";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import type { ScanFinding, FindingStatus } from "@/lib/types";

const severityVariant: Record<string, "danger" | "warn" | "info" | "neutral"> = {
  critical: "danger", high: "warn", medium: "info", low: "neutral", informational: "neutral",
};

const findingStatusVariant: Record<string, "warn" | "success" | "info" | "neutral"> = {
  open: "warn", resolved: "success", accepted: "info", false_positive: "neutral",
};

const findingStatuses: FindingStatus[] = ["open", "resolved", "accepted", "false_positive"];

function FindingRow({ finding }: { finding: ScanFinding }) {
  const [expanded, setExpanded] = useState(false);
  const update = useUpdateFindingStatus();

  return (
    <div className="border-b border-border-soft last:border-b-0">
      <div className="flex items-start gap-4 px-4 py-3 hover:bg-surface-elevated transition-colors cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <Badge variant={severityVariant[finding.severity] || "neutral"} className="mt-0.5 w-20 justify-center">{finding.severity}</Badge>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-text-primary group-hover:text-accent transition-colors truncate">
            {finding.title || finding.rule_id || finding.description}
          </div>
          <div className="text-[11px] text-text-tertiary font-mono mt-1 truncate">
            {finding.file}{finding.line ? `:${finding.line}` : ""} • {finding.source} • CWE {finding.cwe || "—"}
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <Badge variant={findingStatusVariant[finding.status] || "neutral"} className="w-24 justify-center">{finding.status}</Badge>
          <select
            className="appearance-none px-2 py-1.5 rounded border border-border-strong bg-surface-base text-[11px] text-text-secondary outline-none cursor-pointer hover:border-accent transition-colors"
            value={finding.status}
            disabled={update.isPending}
            onChange={(e) => update.mutate({ id: finding.id, update: { status: e.target.value as FindingStatus } })}
          >
            {findingStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      {expanded && (
        <div className="px-4 pb-4 pt-1 bg-surface-elevated/30">
          <div className="space-y-3">
             <p className="text-[13px] text-text-primary leading-relaxed">{finding.description}</p>
             {finding.remediation && <p className="text-[13px] text-status-success leading-relaxed">{finding.remediation}</p>}
             <pre className="p-3 bg-page-bg border border-border-soft rounded-md text-[11px] text-text-secondary font-mono overflow-x-auto whitespace-pre-wrap">
               {finding.evidence || "No exact evidence available."}
             </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SecurityFindingsPage() {
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("open");
  const { data: findings, isLoading } = useSecurityFindings({
    severity: severity || undefined,
    status: status || undefined,
  });

  const openCount = (findings ?? []).filter((f) => f.status === "open").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4 border-b border-border-soft pb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-[20px] font-semibold text-text-primary">Global Findings</h1>
          {openCount > 0 && <Badge variant="warn">{openCount} open</Badge>}
        </div>
        <div className="flex items-center gap-3">
          <Select
            className="w-[140px]"
            options={[
              { value: "", label: "All Severities" },
              { value: "critical", label: "Critical" },
              { value: "high", label: "High" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low" },
              { value: "informational", label: "Info" },
            ]}
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
          />
          <Select
            className="w-[140px]"
            options={[
              { value: "", label: "All Statuses" },
              { value: "open", label: "Open" },
              { value: "resolved", label: "Resolved" },
              { value: "accepted", label: "Accepted" },
              { value: "false_positive", label: "False Positive" },
            ]}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          />
          {(severity || status !== "open") && (
             <Button variant="ghost" size="sm" onClick={() => { setSeverity(""); setStatus(""); }}>Clear</Button>
          )}
        </div>
      </div>

      <div className="border border-border-soft rounded-lg overflow-hidden bg-surface-base">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => <LoadingSkeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : !findings || findings.length === 0 ? (
          <div className="text-center py-16 text-text-secondary">
            <ListChecks size={24} className="mx-auto mb-3 text-text-tertiary" />
            <p className="text-[13px]">No findings match the current filters.</p>
          </div>
        ) : (
          <div className="flex flex-col">
            {findings.map((f) => <FindingRow key={f.id} finding={f} />)}
          </div>
        )}
      </div>
    </div>
  );
}
