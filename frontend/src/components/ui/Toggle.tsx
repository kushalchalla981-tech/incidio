"use client";

import { useState } from "react";
import clsx from "clsx";

interface Props {
  defaultChecked?: boolean;
  checked?: boolean;
  onChange?: (value: boolean) => void;
  label?: string;
  description?: string;
}

export default function Toggle({ defaultChecked = false, checked, onChange, label, description }: Props) {
  const [internal, setInternal] = useState(defaultChecked);
  const on = checked ?? internal;

  return (
    <div className="flex items-center justify-between gap-4">
      {(label || description) && (
        <div>
          {label && <div className="text-[13px] font-medium text-text-primary">{label}</div>}
          {description && <div className="text-[12px] text-text-secondary mt-0.5">{description}</div>}
        </div>
      )}
      <button
        onClick={() => {
          const next = !on;
          setInternal(next);
          onChange?.(next);
        }}
        className={clsx(
          "relative w-9 h-5 rounded-full transition-colors duration-150 flex-shrink-0",
          on ? "bg-accent" : "bg-surface-elevated border border-border-strong"
        )}
        role="switch"
        aria-checked={on}
      >
        <span
          className={clsx(
            "absolute top-[2px] left-[2px] w-4 h-4 rounded-full shadow-sm transition-transform duration-150",
            on ? "translate-x-4 bg-white" : "bg-text-tertiary"
          )}
        />
      </button>
    </div>
  );
}