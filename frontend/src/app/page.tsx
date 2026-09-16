import Link from "next/link";
import {
  Search, Radar, Zap, ShieldCheck, BarChart3, Server, FileText, ScanLine, ArrowRight,
} from "lucide-react";
import LandingNav from "@/components/landing/LandingNav";
import ProductPreview from "@/components/landing/ProductPreview";
import LiveStats from "@/components/landing/LiveStats";
import Reveal from "@/components/shared/Reveal";
import MotionBackground from "@/components/shared/MotionBackground";

const features = [
  { icon: Search, title: "Semantic log search", desc: "Search production logs in natural language with embedding-based retrieval and log grouping via Drain3." },
  { icon: Radar, title: "Anomaly detection", desc: "PyOD-powered outlier detection surfaces deviations in error rates before they become incidents." },
  { icon: Zap, title: "Copilot actions", desc: "Declare incidents, mark them investigating, resolve with root cause — all from one timeline." },
  { icon: ShieldCheck, title: "Repo security scanning", desc: "Twenty heuristic rules plus an optional LLM deep review, with scored A-F reports and findings." },
  { icon: BarChart3, title: "Live analytics", desc: "Mean time to resolve, incident frequency, and service health computed straight from your data." },
  { icon: Server, title: "Self-hosted", desc: "Runs on your infrastructure. PostgreSQL-backed, sealed behind your own access layer." },
];

const steps = [
  { icon: FileText, step: "01", title: "Watch the logs", desc: "Stream, filter, and semantically search log lines across services and severity levels." },
  { icon: Zap, step: "02", title: "Investigate with a timeline", desc: "Track status changes, capture root cause, and let the copilot tie evidence together." },
  { icon: ScanLine, step: "03", title: "Scan your repos", desc: "Submit a repository, live app, or zip for a scored security review with actionable findings." },
];

export default function HomePage() {
  return (
    <div className="flex flex-col">
      <LandingNav />

      <section className="relative overflow-hidden">
        <MotionBackground />
        <div className="relative max-w-screen-xl mx-auto px-4 sm:px-6 pt-16 pb-14 sm:pt-24 sm:pb-20 text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-base border border-border-soft text-text-secondary text-[12px] font-medium mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
              Built for small engineering teams
            </span>
            <h1 className="font-display text-[34px] sm:text-[52px] font-semibold tracking-tight leading-[1.1] text-text-primary max-w-3xl mx-auto">
              Resolve incidents with a copilot by your side
            </h1>
            <p className="mt-5 text-[15px] sm:text-[17px] text-text-secondary max-w-xl mx-auto leading-relaxed">
              Incident Copilot turns logs into insights, detects anomalies automatically, and scans your repositories for vulnerabilities — all self-hosted.
            </p>
            <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
              <Link
                href="/incidents/dashboard"
                className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-accent text-white text-[14px] font-medium shadow-sm hover:brightness-95 active:scale-[0.98] transition-all duration-150"
              >
                Open the Dashboard <ArrowRight size={15} />
              </Link>
              <Link
                href="/security/new"
                className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-surface-base border border-border-strong text-text-primary text-[14px] font-medium shadow-sm hover:bg-surface-sunken active:scale-[0.98] transition-all duration-150"
              >
                Run a Security Scan
              </Link>
            </div>
          </Reveal>

          <Reveal delay={120} className="mt-14">
            <ProductPreview />
          </Reveal>

          <Reveal delay={80} className="mt-14">
            <LiveStats />
          </Reveal>
        </div>
      </section>

      <section className="bg-surface-sunken border-y border-border-soft">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-16 sm:py-20">
          <Reveal>
            <h2 className="font-display text-2xl sm:text-[30px] font-semibold tracking-tight text-center text-text-primary">
              Everything an on-call engineer needs
            </h2>
            <p className="mt-3 text-[14px] text-text-secondary text-center max-w-lg mx-auto">
              One self-hosted workspace for the moments that matter — from the first alert to the final postmortem.
            </p>
          </Reveal>

          <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map(({ icon: Icon, title, desc }, i) => (
              <Reveal key={title} delay={i * 60}>
                <div className="h-full bg-surface-base border border-border-soft rounded-xl p-6 shadow-sm transition-all duration-150 hover:border-border-strong hover:shadow-card">
                  <div className="w-10 h-10 rounded-lg bg-accent-soft text-accent grid place-items-center mb-4">
                    <Icon size={18} />
                  </div>
                  <h3 className="text-[15px] font-semibold text-text-primary">{title}</h3>
                  <p className="mt-1.5 text-[13px] text-text-secondary leading-relaxed">{desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-16 sm:py-20">
          <Reveal>
            <h2 className="font-display text-2xl sm:text-[30px] font-semibold tracking-tight text-center text-text-primary">
              From alert to fix in three steps
            </h2>
          </Reveal>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-10">
            {steps.map(({ icon: Icon, step, title, desc }, i) => (
              <Reveal key={step} delay={i * 80}>
                <div className="flex flex-col items-center text-center">
                  <div className="relative">
                    <div className="w-14 h-14 rounded-2xl bg-surface-base border border-border-soft shadow-sm grid place-items-center text-accent">
                      <Icon size={22} />
                    </div>
                  </div>
                  <span className="mt-4 font-mono text-[12px] text-text-tertiary">{step}</span>
                  <h3 className="mt-1 text-[16px] font-semibold text-text-primary">{title}</h3>
                  <p className="mt-2 text-[13px] text-text-secondary leading-relaxed max-w-xs">{desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-surface-base border-t border-border-soft">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-16 sm:py-20">
          <Reveal>
            <div className="rounded-2xl border border-border-soft bg-surface-base shadow-sm p-10 text-center">
              <h2 className="font-display text-2xl sm:text-[28px] font-semibold tracking-tight text-text-primary">
                Ready to calm the noise?
              </h2>
              <p className="mt-3 text-[14px] text-text-secondary max-w-md mx-auto">
                Jump straight into your incident workspace or run a security scan on a repository right now.
              </p>
              <div className="mt-7 flex items-center justify-center gap-3 flex-wrap">
                <Link
                  href="/incidents/dashboard"
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-accent text-white text-[14px] font-medium shadow-sm hover:brightness-95 active:scale-[0.98] transition-all duration-150"
                >
                  Open the Dashboard <ArrowRight size={15} />
                </Link>
                <Link
                  href="/security"
                  className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-surface-base border border-border-strong text-text-primary text-[14px] font-medium shadow-sm hover:bg-surface-sunken active:scale-[0.98] transition-all duration-150"
                >
                  Browse Security Finder
                </Link>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-border-soft bg-surface-sunken">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="w-6 h-6 rounded-md bg-accent-soft text-accent grid place-items-center text-[10px] font-bold">IC</span>
            <span className="text-[13px] font-medium text-text-primary">Incident Copilot</span>
          </div>
          <div className="flex items-center gap-5 text-[12px] text-text-secondary">
            <Link href="/incidents" className="hover:text-text-primary transition-colors">Incident Manager</Link>
            <Link href="/security" className="hover:text-text-primary transition-colors">Security Checker</Link>
            <Link href="/security/history" className="hover:text-text-primary transition-colors">Scan History</Link>
          </div>
          <p className="text-[12px] text-text-tertiary">Self-hosted. No accounts. No tracking.</p>
        </div>
      </footer>
    </div>
  );
}