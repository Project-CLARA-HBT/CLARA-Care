import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "brand" | "ok" | "warn" | "danger";

const TONES: Record<BadgeTone, string> = {
  neutral:
    "bg-[var(--status-neutral-bg)] text-[var(--status-neutral-text)] border-[color:var(--status-neutral-border)]",
  brand:
    "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border-[color:var(--brand-500)]/30",
  ok: "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border-[color:var(--status-ok-border)]",
  warn: "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border-[color:var(--status-warn-border)]",
  danger:
    "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border-[color:var(--status-danger-border)]",
};

export function Badge({
  tone = "neutral",
  children,
  icon,
  className = "",
}: {
  tone?: BadgeTone;
  children: ReactNode;
  icon?: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[var(--radius-pill)] border px-2.5 py-1 text-xs font-semibold ${TONES[tone]} ${className}`}
    >
      {icon ? (
        <span className="material-symbols-outlined text-[0.95rem] leading-none" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </span>
  );
}
