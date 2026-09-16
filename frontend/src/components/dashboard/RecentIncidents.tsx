import Link from "next/link";
import type { IncidentResponse } from "@/lib/types";
import { SeverityBadge, StatusBadge } from "@/components/shared/StatusBadge";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import EmptyState from "@/components/shared/EmptyState";
import { ArrowRight, Inbox } from "lucide-react";

export default function RecentIncidents({
  incidents,
  isLoading,
}: {
  incidents: IncidentResponse[] | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <LoadingSkeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!incidents?.length) {
    return (
      <EmptyState icon={Inbox} title="No incidents" description="Active incidents will appear here as they're declared." />
    );
  }

  return (
    <div className="overflow-x-auto -mx-5 px-5">
      <table className="w-full border-collapse text-[14px] min-w-[620px]">
        <thead>
          <tr>
            <th className="text-left py-2.5 pr-4 text-text-tertiary font-medium text-[11px]">Title</th>
            <th className="text-left py-2.5 pr-4 text-text-tertiary font-medium text-[11px]">Severity</th>
            <th className="text-left py-2.5 pr-4 text-text-tertiary font-medium text-[11px]">Status</th>
            <th className="text-left py-2.5 pr-4 text-text-tertiary font-medium text-[11px] hidden sm:table-cell">Service</th>
            <th className="text-left py-2.5 text-text-tertiary font-medium text-[11px] hidden md:table-cell">Started</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => (
            <tr key={inc.id} className="border-t border-border-soft hover:bg-accent-soft/50 transition-colors duration-150 group">
              <td className="py-3 pr-4 min-w-0">
                <Link
                  href={`/incidents/${inc.id}`}
                  className="flex items-center gap-1.5 text-text-primary hover:text-accent transition-colors"
                >
                  <span className="truncate">{inc.title}</span>
                  <ArrowRight size={13} className="text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </Link>
              </td>
              <td className="py-3 pr-4">
                <SeverityBadge severity={inc.severity} />
              </td>
              <td className="py-3 pr-4">
                <StatusBadge status={inc.status} />
              </td>
              <td className="py-3 pr-4 hidden sm:table-cell text-text-secondary">{inc.affected_services?.[0] || "—"}</td>
              <td className="py-3 hidden md:table-cell text-text-tertiary text-[13px]">
                {new Date(inc.start_time).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}