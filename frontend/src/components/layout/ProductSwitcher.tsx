"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, AlertTriangle, Check, ChevronsUpDown } from "lucide-react";
import clsx from "clsx";

export type Product = "incidents" | "security";

export const PRODUCTS: { id: Product; label: string; sub: string; href: string; icon: typeof ShieldCheck; color: string }[] = [
  { id: "incidents", label: "Incident Manager", sub: "Track and resolve incidents", href: "/incidents", icon: AlertTriangle, color: "#2F5FD0" },
  { id: "security", label: "Security Checker", sub: "Scan repos and findings", href: "/security", icon: ShieldCheck, color: "#6B56D3" },
];

export function useProduct(): Product {
  const pathname = usePathname();
  if (pathname.startsWith("/security")) return "security";
  return "incidents";
}

export default function ProductSwitcher() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const product = useProduct();
  const current = PRODUCTS.find((p) => p.id === product) ?? PRODUCTS[0];

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border-soft bg-surface-sunken hover:bg-surface-elevated transition-colors duration-150"
        aria-label="Switch product"
        aria-expanded={open}
      >
        <current.icon size={14} style={{ color: current.color }} />
        <span className="flex items-center gap-1.5">
          <span className="text-[13px] font-medium text-text-primary">{current.label}</span>
          <ChevronsUpDown size={14} className="text-text-tertiary" />
        </span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-2 w-[260px] bg-surface-base border border-border-strong rounded-lg shadow-lg p-1 z-50 animate-scale-in">
          {PRODUCTS.map((p) => {
            const active = p.id === product;
            return (
              <Link
                key={p.id}
                href={p.href}
                onClick={() => setOpen(false)}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors duration-150",
                  active ? "bg-accent-soft" : "hover:bg-surface-sunken"
                )}
              >
                <span
                  className="w-7 h-7 rounded-md grid place-items-center flex-shrink-0"
                  style={{ backgroundColor: `${p.color}14`, color: p.color }}
                >
                  <p.icon size={15} />
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-[13px] font-medium text-text-primary">{p.label}</span>
                  <span className="block text-[11px] text-text-secondary truncate">{p.sub}</span>
                </span>
                {active && <Check size={14} className="text-accent" />}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}