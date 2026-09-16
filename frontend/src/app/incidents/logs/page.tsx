"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { Pause, Play, Download, TerminalSquare } from "lucide-react";
import { useLogs } from "@/lib/hooks";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import LiveBadge from "@/components/shared/LiveBadge";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import EmptyState from "@/components/shared/EmptyState";
import { Inbox } from "lucide-react";
import type { LogResponse } from "@/lib/types";

function LogLine({ log }: { log: LogResponse }) {
  const [expanded, setExpanded] = useState(false);
  const levelColors: Record<string, string> = {
    ERROR: "text-status-critical", WARN: "text-status-high", INFO: "text-status-medium", DEBUG: "text-text-tertiary",
  };

  return (
    <div className="group border-b border-border-soft last:border-b-0 text-[12px] font-mono cursor-pointer hover:bg-surface-elevated transition-colors">
      <div className="flex gap-4 py-2 px-3" onClick={() => setExpanded((e) => !e)}>
        <span className="text-text-tertiary whitespace-nowrap flex-shrink-0">
          {new Date(log.timestamp).toLocaleTimeString(undefined, { hour12: false, fractionalSecondDigits: 3 })}
        </span>
        <span className={`w-12 flex-shrink-0 font-medium ${levelColors[log.level] || "text-text-secondary"}`}>
          {log.level}
        </span>
        <span className="text-text-secondary w-32 truncate flex-shrink-0">{log.service}</span>
        <span className="flex-1 break-words text-text-primary leading-snug">{log.message}</span>
      </div>
      {expanded && (
        <div className="px-3 pb-3">
          <div className="bg-surface-sunken p-3 rounded-lg border border-border-soft text-[11px] text-text-secondary whitespace-pre-wrap break-words overflow-x-auto">
            {JSON.stringify({ raw: log.raw_log, template_id: log.template_id, parameters: log.parameters, metadata: log.metadata }, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LogsPage() {
  const [paused, setPaused] = useState(false);
  const [levelFilter, setLevelFilter] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");
  const [frozenCount, setFrozenCount] = useState<number | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const { data: logs, isLoading } = useLogs({ level: levelFilter || undefined, limit: 200 });

  useEffect(() => {
    if (!paused && logs) setFrozenCount(null);
  }, [paused, logs]);

  const services = useMemo(
    () => Array.from(new Set((logs || []).map((l) => l.service))).filter((s): s is string => !!s).sort(),
    [logs]
  );

  const visible = useMemo(() => {
    let out = logs || [];
    if (serviceFilter) out = out.filter((l) => l.service === serviceFilter);
    if (paused && frozenCount !== null) out = out.slice(0, frozenCount);
    return out;
  }, [logs, serviceFilter, paused, frozenCount]);

  function exportJson() {
    const blob = new Blob([JSON.stringify(visible, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-var(--topbar-h)-72px)]">
      <div className="flex items-center justify-between flex-wrap gap-4 border-b border-border-soft pb-4 mb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-accent-soft text-accent grid place-items-center">
            <TerminalSquare size={16} />
          </div>
          <h1 className="text-[20px] font-semibold text-text-primary tracking-tight">Log Explorer</h1>
          <LiveBadge />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={paused ? "primary" : "secondary"}
            size="sm"
            onClick={() => {
              if (!paused) setFrozenCount((logs || []).length);
              setPaused((p) => !p);
            }}
          >
            {paused ? <Play size={14} /> : <Pause size={14} />} {paused ? "Resume" : "Pause"}
          </Button>
          <Button variant="secondary" size="sm" onClick={exportJson} disabled={visible.length === 0}>
            <Download size={14} /> Export
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap mb-4 flex-shrink-0 bg-surface-base border border-border-soft p-2 rounded-lg">
        <Select
          className="w-32"
          options={[
            { value: "", label: "Level: All" },
            { value: "ERROR", label: "ERROR" },
            { value: "WARN", label: "WARN" },
            { value: "INFO", label: "INFO" },
            { value: "DEBUG", label: "DEBUG" },
          ]}
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
        />
        <Select
          className="w-40"
          options={[
            { value: "", label: "Service: All" },
            ...services.map((s) => ({ value: s, label: s })),
          ]}
          value={serviceFilter}
          onChange={(e) => setServiceFilter(e.target.value)}
        />
        <div className="flex-1" />
        <span className="font-mono text-[11px] text-text-tertiary bg-surface-sunken px-2 py-1 rounded border border-border-soft">
          Showing {visible.length} entries{paused ? " (paused)" : ""}
        </span>
      </div>

      <div className="flex-1 min-h-0 bg-surface-base border border-border-strong rounded-lg overflow-hidden flex flex-col shadow-sm">
        <div className="flex gap-4 py-2 px-3 bg-surface-sunken border-b border-border-soft text-[11px] font-mono text-text-tertiary uppercase tracking-wider flex-shrink-0">
          <span className="w-20">Timestamp</span>
          <span className="w-12">Level</span>
          <span className="w-32">Service</span>
          <span className="flex-1">Message</span>
        </div>
        <div ref={streamRef} className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 15 }).map((_, i) => (
                <LoadingSkeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : !visible?.length ? (
            <EmptyState icon={Inbox} title="No log entries" description="Try adjusting the filters, or stream a new incident." />
          ) : (
            visible.map((log) => <LogLine key={log.id} log={log} />)
          )}
        </div>
      </div>
    </div>
  );
}