"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard, BarChart3, AlertTriangle, ScrollText, Settings, ChevronLeft, ChevronRight,
  PlusCircle, FolderKanban, ListChecks, History, Home,
} from "lucide-react";
import { useProduct } from "./ProductSwitcher";

const incidentLinks = [
  { href: "/incidents/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
  { href: "/incidents/new", label: "New Incident", icon: PlusCircle, primary: true },
  { href: "/incidents/logs", label: "Logs", icon: ScrollText },
  { href: "/incidents/analytics", label: "Analytics", icon: BarChart3 },
];

const securityLinks = [
  { href: "/security", label: "Dashboard", icon: LayoutDashboard },
  { href: "/security/projects", label: "Projects", icon: FolderKanban },
  { href: "/security/findings", label: "Findings", icon: ListChecks },
  { href: "/security/history", label: "History", icon: History },
  { href: "/security/new", label: "New Scan", icon: PlusCircle, primary: true },
];

const PRODUCT_META = {
  incidents: { mark: "IC", name: "Incident Copilot", color: "#2F5FD0" },
  security: { mark: "SC", name: "Security Checker", color: "#6B56D3" },
} as const;

export default function Sidebar({
  mobileOpen,
  onCloseMenu,
}: {
  mobileOpen: boolean;
  onCloseMenu: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const product = useProduct();
  const meta = PRODUCT_META[product];
  const links = product === "security" ? securityLinks : incidentLinks;

  const settingsHref = product === "security" ? "/security/settings" : "/incidents/settings";

  const isActive = (href: string) => {
    if (href === "/incidents") return pathname === "/incidents";
    if (href === "/security") return pathname === "/security" || pathname.startsWith("/security/projects");
    return pathname.startsWith(href);
  };

  const rowClass = (active: boolean) =>
    clsx(
      "flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-medium whitespace-nowrap transition-colors duration-150",
      active ? "bg-accent-soft text-accent" : "text-text-secondary hover:bg-surface-elevated hover:text-text-primary"
    );

  const content = (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 h-[var(--topbar-h)] px-4 flex-shrink-0 whitespace-nowrap overflow-hidden">
        <div
          className="w-6 h-6 rounded flex items-center justify-center text-[11px] font-bold flex-shrink-0"
          style={{ backgroundColor: `${meta.color}1a`, color: meta.color }}
        >
          {meta.mark}
        </div>
        <span
          className={clsx(
            "text-[14px] font-semibold tracking-tight transition-opacity duration-200",
            collapsed && "opacity-0"
          )}
        >
          {meta.name}
        </span>
      </div>

      <nav className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
        {links.map(({ href, label, icon: Icon, primary }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                rowClass(active),
                primary && "mt-1 bg-surface-elevated border border-border-soft hover:border-border-strong text-text-primary"
              )}
            >
              <Icon size={16} className={clsx("flex-shrink-0", active ? "text-accent" : "opacity-80")} />
              <span className={clsx("transition-opacity duration-200", collapsed && "opacity-0")}>
                {label}
              </span>
            </Link>
          );
        })}
        <div className="mt-auto pt-4" />
        <Link
          key="/"
          href="/"
          className={rowClass(pathname === "/")}
          aria-label="Back to landing page"
        >
          <Home size={16} className="flex-shrink-0 opacity-80" />
          <span className={clsx("transition-opacity duration-200", collapsed && "opacity-0")}>
            Home
          </span>
        </Link>
        <Link
          key={settingsHref}
          href={settingsHref}
          aria-current={pathname.startsWith(settingsHref) ? "page" : undefined}
          className={clsx(rowClass(isActive(settingsHref)))}
        >
          <Settings size={16} className={clsx("flex-shrink-0", isActive(settingsHref) ? "text-accent" : "opacity-80")} />
          <span className={clsx("transition-opacity duration-200", collapsed && "opacity-0")}>
            Settings
          </span>
        </Link>
      </nav>

      <div className="p-3 hidden lg:block">
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="w-full flex items-center justify-center p-2 rounded-md text-text-tertiary hover:bg-surface-elevated hover:text-text-primary transition-colors duration-150"
          aria-label="Toggle sidebar"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={clsx(
          "fixed inset-0 z-30 bg-text-primary/30 lg:hidden transition-opacity duration-200",
          mobileOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={onCloseMenu}
        aria-hidden="true"
      />
      <aside
        className={clsx(
          "z-40 lg:z-20 flex flex-col flex-shrink-0 h-screen bg-surface-base border-r border-border-soft",
          "transition-transform duration-200 lg:transition-[width]",
          "fixed top-0 left-0 w-[264px] lg:static lg:h-auto",
          collapsed ? "lg:w-[64px]" : "lg:w-[240px]",
          mobileOpen ? "translate-x-0 lg:translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {content}
      </aside>
    </>
  );
}