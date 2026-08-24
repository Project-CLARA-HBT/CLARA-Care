import type { HTMLAttributes, ReactNode } from "react";
import { Icon, resolveIconName } from "@/components/ui/icon";

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

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  children: ReactNode;
  icon?: string;
  className?: string;
}

export function Badge({
  tone = "neutral",
  children,
  icon,
  className = "",
  ...rest
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[var(--radius-pill)] border px-2.5 py-1 text-xs font-semibold ${TONES[tone]} ${className}`}
      {...rest}
    >
      {icon ? (
        <Icon name={resolveIconName(icon)} size="0.95rem" className="leading-none" />
      ) : null}
      {children}
    </span>
  );
}

export default Badge;
