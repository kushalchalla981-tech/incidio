import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-white border border-accent hover:brightness-95 shadow-sm",
  secondary: "bg-surface-base text-text-primary border border-border-strong hover:border-text-tertiary hover:bg-surface-sunken shadow-sm",
  ghost: "bg-transparent text-text-secondary border border-transparent hover:text-text-primary hover:bg-surface-elevated",
  danger: "bg-transparent text-status-critical border border-border-strong hover:border-status-critical hover:bg-status-critical/5",
};

type Size = "sm" | "md" | "lg";

const sizes: Record<Size, string> = {
  sm: "px-2.5 py-1 text-[12px] rounded-md",
  md: "px-3.5 py-1.5 text-[13px] rounded-md",
  lg: "px-5 py-2.5 text-[14px] rounded-lg",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  children,
  className,
  disabled,
  ...props
}: Props) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 font-medium transition-colors duration-150 active:scale-[0.98] whitespace-nowrap",
        variants[variant],
        sizes[size],
        (disabled || loading) && "opacity-50 cursor-not-allowed active:scale-100",
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <span className="inline-block w-3 h-3 border-2 border-transparent border-t-current rounded-full animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

export function IconButton({
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      className={clsx(
        "w-8 h-8 grid place-items-center rounded-md border border-border-soft text-text-secondary bg-surface-base shadow-sm hover:border-border-strong hover:text-text-primary hover:bg-surface-sunken transition-colors duration-150",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}