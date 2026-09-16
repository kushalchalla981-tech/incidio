"use client";

import { useState } from "react";
import { Plus, ArrowRight, Inbox } from "lucide-react";
import { useIncidents } from "@/lib/hooks";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import PageHeader from "@/components/shared/PageHeader";
import EmptyState from "@/components/shared/EmptyState";
import ErrorState from "@/components/shared/ErrorState";
import { SeverityBadge, StatusBadge } from "@/components/shared/StatusBadge";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";

export default function IncidentsPage() {
  const [sevFilter, setSevFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { data: incidents, isLoading, isError, error } = useIncidents({
    severity: sevFilter || undefined,
    status: statusFilter || undefined,
  });

  const filtered = incidents || [];
  const openCount = filtered.filter((i) => i.status === "open" || i.status === "investigating").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Incidents"
        description="Track, investigate, and resolve incidents across your services."
        badge={openCount > 0 ? { label: `${openCount} active`, tone: "severity" } : undefined}
        actions={
          <Link href="/incidents/new">
            <Button variant="primary" size="sm">
              <Plus size={14} /> New Incident
            </Button>
          </Link>
        }
      />

      <div className="flex items-center gap-3 flex-wrap">
        <Select
          className="w-40"
          options={[
            { value: "", label: "All Severities" },
            { value: "critical", label: "Critical" },
            { value: "high", label: "High" },
            { value: "medium", label: "Medium" },
            { value: "low", label: "Low" },
          ]}
          value={sevFilter}
          onChange={(e) => setSevFilter(e.target.value)}
        />
        <Select
          className="w-40"
          options={[
            { value: "", label: "All Statuses" },
            { value: "open", label: "Open" },
            { value: "investigating", label: "Investigating" },
            { value: "resolved", label: "Resolved" },
            { value: "closed", label: "Closed" },
          ]}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        />
        {(sevFilter || statusFilter) && (
          <Button variant="ghost" size="sm" onClick={() => { setSevFilter(""); setStatusFilter(""); }}>
            Clear Filters
          </Button>
        )}
      </div>

      {isError && <ErrorState title="Failed to load incidents" message={error?.message} />}

      <div className="border border-border-soft rounded-lg overflow-hidden bg-surface-base shadow-sm">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <LoadingSkeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No incidents found"
            description={sevFilter || statusFilter ? "Try adjusting your filters." : "Declare an incident to get started."}
            action={
              sevFilter || statusFilter ? undefined : (
                <Link href="/incidents/new">
                  <Button variant="primary" size="sm">
                    <Plus size={14} /> New Incident
                  </Button>
                </Link>
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px] border-collapse min-w-[640px]">
              <thead>
                <tr className="border-b border-border-soft bg-surface-sunken">
                  <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Incident</th>
                  <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Severity</th>
                  <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Status</th>
                  <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium hidden md:table-cell">Service</th>
                  <th className="py-2.5 px-4 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Started</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inc) => (
                  <tr key={inc.id} className="border-b border-border-soft last:border-b-0 hover:bg-accent-soft/50 transition-colors group">
                    <td className="py-3 px-4">
                      <Link href={`/incidents/${inc.id}`} className="block">
                        <div className="font-semibold text-text-primary group-hover:text-accent transition-colors flex items-center gap-2">
                          <span className="truncate">{inc.title}</span>
                          <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                        </div>
                        <div className="font-mono text-[11px] text-text-tertiary mt-0.5">{inc.id}</div>
                      </Link>
                    </td>
                    <td className="py-3 px-4">
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={inc.status} />
                    </td>
                    <td className="py-3 px-4 hidden md:table-cell text-text-secondary font-mono text-[12px]">{inc.affected_services?.[0] || "—"}</td>
                    <td className="py-3 px-4 text-right text-text-secondary tabular-nums text-[13px]">
                      {new Date(inc.start_time).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
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