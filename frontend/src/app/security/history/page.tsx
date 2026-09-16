"use client";

import { useRouter } from "next/navigation";
import { History, ArrowRight } from "lucide-react";
import { useSecurityScans } from "@/lib/hooks";
import Badge from "@/components/ui/Badge";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import PageHeader from "@/components/shared/PageHeader";
import EmptyState from "@/components/shared/EmptyState";

const statusVariant: Record<string, "warn" | "success" | "danger" | "neutral"> = {
  queued: "warn", running: "warn", completed: "success", failed: "danger",
};

export default function SecurityHistoryPage() {
  const router = useRouter();
  const { data: scans, isLoading } = useSecurityScans();
  const sorted = [...(scans ?? [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scan History"
        description="Every scan run across all projects."
        badge={{ label: `${sorted.length} records`, tone: "neutral" }}
      />

      <div className="border border-border-soft rounded-lg overflow-hidden bg-surface-base">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => <LoadingSkeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : sorted.length === 0 ? (
          <EmptyState icon={History} title="No scans yet" description="Run your first security scan to start building scan history." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px] border-collapse min-w-[680px]">
            <thead>
              <tr className="border-b border-border-soft bg-surface-sunken">
                <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Scan Target</th>
                <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Status</th>
                <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Files</th>
                <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Findings</th>
                <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => router.push(`/security/scans/${s.id}`)}
                  className="border-b border-border-soft last:border-b-0 hover:bg-surface-elevated cursor-pointer transition-colors group"
                >
                  <td className="py-3 px-4">
                    <div className="font-medium text-text-primary group-hover:text-accent transition-colors flex items-center gap-2 truncate max-w-[300px]">
                      {s.name || s.source_ref || s.repo_url}
                      <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <div className="text-[11px] text-text-tertiary font-mono mt-0.5">{s.id}</div>
                  </td>
                  <td className="py-3 px-4"><Badge variant={statusVariant[s.status] || "neutral"}>{s.status}</Badge></td>
                  <td className="py-3 px-4 font-mono text-text-secondary">{s.total_files}</td>
                  <td className="py-3 px-4 font-mono text-text-secondary">{s.finding_count}</td>
                  <td className="py-3 px-4 text-right text-text-secondary tabular-nums">
                    {new Date(s.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
