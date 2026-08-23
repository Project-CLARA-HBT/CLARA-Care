"use client";

import React from "react";

export type StatusTone = "success" | "warning" | "danger" | "info" | "unknown";

interface StatusChipProps {
  tone: StatusTone;
  label: string;
  icon?: React.ReactNode;
  size?: "sm" | "md";
  className?: string;
}

const TONE_CLASSES: Record<StatusTone, string> = {
  success:
    "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border-[var(--status-success-border)]",
  warning:
    "bg-[var(--status-warning-bg)] text-[var(--status-warning-text)] border-[var(--status-warning-border)]",
  danger:
    "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border-[var(--status-danger-border)]",
  info:
    "bg-[var(--status-info-bg)] text-[var(--status-info-text)] border-[var(--status-info-border)]",
  unknown:
    "bg-[var(--status-unknown-bg)] text-[var(--status-unknown-text)] border-[var(--status-unknown-border)]",
};

export function StatusChip({
  tone,
  label,
  icon,
  size = "md",
  className = "",
}: StatusChipProps) {
  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-xs gap-1"
      : "px-2.5 py-1 text-xs sm:text-sm gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium leading-none tracking-tight select-none ${sizeClasses} ${TONE_CLASSES[tone]} ${className}`}
      role="status"
    >
      {icon && <span className="shrink-0 flex items-center">{icon}</span>}
      <span>{label}</span>
    </span>
  );
}

export default StatusChip;
