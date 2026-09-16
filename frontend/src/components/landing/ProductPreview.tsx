"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldCheck, ArrowRight } from "lucide-react";
import clsx from "clsx";
import { useIncidents, useSecurityScans } from "@/lib/hooks";
import LiveBadge from "@/components/shared/LiveBadge";
import { SeverityBadge, StatusBadge } from "@/components/shared/StatusBadge";

type Tab = "incidents" | "security";

function gradeColor(grade?: string | null) {
  if (!grade) return "text-text-tertiary";
  if (grade === "A" || grade === "B") return "text-status-success";
  if (grade === "C") return "text-status-high";
  return "text-status-critical";
}

export default function ProductPreview() {
  const [tab, setTab] = useState<Tab>("incidents");
  const { data: incidents } = useIncidents({ limit: 8 });
  const { data: scans } = useSecurityScans();

  const sortedIncidents = [...(incidents || [])].sort(
    (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
  ).slice(0, 4);

  const recentScans = [...(scans || [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  ).slice(0, 4);

  return (
    <div className="bg-surface-base border border-border-strong rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-soft">
        <div className="flex items-center gap-1 bg-surface-sunken rounded-lg p-1">
          <button
            onClick={() => setTab("incidents")}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium transition-colors duration-150",
              tab === "incidents" ? "bg-surface-base text-text-primary shadow-sm border border-border-soft" : "text-text-secondary hover:text-text-primary"
            )}
          >
            <AlertTriangle size={13} className="text-accent" /> Incidents
          </button>
          <button
            onClick={() => setTab("security")}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium transition-colors duration-150",
              tab === "security" ? "bg-surface-base text-text-primary shadow-sm border border-border-soft" : "text-text-secondary hover:text-text-primary"
            )}
          >
            <ShieldCheck size={13} className="text-security" /> Security
          </button>
        </div>
        <LiveBadge label="Live" />
      </div>

      <div className="p-2">
        {tab === "incidents" ? (
          sortedIncidents.length === 0 ? (
            <div className="py-12 px-6 text-center text-[13px] text-text-secondary">
              No incidents yet. Declare one from the dashboard.
            </div>
          ) : (
            <div className="divide-y divide-border-soft">
              {sortedIncidents.map((inc) => (
                <Link key={inc.id} href={`/incidents/${inc.id}`} className="flex items-center gap-3 px-2 py-2.5 rounded-md hover:bg-surface-sunken transition-colors duration-150">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-text-primary truncate">{inc.title}</div>
                    <div className="text-[11px] text-text-tertiary font-mono mt-0.5 truncate">{inc.affected_services?.[0] || "no service"}</div>
                  </div>
                  <SeverityBadge severity={inc.severity} />
                  <StatusBadge status={inc.status} />
                </Link>
              ))}
            </div>
          )
        ) : recentScans.length === 0 ? (
          <div className="flex flex-col items-center py-12 px-6 text-center">
            <p className="text-[13px] text-text-secondary">No scans yet.</p>
            <Link href="/security/new" className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-accent hover:underline">
              Run your first scan <ArrowRight size={13} />
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-border-soft">
            {recentScans.map((s) => (
              <Link key={s.id} href={`/security/scans/${s.id}`} className="flex items-center gap-3 px-2 py-2.5 rounded-md hover:bg-surface-sunken transition-colors duration-150">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium text-text-primary truncate">{s.name || s.source_ref || s.repo_url}</div>
                  <div className="text-[11px] text-text-tertiary font-mono mt-0.5">{s.source_type} · {new Date(s.created_at).toLocaleDateString()}</div>
                </div>
                {s.score !== null && s.score !== undefined && (
                  <span className={clsx("font-mono text-[14px] font-semibold tabular-nums", gradeColor(s.grade))}>{s.score}</span>
                )}
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-surface-sunken text-text-secondary border border-border-soft capitalize">
                  {s.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}