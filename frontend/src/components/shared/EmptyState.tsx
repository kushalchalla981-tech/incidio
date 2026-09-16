import clsx from "clsx";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export default function EmptyState({ icon: Icon, title, description, action, className }: Props) {
  return (
    <div className={clsx("flex flex-col items-center justify-center text-center py-12 px-6", className)}>
      {Icon && (
        <div className="w-12 h-12 rounded-full bg-accent-soft text-accent grid place-items-center mb-4">
          <Icon size={20} />
        </div>
      )}
      <h3 className="text-[15px] font-semibold text-text-primary">{title}</h3>
      {description && <p className="text-sm text-text-secondary mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}