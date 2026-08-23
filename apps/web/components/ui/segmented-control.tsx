"use client";

import React from "react";

export interface SegmentOption<T extends string = string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

interface SegmentedControlProps<T extends string = string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
  className?: string;
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  size = "md",
  className = "",
}: SegmentedControlProps<T>) {
  const sizeClasses =
    size === "sm"
      ? "p-0.5 text-xs rounded-lg"
      : "p-1 text-xs sm:text-sm rounded-xl";

  const buttonSizeClasses =
    size === "sm" ? "px-2.5 py-1" : "px-3 py-1.5";

  return (
    <div
      role="tablist"
      className={`inline-flex items-center bg-[var(--surface-2)] border border-[var(--border-subtle)] ${sizeClasses} ${className}`}
    >
      {options.map((option) => {
        const isSelected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            onClick={() => onChange(option.value)}
            className={`flex items-center justify-center gap-1.5 font-medium transition-all duration-150 rounded-lg ${buttonSizeClasses} ${
              isSelected
                ? "bg-[var(--surface-0)] text-[var(--text-primary)] font-semibold shadow-sm border border-[var(--border-subtle)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-1)]/50"
            }`}
          >
            {option.icon && <span className="shrink-0">{option.icon}</span>}
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default SegmentedControl;
