"use client";

import { useState } from "react";
import { Sparkles, Server, Database, CheckCircle2, CircleDashed, Palette, Sun, Moon } from "lucide-react";
import clsx from "clsx";
import Card from "@/components/ui/Card";
import Toggle from "@/components/ui/Toggle";
import SettingsHero from "@/components/shared/SettingsHero";
import { useHealth, useIncidents } from "@/lib/hooks";
import { useTheme } from "@/lib/useTheme";
import type { Product } from "@/components/layout/ProductSwitcher";

export default function SettingsContent({ product }: { product: Product }) {
  const { data: health } = useHealth();
  const { data: incidents } = useIncidents({ limit: 1 });
  const { theme, setTheme } = useTheme();

  const [llmReview, setLlmReview] = useState(() =>
    typeof window !== "undefined"
      ? (window.localStorage.getItem("security-llm") ?? "true") === "true"
      : true
  );

  function toggleLlmReview(value: boolean) {
    setLlmReview(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("security-llm", String(value));
    }
  }

  const online = health?.status === "ok";

  const themeOption = (value: "light" | "dark", label: string, Icon: typeof Sun) => (
    <button
      key={value}
      onClick={() => setTheme(value)}
      aria-pressed={theme === value}
      className={clsx(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all duration-150",
        theme === value
          ? "bg-surface-base text-text-primary border border-border-strong shadow-sm"
          : "text-text-secondary hover:text-text-primary border border-transparent"
      )}
    >
      <Icon size={14} />
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      <SettingsHero product={product} />

      {product === "security" && (
        <Card>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-soft text-accent grid place-items-center flex-shrink-0">
              <Sparkles size={18} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[14px] font-medium text-text-primary">LLM deep review</div>
              <p className="text-[12px] text-text-secondary mt-0.5">
                Send up to 10 flagged files to the LLM for a security deep review. Disabled scans run rules-only.
              </p>
            </div>
            <Toggle defaultChecked={llmReview} onChange={toggleLlmReview} />
          </div>
        </Card>
      )}

      <Card>
        <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-3 flex items-center gap-2">
          <Palette size={16} className="text-accent" /> Appearance
        </h3>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="text-[14px] font-medium text-text-primary">Theme</div>
            <p className="text-[12px] text-text-secondary mt-0.5">
              Choose a light or dark interface. Your preference is remembered on this device.
            </p>
          </div>
          <div className="flex items-center rounded-lg border border-border-soft bg-surface-sunken p-1 gap-1">
            {themeOption("light", "Light", Sun)}
            {themeOption("dark", "Dark", Moon)}
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="text-[14px] font-semibold mb-4 border-b border-border-soft pb-3 flex items-center gap-2">
          <Server size={16} className="text-accent" /> System Status
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="flex items-center gap-2 text-text-secondary">
              <Database size={14} className="text-text-tertiary" /> Backend & database
            </span>
            {online ? (
              <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-status-success">
                <CheckCircle2 size={13} /> Connected
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-status-critical">
                <CircleDashed size={13} /> Offline
              </span>
            )}
          </div>
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-text-secondary">Data source</span>
            <span className="font-mono text-[12px] text-text-primary">{incidents ? "Live API (PostgreSQL)" : "Connecting…"}</span>
          </div>
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-text-secondary">Last health check</span>
            <span className="font-mono text-[12px] text-text-tertiary">
              {health?.timestamp ? new Date(health.timestamp).toLocaleString() : "—"}
            </span>
          </div>
        </div>
      </Card>

      <p className="text-center text-[12px] text-text-tertiary pb-2">
        This is an internal tool with no user accounts. Learn more about the platform in the project README.
      </p>
    </div>
  );
}