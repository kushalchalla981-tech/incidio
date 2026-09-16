"use client";

import { useIncidents, useSecurityScans, useSecurityFindings } from "@/lib/hooks";

export default function LiveStats() {
  const { data: incidents } = useIncidents({ limit: 50 });
  const { data: scans } = useSecurityScans();
  const { data: findings } = useSecurityFindings();

  const openIncidents = (incidents || []).filter((i) => i.status === "open" || i.status === "investigating").length;
  const scansRun = (scans || []).length;
  const openFindings = (findings || []).filter((f) => f.status === "open").length;

  const stats = [
    { value: openIncidents, label: "Open incidents" },
    { value: scansRun, label: "Scans run" },
    { value: openFindings, label: "Open findings" },
  ];

  return (
    <div className="grid grid-cols-3 gap-4 max-w-md mx-auto">
      {stats.map((s) => (
        <div key={s.label} className="text-center">
          <div className="font-display text-3xl font-semibold tracking-tight text-text-primary tabular-nums">
            {s.value}
          </div>
          <div className="text-[12px] text-text-secondary mt-1">{s.label}</div>
        </div>
      ))}
    </div>
  );
}