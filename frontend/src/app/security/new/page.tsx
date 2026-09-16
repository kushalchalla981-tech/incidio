"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { GitBranch, Globe, FileArchive, ArrowRight, Loader2, ShieldCheck } from "lucide-react";
import clsx from "clsx";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { useCreateSecurityScan, useCreateSecurityScanZip } from "@/lib/hooks";

const inputCls = "w-full py-2 px-3 border border-border-soft rounded-md bg-surface-base text-[13px] text-text-primary outline-none focus:border-accent transition-colors placeholder:text-text-tertiary font-mono shadow-sm";

type Tab = "repo" | "url" | "zip";

const tabs: { id: Tab; label: string; icon: typeof GitBranch; hint: string }[] = [
  { id: "repo", label: "Repository", icon: GitBranch, hint: "Public GitHub, GitLab, or Bitbucket repo" },
  { id: "url", label: "Live Application", icon: Globe, hint: "HTTPS endpoint, non-destructive checks only" },
  { id: "zip", label: "Zip Upload", icon: FileArchive, hint: "Upload your source code as a .zip" },
];

export default function NewSecurityScanPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("repo");
  const [repoUrl, setRepoUrl] = useState("");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const createRepo = useCreateSecurityScan();
  const createZip = useCreateSecurityScanZip();
  const busy = createRepo.isPending || createZip.isPending;

  const llmEnabled = typeof window !== "undefined"
    ? (window.localStorage.getItem("security-llm") ?? "true") === "true"
    : true;

  function run(target: { source_type: Tab; source_ref: string }) {
    setError(null);
    if (target.source_type === "zip") {
      const file = fileRef.current?.files?.[0];
      if (!file) {
        setError("Choose a .zip file first.");
        return;
      }
      createZip.mutate(
        { file, name: name || undefined },
        {
          onSuccess: (scan) => router.push(`/security/scans/${scan.id}`),
          onError: (e) => setError(e instanceof Error ? e.message : "Upload failed"),
        }
      );
      return;
    }
    createRepo.mutate(
      {
        source_type: target.source_type,
        source_ref: target.source_ref,
        name: name || undefined,
        options: { llm_review: llmEnabled },
      },
      {
        onSuccess: (scan) => router.push(`/security/scans/${scan.id}`),
        onError: (e) => setError(e instanceof Error ? e.message : "Scan failed to start"),
      }
    );
  }

  function submit() {
    if (tab === "repo") run({ source_type: "repo", source_ref: repoUrl });
    else if (tab === "url") run({ source_type: "url", source_ref: url });
    else run({ source_type: "zip", source_ref: "" });
  }

  const canSubmit = tab === "repo" ? repoUrl.trim().length > 0 : tab === "url" ? url.trim().length > 0 : true;

  return (
    <div className="max-w-[700px] mx-auto pt-6">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-border-soft">
         <div className="flex items-center gap-3">
            <h1 className="text-[20px] font-semibold text-text-primary">New Security Scan</h1>
            <Badge variant="info">Automated analysis</Badge>
         </div>
      </div>

      <div className="bg-surface-base border border-border-soft rounded-lg p-6">
        <div className="flex gap-2 mb-6">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={clsx(
                "flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-[13px] font-medium transition-colors duration-150",
                tab === t.id
                  ? "bg-accent-soft text-accent border border-accent-border"
                  : "bg-surface-elevated text-text-secondary border border-border-strong hover:text-text-primary"
              )}
            >
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-md bg-status-critical/10 border border-status-critical/20 text-[13px] text-status-critical">
            {error}
          </div>
        )}

        <div className="space-y-5">
          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1.5">
              {tabs.find((t) => t.id === tab)?.hint}
            </label>
            {tab === "repo" && (
              <input
                className={inputCls}
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                disabled={busy}
                autoFocus
              />
            )}
            {tab === "url" && (
              <input
                className={inputCls}
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={busy}
                autoFocus
              />
            )}
            {tab === "zip" && (
              <div className="relative">
                 <input
                   ref={fileRef}
                   type="file"
                   accept=".zip"
                   className="w-full py-2 px-3 border border-border-soft rounded-md bg-surface-elevated text-[13px] text-text-primary outline-none focus:border-accent transition-colors file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:text-[12px] file:font-medium file:bg-surface-base file:text-text-primary file:border file:border-border-strong file:hover:bg-surface-elevated file:cursor-pointer"
                   disabled={busy}
                 />
              </div>
            )}
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Project Name (Optional)</label>
            <input
              className={inputCls}
              placeholder="e.g. payments-service"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={busy}
            />
          </div>

          {llmEnabled && (
             <div className="p-3 bg-accent-soft/30 border border-accent-border rounded-md flex gap-3 text-[12px] text-text-secondary">
               <ShieldCheck size={16} className="text-accent flex-shrink-0 mt-0.5" />
               <p>LLM deep review is enabled in your settings. Up to 10 high-risk files will be sent for AI analysis during this scan.</p>
             </div>
          )}

          <div className="pt-4 border-t border-border-soft flex justify-end">
            <Button variant="primary" onClick={submit} disabled={!canSubmit || busy}>
              {busy ? <><Loader2 size={14} className="animate-spin" /> Starting Scan...</> : <>Start Scan <ArrowRight size={14} /></>}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
