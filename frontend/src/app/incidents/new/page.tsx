"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, SearchCheck, Sparkles, CheckCircle2, ArrowRight, ArrowLeft, Terminal, History, Zap } from "lucide-react";
import clsx from "clsx";
import Button from "@/components/ui/Button";
import { SeverityBadge } from "@/components/shared/StatusBadge";
import { createIncident } from "@/lib/api";

const inputCls =
  "w-full py-2 px-3 border border-border-soft rounded-md bg-surface-base text-[13px] text-text-primary outline-none focus:border-accent transition-colors placeholder:text-text-tertiary shadow-sm";

const workspaceTools = [
  { icon: Terminal, label: "Log Explorer", desc: "Search and trace log evidence for this service." },
  { icon: Zap, label: "Copilot Actions", desc: "Quick status updates with resolution notes." },
  { icon: History, label: "Timeline", desc: "Every status change and note, in order." },
];

export default function NewIncidentPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const steps = [
    { id: 1, label: "Details", icon: AlertTriangle },
    { id: 2, label: "Workspace", icon: SearchCheck },
    { id: 3, label: "Investigation", icon: Sparkles },
    { id: 4, label: "Review", icon: CheckCircle2 },
  ];

  const [form, setForm] = useState({
    title: "",
    service: "",
    severity: "high",
    start_time: new Date().toISOString().slice(0, 16),
    description: "",
    root_cause: "",
    resolution: "",
  });

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const incident = await createIncident({
        title: form.title,
        severity: form.severity,
        start_time: new Date(form.start_time).toISOString(),
        description: form.description || undefined,
        affected_services: form.service ? [form.service] : undefined,
        metadata: { root_cause_hint: form.root_cause || undefined, resolution_hint: form.resolution || undefined },
      });
      router.push(`/incidents/${incident.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create incident");
      setCreating(false);
    }
  }

  const canNext = step === 1 ? form.title.trim().length > 0 : true;

  return (
    <div className="max-w-[700px] mx-auto">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-border-soft">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Declare Incident</h1>
          <p className="text-sm text-text-secondary mt-1">Walk through the declaration wizard to start an investigation.</p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-8">
        {steps.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2 flex-1">
            <button
              onClick={() => s.id < step && setStep(s.id)}
              className={clsx(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors duration-150",
                step === s.id
                  ? "bg-accent-soft text-accent"
                  : step > s.id
                    ? "text-status-success"
                    : "text-text-tertiary hover:text-text-secondary"
              )}
            >
              <s.icon size={14} />
              <span className="hidden sm:inline">{s.label}</span>
            </button>
            {i < steps.length - 1 && <div className={clsx("flex-1 h-px", step > s.id ? "bg-status-success/40" : "bg-border-soft")} />}
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-md bg-status-critical/10 border border-status-critical/25 text-[13px] text-status-critical">
          {error}
        </div>
      )}

      <div className="bg-surface-base border border-border-soft rounded-lg p-6 shadow-sm">
        {step === 1 && (
          <div className="space-y-5">
            <div className="border-b border-border-soft pb-4 mb-4">
              <h3 className="text-[15px] font-semibold text-text-primary">What happened?</h3>
              <p className="text-[13px] text-text-secondary mt-1">Provide initial details to start the investigation.</p>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Incident Title <span className="text-status-critical">*</span></label>
              <input className={inputCls} placeholder="e.g., API gateway timeouts in production" value={form.title} onChange={set("title")} autoFocus />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div>
                <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Affected Service</label>
                <input className={inputCls} placeholder="e.g., api-gateway" value={form.service} onChange={set("service")} />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Severity</label>
                <select className={inputCls} value={form.severity} onChange={set("severity")}>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div>
                <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Started At</label>
                <input type="datetime-local" className={inputCls} value={form.start_time} onChange={set("start_time")} />
              </div>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Description</label>
              <textarea rows={4} className={inputCls} placeholder="What did you observe? Error rates, symptoms, user impact..." value={form.description} onChange={set("description")} />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div className="border-b border-border-soft pb-4 mb-4">
              <h3 className="text-[15px] font-semibold text-text-primary">Investigation Workspace</h3>
              <p className="text-[13px] text-text-secondary mt-1">Tools attached to this incident once created.</p>
            </div>
            <div className="p-4 bg-surface-sunken border border-border-soft rounded-md text-[13px] text-text-secondary">
              <p>
                The copilot will correlate logs for <strong className="text-text-primary">{form.service || "the affected service"}</strong> starting around{" "}
                <strong className="text-text-primary">{new Date(form.start_time).toLocaleTimeString()}</strong>.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {workspaceTools.map(({ icon: Icon, label, desc }) => (
                <div key={label} className="p-4 rounded-lg border border-border-soft bg-surface-sunken">
                  <div className="w-8 h-8 rounded-md bg-surface-base border border-border-soft grid place-items-center text-accent mb-2">
                    <Icon size={15} />
                  </div>
                  <div className="text-[13px] font-medium text-text-primary">{label}</div>
                  <div className="text-[12px] text-text-secondary mt-0.5 leading-snug">{desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5">
            <div className="border-b border-border-soft pb-4 mb-4">
              <h3 className="text-[15px] font-semibold text-text-primary">Root Cause & Resolution</h3>
              <p className="text-[13px] text-text-secondary mt-1">Capture early suspicions. You can refine this later.</p>
            </div>
            <div>
              <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Suspected Root Cause</label>
              <textarea rows={3} className={inputCls} placeholder="e.g. connection pool exhaustion after deploy 4.2.1" value={form.root_cause} onChange={set("root_cause")} />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-text-secondary mb-1.5">Planned Resolution</label>
              <textarea rows={3} className={inputCls} placeholder="e.g. roll back to 4.2.0 and raise pool limits" value={form.resolution} onChange={set("resolution")} />
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-5">
            <div className="border-b border-border-soft pb-4 mb-4">
              <h3 className="text-[15px] font-semibold text-text-primary">Review Details</h3>
              <p className="text-[13px] text-text-secondary mt-1">Confirm before creating the incident.</p>
            </div>
            <div className="space-y-3 text-[13px]">
              <div className="flex"><span className="w-32 text-text-tertiary">Title</span><span className="text-text-primary font-medium">{form.title}</span></div>
              <div className="flex"><span className="w-32 text-text-tertiary">Service</span><span className="text-text-primary font-mono">{form.service || "—"}</span></div>
              <div className="flex items-center"><span className="w-32 text-text-tertiary">Severity</span><SeverityBadge severity={form.severity} /></div>
              <div className="flex"><span className="w-32 text-text-tertiary">Started</span><span className="text-text-primary font-mono text-[12px]">{new Date(form.start_time).toLocaleString()}</span></div>
              <div className="flex"><span className="w-32 text-text-tertiary">Description</span><span className="text-text-secondary max-w-md">{form.description || "—"}</span></div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-6">
        <Button variant="ghost" disabled={step === 1} onClick={() => setStep((s) => s - 1)}>
          <ArrowLeft size={14} /> Back
        </Button>
        {step < 4 ? (
          <Button variant="primary" disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
            Continue <ArrowRight size={14} />
          </Button>
        ) : (
          <Button variant="primary" loading={creating} disabled={!form.title.trim()} onClick={handleCreate}>
            Create Incident <CheckCircle2 size={14} />
          </Button>
        )}
      </div>
    </div>
  );
}