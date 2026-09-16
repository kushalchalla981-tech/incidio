"use client";

import Link from "next/link";
import { ArrowLeft, AlertTriangle, RefreshCw, CheckCircle2, Zap } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useIncident } from "@/lib/hooks";
import { updateIncident } from "@/lib/api";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import ErrorState from "@/components/shared/ErrorState";
import { SeverityBadge, StatusBadge } from "@/components/shared/StatusBadge";
import { useState } from "react";

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <label className="text-[11px] text-text-tertiary uppercase font-mono tracking-wide">{label}</label>
      <p className={`mt-1 text-[13px] text-text-primary ${mono ? "font-mono text-[12px]" : ""}`}>{value || "—"}</p>
    </div>
  );
}

type TimelineEntry = {
  action: string;
  from?: string;
  to?: string;
  timestamp: string;
  note?: string;
};

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  const { data: incident, isLoading, isError, error, refetch } = useIncident(params.id);
  const qc = useQueryClient();
  const [saving, setSaving] = useState<string | null>(null);
  const isNotFound = isError && (error as { status?: number } | null)?.status === 404;

  const timeline = (incident?.metadata?.timeline as TimelineEntry[] | undefined) ?? [];

  async function setStatus(status: string, extra?: { resolution?: string }) {
    setSaving(status);
    try {
      await updateIncident(params.id, { status, ...extra });
      await qc.invalidateQueries({ queryKey: ["incident", params.id] });
      await qc.invalidateQueries({ queryKey: ["incidents"] });
    } finally {
      setSaving(null);
    }
  }

  if (isLoading) return <LoadingSkeleton className="h-64 w-full rounded-lg" />;

  if (isNotFound) {
    return (
      <Card className="flex flex-col items-center text-center py-16 px-6 space-y-4">
        <div className="w-12 h-12 rounded-full bg-surface-elevated text-text-tertiary grid place-items-center">
          <AlertTriangle size={20} />
        </div>
        <div>
          <h2 className="text-[16px] font-semibold text-text-primary">Incident not found</h2>
          <p className="text-sm text-text-secondary mt-1">The incident you&apos;re looking for doesn&apos;t exist.</p>
        </div>
        <Link href="/incidents">
          <Button variant="secondary" size="sm">Back to Incidents</Button>
        </Link>
      </Card>
    );
  }

  if (isError || !incident) {
    return <ErrorState title="Failed to load incident" message={error?.message} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <Link href="/incidents" className="inline-flex items-center gap-2 text-[13px] text-text-secondary hover:text-text-primary transition-colors">
          <ArrowLeft size={14} /> Back to Incidents
        </Link>
        <div className="flex items-center gap-2">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6 min-w-0">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight leading-tight text-text-primary">{incident.title}</h1>
            <p className="text-[12px] text-text-tertiary font-mono">{incident.id}</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 p-4 rounded-lg border border-border-soft bg-surface-sunken shadow-sm">
            <Field label="Started" value={incident.start_time ? new Date(incident.start_time).toLocaleString() : "—"} mono />
            <Field label="Resolved" value={incident.end_time ? new Date(incident.end_time).toLocaleString() : "—"} mono />
            <Field label="Service" value={incident.affected_services?.join(", ") || "—"} mono />
            <Field label="Status" value={incident.status} />
          </div>

          <div>
            <label className="text-[11px] text-text-tertiary uppercase font-mono tracking-wide block mb-2">Description</label>
            <div className="p-4 rounded-lg border border-border-soft bg-surface-base text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap shadow-sm">
              {incident.description || "No description provided."}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="text-[11px] text-text-tertiary uppercase font-mono tracking-wide block mb-2">Root Cause</label>
              <div className="p-4 rounded-lg border border-border-soft bg-surface-base text-[13px] text-text-primary min-h-[100px] leading-relaxed shadow-sm">
                {incident.root_cause || "Not determined yet."}
              </div>
            </div>
            <div>
              <label className="text-[11px] text-text-tertiary uppercase font-mono tracking-wide block mb-2">Resolution</label>
              <div className="p-4 rounded-lg border border-border-soft bg-surface-base text-[13px] text-text-primary min-h-[100px] leading-relaxed shadow-sm">
                {incident.resolution || "Not resolved yet."}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-2 flex items-center gap-2">
              <Zap size={16} className="text-accent" /> Copilot Actions
            </h3>
            <div className="space-y-2">
              <Button
                variant="secondary"
                size="sm"
                className="w-full justify-start"
                loading={saving === "investigating"}
                disabled={saving !== null || incident.status === "investigating"}
                onClick={() => setStatus("investigating")}
              >
                Mark as Investigating
              </Button>
              <Button
                variant="primary"
                size="sm"
                className="w-full justify-start"
                loading={saving === "resolved"}
                disabled={saving !== null || incident.status === "resolved"}
                onClick={() => setStatus("resolved", { resolution: incident.resolution || "Resolved by user" })}
              >
                <CheckCircle2 size={14} />
                Resolve Incident
              </Button>
              <Link href="/incidents/logs" className="block mt-2">
                <Button variant="ghost" size="sm" className="w-full justify-start">Search Log Evidence</Button>
              </Link>
            </div>
          </Card>

          <Card>
            <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-2 flex items-center gap-2">
              <RefreshCw size={14} className="text-text-tertiary" /> Timeline
            </h3>
            {timeline.length === 0 ? (
              <p className="text-[13px] text-text-tertiary text-center py-4">No events recorded.</p>
            ) : (
              <div className="relative border-l border-border-soft ml-2 space-y-4">
                {timeline.map((entry, i) => (
                  <div key={i} className="ml-4 relative">
                    <span className="absolute -left-[19px] top-1.5 w-2 h-2 rounded-full bg-surface-base border-2 border-accent" />
                    <div className="text-[13px] text-text-primary">
                      {entry.action === "status_changed" ? (
                        <>Changed from <span className="text-text-secondary font-mono">{entry.from}</span> to <span className="text-text-primary font-mono">{entry.to}</span></>
                      ) : (
                        entry.action
                      )}
                    </div>
                    <div className="text-[11px] text-text-tertiary font-mono mt-0.5">
                      {new Date(entry.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}