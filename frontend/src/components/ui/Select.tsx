"use client";

import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import type { SelectHTMLAttributes } from "react";

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
}

export default function Select({ options, className, ...props }: Props) {
  return (
    <div className={clsx("relative", className)}>
      <select
        className="w-full appearance-none py-1.5 pl-3 pr-7 border border-border-soft rounded-md bg-surface-base text-text-primary text-[13px] cursor-pointer shadow-sm outline-none transition-colors duration-150 hover:border-border-strong focus:border-accent"
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none" />
    </div>
  );
}