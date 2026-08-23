"use client";

import React from "react";

interface DataRowProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  action?: React.ReactNode;
  divider?: boolean;
  className?: string;
}

export function DataRow({
  label,
  value,
  hint,
  action,
  divider = true,
  className = "",
}: DataRowProps) {
  return (
    <div
      className={`flex items-center justify-between py-3 gap-4 ${
        divider ? "border-b border-[var(--border-subtle)]" : ""
      } ${className}`}
    >
      <div className="min-w-0 flex-1">
        <div className="text-xs sm:text-sm font-medium text-[var(--text-secondary)]">
          {label}
        </div>
        {hint && (
          <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
            {hint}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-sm font-semibold text-[var(--text-primary)] text-right">
          {value}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  );
}

export default DataRow;
