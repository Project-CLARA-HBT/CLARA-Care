"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/icon";

export type InlineErrorSeverity = "error" | "warning" | "info";

export interface InlineErrorProps {
  message: string;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
  onDismiss?: () => void;
  dismissLabel?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionHref?: string;
  severity?: InlineErrorSeverity;
  locale?: "vi" | "en";
  compact?: boolean;
  className?: string;
  children?: ReactNode;
}

const SEVERITY_STYLES: Record<
  InlineErrorSeverity,
  {
    container: string;
    text: string;
    border: string;
    icon: IconName;
    defaultTitleVi: string;
    defaultTitleEn: string;
  }
> = {
  error: {
    container: "bg-[var(--status-danger-bg)] border-[color:var(--status-danger-border)]",
    text: "text-[var(--status-danger-text)]",
    border: "border-[color:var(--status-danger-border)]",
    icon: "warning",
    defaultTitleVi: "Đã xảy ra lỗi",
    defaultTitleEn: "Something went wrong",
  },
  warning: {
    container: "bg-[var(--status-warn-bg)] border-[color:var(--status-warn-border)]",
    text: "text-[var(--status-warn-text)]",
    border: "border-[color:var(--status-warn-border)]",
    icon: "warning",
    defaultTitleVi: "Cần chú ý",
    defaultTitleEn: "Attention needed",
  },
  info: {
    container: "bg-[var(--status-ok-bg)] border-[color:var(--status-ok-border)]",
    text: "text-[var(--status-ok-text)]",
    border: "border-[color:var(--status-ok-border)]",
    icon: "clinical-notes",
    defaultTitleVi: "Thông báo",
    defaultTitleEn: "Notice",
  },
};

export function InlineError({
  message,
  title,
  onRetry,
  retryLabel,
  onDismiss,
  dismissLabel,
  actionLabel,
  onAction,
  actionHref,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionHref,
  severity = "error",
  locale = "vi",
  compact = false,
  className = "",
  children,
}: InlineErrorProps) {
  const isEn = locale === "en";
  const styles = SEVERITY_STYLES[severity];
  const activeTitle =
    title ?? (isEn ? styles.defaultTitleEn : styles.defaultTitleVi);
  const activeRetryLabel = retryLabel ?? (isEn ? "Try again" : "Thử lại");
  const activeDismissLabel = dismissLabel ?? (isEn ? "Dismiss" : "Đóng");

  return (
    <div
      role={severity === "error" ? "alert" : "status"}
      aria-live={severity === "error" ? "assertive" : "polite"}
      className={`rounded-[var(--radius-lg)] border p-3 sm:p-4 text-sm ${styles.container} ${styles.text} ${className}`}
      data-testid={`inline-error-${severity}`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex shrink-0">
          <Icon name={styles.icon} size="1.25rem" />
        </span>

        <div className="min-w-0 flex-1">
          {activeTitle ? (
            <h4 className="font-semibold leading-snug">{activeTitle}</h4>
          ) : null}

          <p
            className={`leading-relaxed ${
              activeTitle ? "mt-1 text-xs sm:text-sm opacity-95" : "text-sm"
            }`}
          >
            {message}
          </p>

          {children ? <div className="mt-2">{children}</div> : null}

          {(onRetry || actionLabel || secondaryActionLabel) && !compact ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 pt-0.5 text-xs font-semibold">
              {onRetry ? (
                <button
                  type="button"
                  onClick={onRetry}
                  className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-current px-2.5 py-1 transition-opacity hover:opacity-80 active:opacity-60"
                  data-testid="inline-error-retry"
                >
                  <Icon name="progress" size="0.9em" />
                  <span>{activeRetryLabel}</span>
                </button>
              ) : null}

              {actionLabel && actionHref ? (
                <Link
                  href={actionHref}
                  className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-current px-2.5 py-1 hover:underline"
                >
                  <span>{actionLabel}</span>
                </Link>
              ) : actionLabel && onAction ? (
                <button
                  type="button"
                  onClick={onAction}
                  className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-current px-2.5 py-1 hover:underline"
                >
                  <span>{actionLabel}</span>
                </button>
              ) : null}

              {secondaryActionLabel && secondaryActionHref ? (
                <Link
                  href={secondaryActionHref}
                  className="hover:underline px-1"
                >
                  <span>{secondaryActionLabel}</span>
                </Link>
              ) : secondaryActionLabel && onSecondaryAction ? (
                <button
                  type="button"
                  onClick={onSecondaryAction}
                  className="hover:underline px-1"
                >
                  <span>{secondaryActionLabel}</span>
                </button>
              ) : null}
            </div>
          ) : null}
        </div>

        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            title={activeDismissLabel}
            aria-label={activeDismissLabel}
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-sm)] opacity-70 transition-opacity hover:opacity-100"
            data-testid="inline-error-dismiss"
          >
            <Icon name="close" size="1rem" />
          </button>
        ) : null}
      </div>

      {(onRetry || actionLabel) && compact ? (
        <div className="mt-2.5 flex items-center gap-2 border-t border-current/20 pt-2 text-xs font-semibold">
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="underline hover:no-underline"
              data-testid="inline-error-retry-compact"
            >
              {activeRetryLabel}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default InlineError;
