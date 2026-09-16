import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

const links = [
  { href: "/incidents/dashboard", label: "Dashboard" },
  { href: "/incidents", label: "Incidents" },
  { href: "/security", label: "Security Checker" },
];

export default function LandingNav() {
  return (
    <header className="sticky top-0 z-40 bg-page-bg/90 backdrop-blur border-b border-border-soft">
      <div className="max-w-screen-xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-accent-soft text-accent grid place-items-center text-[12px] font-bold">
            IC
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-text-primary">Incident Copilot</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="px-3 py-1.5 rounded-md text-[13px] font-medium text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors duration-150"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href="/incidents/dashboard"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-[13px] font-medium shadow-sm hover:brightness-95 transition-all duration-150"
          >
            Open App <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>
    </header>
  );
}