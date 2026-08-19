"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon, type IconName, resolveIconName } from "@/components/ui/icon";

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: IconName | string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionHref?: string;
  badge?: ReactNode;
  locale?: "vi" | "en";
  compact?: boolean;
  className?: string;
  children?: ReactNode;
}

export function EmptyState({
  title,
  description,
  icon = "clinical-notes",
  actionLabel,
  onAction,
  actionHref,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionHref,
  badge,
  compact = false,
  className = "",
  children,
}: EmptyStateProps) {
  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-[var(--radius-xl)] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-panel)]/50 text-center ${
        compact ? "p-4 sm:p-6" : "p-6 sm:p-10"
      } ${className}`}
      data-testid="empty-state"
    >
      {icon ? (
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-[var(--radius-pill)] bg-[var(--surface-muted)] text-[var(--text-brand)] shadow-sm">
          <Icon name={resolveIconName(icon)} size="1.5rem" />
        </div>
      ) : null}

      {badge ? <div className="mt-3">{badge}</div> : null}

      <h3
        className={`font-semibold text-[var(--text-primary)] ${
          compact ? "mt-2.5 text-sm sm:text-base" : "mt-3.5 text-base sm:text-lg"
        }`}
      >
        {title}
      </h3>

      {description ? (
        <p className="mt-1.5 max-w-md text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
          {description}
        </p>
      ) : null}

      {children ? <div className="mt-4 w-full max-w-sm">{children}</div> : null}

      {(actionLabel || secondaryActionLabel) ? (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
          {actionLabel && actionHref ? (
            <Link
              href={actionHref}
              className="fluent-button-primary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] px-4 py-2 text-sm font-semibold transition-colors"
            >
              {actionLabel}
            </Link>
          ) : actionLabel && onAction ? (
            <Button variant="primary" onClick={onAction}>
              {actionLabel}
            </Button>
          ) : null}

          {secondaryActionLabel && secondaryActionHref ? (
            <Link
              href={secondaryActionHref}
              className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {secondaryActionLabel}
            </Link>
          ) : secondaryActionLabel && onSecondaryAction ? (
            <Button variant="ghost" onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default EmptyState;
