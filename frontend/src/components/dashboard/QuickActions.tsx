import Link from "next/link";
import { Plus, List, Terminal, ShieldCheck, ArrowRight } from "lucide-react";

const actions = [
  { href: "/incidents/new", label: "New Incident", desc: "Declare and kick off an incident", icon: Plus },
  { href: "/incidents", label: "View Incidents", desc: "Browse and filter the board", icon: List },
  { href: "/incidents/logs", label: "Log Explorer", desc: "Search and trace log streams", icon: Terminal },
  { href: "/security", label: "Security Checker", desc: "Scan repos for vulnerabilities", icon: ShieldCheck },
];

export default function QuickActions() {
  return (
    <div className="space-y-2">
      {actions.map(({ href, label, desc, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className="flex items-center gap-3 px-3 py-2.5 rounded-md border border-border-soft bg-surface-sunken hover:bg-surface-elevated hover:border-border-strong transition-colors duration-150 group"
        >
          <span className="w-8 h-8 rounded-md bg-surface-base border border-border-soft grid place-items-center text-text-secondary flex-shrink-0">
            <Icon size={15} />
          </span>
          <span className="flex-1 min-w-0">
            <span className="block text-[13px] font-medium text-text-primary">{label}</span>
            <span className="block text-[11px] text-text-secondary truncate">{desc}</span>
          </span>
          <ArrowRight size={14} className="text-text-tertiary group-hover:text-accent group-hover:translate-x-0.5 transition-all duration-150 flex-shrink-0" />
        </Link>
      ))}
    </div>
  );
}