"use client";

import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import type { IncidentResponse } from "@/lib/types";

function startOfDay(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x.getTime();
}

export default function IncidentTrend({
  incidents,
  days = 14,
}: {
  incidents: IncidentResponse[];
  days?: number;
}) {
  const data = useMemo(() => {
    const now = new Date();
    const buckets = Array.from({ length: days }, (_, i) => {
      const day = new Date(now);
      day.setDate(now.getDate() - (days - 1 - i));
      return { label: day.toLocaleDateString("en-US", { month: "short", day: "numeric" }), count: 0, key: startOfDay(day) };
    });
    for (const inc of incidents) {
      const t = startOfDay(new Date(inc.start_time));
      const hit = buckets.find((b) => b.key === t);
      if (hit) hit.count += 1;
    }
    return buckets;
  }, [incidents, days]);

  const total = data.reduce((sum, d) => sum + d.count, 0);

  if (total === 0) {
    return <p className="text-sm text-text-secondary py-8 text-center">No incidents in this period.</p>;
  }

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -22 }}>
          <CartesianGrid vertical={false} stroke="var(--border-soft)" strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--text-tertiary)" }}
            interval={days > 10 ? 2 : 0}
            dy={6}
          />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--text-tertiary)" }} width={28} />
          <Tooltip
            cursor={{ fill: "var(--accent-soft)" }}
            contentStyle={{
              background: "var(--surface-base)",
              border: "1px solid var(--border-strong)",
              borderRadius: 8,
              fontSize: 12,
              boxShadow: "0 8px 24px rgba(16,24,40,0.1)",
            }}
            labelStyle={{ color: "var(--text-tertiary)", fontWeight: 500 }}
          />
          <Bar dataKey="count" name="Incidents" fill="var(--accent)" radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}