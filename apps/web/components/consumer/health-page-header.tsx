"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon, resolveIconName } from "@/components/ui/icon";

export interface ActiveProfileInfo {
  id?: string;
  name: string;
  relationship?: string;
  avatarUrl?: string;
}

export interface HeaderAction {
  label: string;
  onClick?: () => void;
  href?: string;
  icon?: string;
  loading?: boolean;
  disabled?: boolean;
}

export interface HealthPageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  activeProfile?: ActiveProfileInfo | null;
  onSwitchProfile?: () => void;
  primaryAction?: HeaderAction;
  secondaryAction?: HeaderAction;
  backHref?: string;
  backLabel?: string;
  locale?: "vi" | "en";
  className?: string;
  children?: ReactNode;
}

export function HealthPageHeader({
  title,
  subtitle,
  badge,
  activeProfile,
  onSwitchProfile,
  primaryAction,
  secondaryAction,
  backHref,
  backLabel,
  locale = "vi",
  className = "",
  children,
}: HealthPageHeaderProps) {
  const isEn = locale === "en";
  const defaultBackText = backLabel ?? (isEn ? "Back" : "Quay lại");
  const switchProfileText = isEn ? "Switch profile" : "Đổi hồ sơ";

  return (
    <header
      className={`page-intro flex flex-col gap-4 pb-4 border-b border-[color:var(--shell-border)]/60 sm:pb-5 ${className}`}
      data-testid="health-page-header"
    >
      {backHref ? (
        <div>
          <Link
            href={backHref}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            data-testid="health-page-back-link"
          >
            <Icon name="arrow-left" size="0.95rem" />
            <span>{defaultBackText}</span>
          </Link>
        </div>
      ) : null}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)] sm:text-2xl">
              {title}
            </h1>
            {badge ? <div>{badge}</div> : null}
          </div>

          {subtitle ? (
            <p className="mt-1 max-w-2xl text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
              {subtitle}
            </p>
          ) : null}

          {children ? <div className="mt-2">{children}</div> : null}
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          {activeProfile ? (
            <div
              className="app-profile-chip inline-flex items-center gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs"
              data-testid="header-active-profile"
            >
              <span className="app-profile-avatar inline-flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)] font-bold">
                {activeProfile.name.charAt(0).toUpperCase()}
              </span>
              <div className="flex flex-col text-left">
                <span className="font-semibold text-[var(--text-primary)] leading-tight">
                  {activeProfile.name}
                </span>
                {activeProfile.relationship ? (
                  <span className="text-[10px] text-[var(--text-muted)] leading-tight">
                    {activeProfile.relationship}
                  </span>
                ) : null}
              </div>
              {onSwitchProfile ? (
                <button
                  type="button"
                  onClick={onSwitchProfile}
                  title={switchProfileText}
                  aria-label={switchProfileText}
                  className="ml-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  data-testid="header-switch-profile-btn"
                >
                  <Icon name="chevron-down" size="0.85rem" />
                </button>
              ) : null}
            </div>
          ) : null}

          {secondaryAction ? (
            secondaryAction.href ? (
              <Link
                href={secondaryAction.href}
                className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] px-3 py-2 text-xs sm:text-sm font-medium"
              >
                {secondaryAction.icon ? (
                  <Icon name={resolveIconName(secondaryAction.icon)} size="1em" />
                ) : null}
                <span>{secondaryAction.label}</span>
              </Link>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={secondaryAction.onClick}
                disabled={secondaryAction.disabled}
                icon={secondaryAction.icon}
              >
                {secondaryAction.label}
              </Button>
            )
          ) : null}

          {primaryAction ? (
            primaryAction.href ? (
              <Link
                href={primaryAction.href}
                className="fluent-button-primary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] px-4 py-2 text-xs sm:text-sm font-semibold shadow-sm"
              >
                {primaryAction.icon ? (
                  <Icon name={resolveIconName(primaryAction.icon)} size="1em" />
                ) : null}
                <span>{primaryAction.label}</span>
              </Link>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={primaryAction.onClick}
                loading={primaryAction.loading}
                disabled={primaryAction.disabled}
                icon={primaryAction.icon}
              >
                {primaryAction.label}
              </Button>
            )
          ) : null}
        </div>
      </div>
    </header>
  );
}

export default HealthPageHeader;
