"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName, resolveIconName } from "@/components/ui/icon";

export type ActionCardSeverity =
  | "critical"
  | "urgent"
  | "high"
  | "warning"
  | "moderate"
  | "routine"
  | "normal"
  | "info";

export interface PrimaryActionCardProps {
  title: string;
  description?: string;
  actionLabel: string;
  onAction?: () => void;
  actionHref?: string;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionHref?: string;
  severity?: ActionCardSeverity;
  severityLabel?: string;
  badge?: ReactNode;
  icon?: IconName | string;
  loading?: boolean;
  loadingLabel?: string;
  error?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
  locale?: "vi" | "en";
  className?: string;
  children?: ReactNode;
}

const SEVERITY_CONFIG: Record<
  ActionCardSeverity,
  { tone: BadgeTone; labelVi: string; labelEn: string; icon: IconName }
> = {
  critical: {
    tone: "danger",
    labelVi: "Khẩn cấp",
    labelEn: "Critical",
    icon: "warning",
  },
  urgent: {
    tone: "danger",
    labelVi: "Khẩn cấp",
    labelEn: "Urgent",
    icon: "warning",
  },
  high: {
    tone: "warn",
    labelVi: "Ưu tiên cao",
    labelEn: "High priority",
    icon: "warning",
  },
  warning: {
    tone: "warn",
    labelVi: "Cần chú ý",
    labelEn: "Attention",
    icon: "warning",
  },
  moderate: {
    tone: "warn",
    labelVi: "Cần theo dõi",
    labelEn: "Moderate",
    icon: "progress",
  },
  routine: {
    tone: "neutral",
    labelVi: "Thường quy",
    labelEn: "Routine",
    icon: "calendar",
  },
  normal: {
    tone: "neutral",
    labelVi: "Bình thường",
    labelEn: "Normal",
    icon: "check",
  },
  info: {
    tone: "brand",
    labelVi: "Gợi ý",
    labelEn: "Suggested",
    icon: "clinical-notes",
  },
};

export function PrimaryActionCard({
  title,
  description,
  actionLabel,
  onAction,
  actionHref,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionHref,
  severity,
  severityLabel,
  badge,
  icon,
  loading = false,
  loadingLabel,
  error,
  onRetry,
  retryLabel,
  locale = "vi",
  className = "",
  children,
}: PrimaryActionCardProps) {
  const isEn = locale === "en";
  const defaultRetryText = retryLabel ?? (isEn ? "Try again" : "Thử lại");

  const severityMeta = severity ? SEVERITY_CONFIG[severity] : undefined;
  const computedSeverityLabel =
    severityLabel ??
    (severityMeta
      ? isEn
        ? severityMeta.labelEn
        : severityMeta.labelVi
      : undefined);

  return (
    <section
      className={`fluent-card relative flex flex-col justify-between overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 transition-shadow duration-150 ${className}`}
      aria-busy={loading || undefined}
      data-testid="primary-action-card"
    >
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            {icon ? (
              <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
                <Icon name={resolveIconName(icon)} size="1.2rem" />
              </span>
            ) : null}
            <h2 className="text-base font-semibold leading-snug text-[var(--text-primary)]">
              {title}
            </h2>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {badge}
            {severityMeta && computedSeverityLabel ? (
              <Badge tone={severityMeta.tone} icon={severityMeta.icon}>
                {computedSeverityLabel}
              </Badge>
            ) : null}
          </div>
        </div>

        {description ? (
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            {description}
          </p>
        ) : null}

        {children ? <div className="mt-3">{children}</div> : null}

        {error ? (
          <div
            role="alert"
            className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[var(--status-danger-text)]"
            data-testid="card-inline-error"
          >
            <div className="flex items-center gap-1.5">
              <Icon name="warning" size="1rem" className="shrink-0" />
              <span>{error}</span>
            </div>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="font-semibold underline hover:no-underline"
              >
                {defaultRetryText}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2.5 pt-1">
        {actionHref ? (
          <Link
            href={actionHref}
            onClick={onAction}
            className="fluent-button-primary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] px-4 py-2 text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-55"
            aria-disabled={loading || undefined}
          >
            {loading && loadingLabel ? loadingLabel : actionLabel}
          </Link>
        ) : (
          <Button
            variant="primary"
            onClick={onAction}
            loading={loading}
            loadingLabel={loadingLabel}
            disabled={loading}
          >
            {actionLabel}
          </Button>
        )}

        {secondaryActionLabel && secondaryActionHref ? (
          <Link
            href={secondaryActionHref}
            onClick={onSecondaryAction}
            className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            {secondaryActionLabel}
          </Link>
        ) : secondaryActionLabel && onSecondaryAction ? (
          <Button
            variant="ghost"
            onClick={onSecondaryAction}
            disabled={loading}
          >
            {secondaryActionLabel}
          </Button>
        ) : null}
      </div>
    </section>
  );
}

export default PrimaryActionCard;
