export default function LiveBadge({ label = "Live" }: { label?: string }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-status-success/25 bg-status-success/10 text-status-success text-[10px] font-bold tracking-widest">
      <span className="w-1.5 h-1.5 rounded-full bg-status-success status-dot" />
      {label}
    </div>
  );
}