import type { IncidentResponse } from "@/lib/types";

interface ServiceState {
  name: string;
  worst: string | null;
}

export default function ServiceHealth({ incidents }: { incidents: IncidentResponse[] }) {
  const byService = new Map<string, ServiceState>();
  for (const inc of incidents) {
    const active = inc.status === "open" || inc.status === "investigating";
    for (const svc of inc.affected_services || []) {
      const prev = byService.get(svc)?.worst ?? null;
      const severityRank = { critical: 0, high: 1, medium: 2, low: 3 } as Record<string, number>;
      if (active) {
        const cur = prev === null || (severityRank[inc.severity] ?? 9) < (severityRank[prev] ?? 9)
          ? inc.severity
          : prev;
        byService.set(svc, { name: svc, worst: cur });
      } else if (prev === null) {
        byService.set(svc, { name: svc, worst: null });
      }
    }
  }

  const rows = Array.from(byService.values()).sort((a, b) => a.name.localeCompare(b.name));
  const affected = rows.filter((r) => r.worst !== null).length;

  if (rows.length === 0) {
    return (
      <p className="text-sm text-text-secondary py-6 text-center">
        No service data yet. Services appear here once incidents reference them.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-baseline gap-2 mb-4">
        <span className="font-display text-[28px] font-semibold tracking-tight tabular-nums text-text-primary">
          {rows.length - affected}
        </span>
        <span className="text-[12px] text-text-secondary">
          of {rows.length} services operational
        </span>
      </div>

      <div className="divide-y divide-border-soft">
        {rows.map((row) => {
          const ok = row.worst === null;
          return (
            <div key={row.name} className="flex items-center justify-between py-2.5">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: ok ? "var(--status-success)" : `var(--status-${row.worst})` }}
                />
                <span className="text-[13px] font-medium text-text-primary truncate">{row.name}</span>
              </div>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${
                  ok
                    ? "bg-status-success/10 text-status-success"
                    : "bg-status-critical/10 text-status-critical"
                }`}
              >
                {ok ? "Operational" : row.worst}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}