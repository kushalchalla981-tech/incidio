"use client";

import { useRouter } from "next/navigation";
import { PlusCircle, FolderGit2 } from "lucide-react";
import { useSecurityProjects } from "@/lib/hooks";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import LoadingSkeleton from "@/components/shared/LoadingSkeleton";
import PageHeader from "@/components/shared/PageHeader";

const statusVariant: Record<string, "warn" | "success" | "danger" | "neutral"> = {
  queued: "warn", running: "warn", completed: "success", failed: "danger",
};

export default function SecurityProjectsPage() {
  const router = useRouter();
  const { data: projects, isLoading } = useSecurityProjects();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Projects"
        description="Repositories and applications monitored for vulnerabilities."
        actions={
          <Button variant="primary" size="sm" onClick={() => router.push("/security/new")}>
            <PlusCircle size={14} /> New Scan
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <LoadingSkeleton key={i} className="h-32 w-full rounded-lg" />)}
        </div>
      ) : !projects || projects.length === 0 ? (
        <Card className="text-center py-16">
          <FolderGit2 size={24} className="mx-auto mb-3 text-text-tertiary" />
          <h2 className="text-[16px] font-semibold mb-1 text-text-primary">No projects yet</h2>
          <p className="text-[13px] text-text-secondary mb-5">Scan a repository, live application, or zip upload to get started.</p>
          <Button variant="secondary" size="sm" onClick={() => router.push("/security/new")}>Start a Scan</Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {projects.map((p) => (
            <Card key={p.id} hover onClick={() => router.push(`/security/projects/${p.id}`)} className="flex flex-col">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="min-w-0">
                  <h3 className="text-[15px] font-semibold text-text-primary truncate">{p.name || p.source_ref}</h3>
                  <p className="text-[12px] text-text-tertiary font-mono truncate mt-0.5">{p.source_ref}</p>
                </div>
                <Badge variant="neutral" className="flex-shrink-0">{p.source_type}</Badge>
              </div>

              <div className="mt-auto pt-4 border-t border-border-soft flex items-center justify-between">
                <div className="flex items-center gap-2 text-[12px]">
                   {p.last_scan_status ? (
                      <>
                         <Badge variant={statusVariant[p.last_scan_status] || "neutral"}>{p.last_scan_status}</Badge>
                         <span className="text-text-tertiary font-mono ml-2 tabular-nums">{new Date(p.updated_at).toLocaleDateString()}</span>
                      </>
                   ) : (
                      <span className="text-text-tertiary">No completed scans</span>
                   )}
                </div>
                <div className="text-[12px] font-medium text-accent">View Details &rarr;</div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
