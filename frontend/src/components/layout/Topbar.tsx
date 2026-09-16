"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, Menu, Settings, CheckCircle2, Home, Moon, Sun } from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import ProductSwitcher, { useProduct } from "./ProductSwitcher";
import { useIncidents } from "@/lib/hooks";
import { SeverityBadge } from "@/components/shared/StatusBadge";
import { useTheme } from "@/lib/useTheme";

function RecentNotifications({ onNavigate }: { onNavigate: () => void }) {
  const { data: incidents, isLoading } = useIncidents({ limit: 20 });
  const severityRank = { critical: 0, high: 1, medium: 2, low: 3 } as const;
  const active = (incidents || [])
    .filter((i) => i.status === "open" || i.status === "investigating")
    .sort(
      (a, b) =>
        (severityRank[a.severity as keyof typeof severityRank] ?? 9) -
        (severityRank[b.severity as keyof typeof severityRank] ?? 9)
    )
    .slice(0, 5);

  if (!isLoading && active.length === 0) {
    return (
      <div className="flex flex-col items-center text-center px-4 py-8">
        <div className="w-10 h-10 rounded-full bg-status-success/10 text-status-success grid place-items-center mb-3">
          <CheckCircle2 size={18} />
        </div>
        <p className="text-[13px] font-medium text-text-primary">No active incidents</p>
        <p className="text-[12px] text-text-secondary mt-1">You&apos;re all caught up.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border-soft">
      {active.map((inc) => (
        <Link
          key={inc.id}
          href={`/incidents/${inc.id}`}
          onClick={onNavigate}
          className="flex items-start gap-3 px-3 py-2.5 hover:bg-surface-sunken transition-colors duration-150"
        >
          <span
            className={clsx(
              "w-2 h-2 rounded-full mt-1.5 flex-shrink-0",
              inc.severity === "critical" && "bg-status-critical",
              inc.severity === "high" && "bg-status-high",
              inc.severity === "medium" && "bg-status-medium",
              inc.severity === "low" && "bg-status-low"
            )}
          />
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] text-text-primary leading-snug line-clamp-2">{inc.title}</span>
            <span className="block mt-1">
              <SeverityBadge severity={inc.severity} />
            </span>
          </span>
        </Link>
      ))}
    </div>
  );
}

export default function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const [notifOpen, setNotifOpen] = useState(false);
  const [clock, setClock] = useState("");
  const notifRef = useRef<HTMLDivElement>(null);
  const product = useProduct();
  const { theme, toggleTheme } = useTheme();

  const settingsHref = product === "security" ? "/security/settings" : "/incidents/settings";

  useEffect(() => {
    function tick() {
      setClock(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " UTC");
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const { data: incidents } = useIncidents({ limit: 20 });
  const hasAlerts = (incidents || []).some((i) => i.status === "open" || i.status === "investigating");

  return (
    <header className="h-[var(--topbar-h)] bg-surface-base border-b border-border-soft flex items-center gap-3 px-4 sm:px-6 flex-shrink-0 z-20 relative shadow-sm">
      <button
        onClick={onOpenMenu}
        className="lg:hidden w-8 h-8 rounded-md grid place-items-center text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150"
        aria-label="Open menu"
      >
        <Menu size={16} />
      </button>

<ProductSwitcher />

          <Link
            href="/"
            className="w-8 h-8 rounded-md grid place-items-center text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150"
            aria-label="Home"
            title="Back to landing page"
          >
            <Home size={16} />
          </Link>

          <div className="flex items-center gap-3 ml-auto">
            <button
              onClick={toggleTheme}
              className="w-8 h-8 rounded-md grid place-items-center text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150"
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title="Toggle theme"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <span className="font-mono text-[12px] text-text-tertiary hidden md:inline-block tabular-nums">{clock}</span>

        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifOpen((o) => !o)}
            className="w-8 h-8 rounded-md grid place-items-center text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150 relative"
            aria-label="Notifications"
            aria-expanded={notifOpen}
          >
            <Bell size={16} />
            {hasAlerts && (
              <span className="absolute top-[6px] right-[6px] w-1.5 h-1.5 rounded-full bg-status-critical status-dot border border-surface-base" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute top-full right-0 mt-2 w-[320px] bg-surface-base border border-border-strong rounded-lg shadow-lg overflow-hidden z-50 animate-scale-in">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-soft">
                <div className="text-[12px] font-semibold text-text-secondary">Notifications</div>
                <span className="text-[11px] text-text-tertiary">Active incidents</span>
              </div>
              <RecentNotifications onNavigate={() => setNotifOpen(false)} />
            </div>
          )}
        </div>

        <Link
          href={settingsHref}
          className="w-8 h-8 rounded-md grid place-items-center text-text-secondary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150"
          aria-label="Settings"
        >
          <Settings size={16} />
        </Link>
      </div>
    </header>
  );
}