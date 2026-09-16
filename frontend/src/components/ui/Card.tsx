import clsx from "clsx";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  shine?: boolean; // retained for prop compatibility; disabled
  glow?: boolean; // retained for prop compatibility; disabled
  onClick?: () => void;
}

export default function Card({
  children,
  className,
  hover = false,
  onClick,
}: Props) {
  return (
    <div
      className={clsx(
        "bg-surface-base border border-border-soft rounded-lg p-5 shadow-sm",
        hover && "transition-all duration-150 hover:border-border-strong hover:shadow-card",
        onClick && "cursor-pointer",
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}