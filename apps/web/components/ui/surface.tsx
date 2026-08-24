"use client";

import type { HTMLAttributes, ReactNode } from "react";
import { useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/ui/icon";
import { t } from "@/lib/i18n/catalog";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

function useSurfaceLanguage(): UILanguage {
  const [language, setLanguage] = useState<UILanguage>("vi");
  useEffect(() => {
    setLanguage(getStoredUILanguage());
    return onUILanguageChange(setLanguage);
  }, []);
  return language;
}

/**
 * Surface primitives are used by many routes. Resolve the legacy Material
 * Symbol names at this boundary so a late or missing icon font can never
 * render its raw glyph name (the historic source of visible "?" icons).
 */
function resolveSurfaceIcon(name: string): IconName {
  const icons: Record<string, IconName> = {
    add: "arrow-right",
    assignment: "clinical-notes",
    calendar_today: "calendar",
    description: "clinical-notes",
    diversity_1: "contact",
    event_available: "calendar",
    family_restroom: "contact",
    groups: "contact",
    lock: "warning",
    medication: "medication",
    route: "progress",
    task_alt: "check",
    warning: "warning",
  };
  return icons[name] ?? "clinical-notes";
}

export function SurfaceCard({
  children,
  className = "",
  interactive = false,
  ...rest
}: HTMLAttributes<HTMLElement> & {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <section
      className={`rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] transition-colors ${
        interactive
          ? "hover:border-[color:var(--shell-border-strong)]/60 hover:bg-[var(--surface-muted)]"
          : ""
      } ${className}`}
      {...rest}
    >
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "brand",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: string;
  tone?: "brand" | "ok" | "warn" | "danger" | "neutral";
}) {
  const toneRing: Record<string, string> = {
    brand: "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
    ok: "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
    warn: "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
    danger: "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
    neutral: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
  };
  return (
    <SurfaceCard className="p-5" interactive>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-[var(--text-secondary)]">{label}</p>
          <p className="mt-2 text-[2rem] font-semibold leading-none tracking-[-0.02em] text-[var(--text-primary)]">
            {value}
          </p>
          {hint ? <p className="mt-2 text-xs text-[var(--text-muted)]">{hint}</p> : null}
        </div>
        {icon ? (
          <span
            className={`grid h-11 w-11 shrink-0 place-items-center rounded-[var(--radius-lg)] ${toneRing[tone]}`}
            aria-hidden="true"
          >
            <Icon name={resolveSurfaceIcon(icon)} size={20} />
          </span>
        ) : null}
      </div>
    </SurfaceCard>
  );
}

export function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const language = useSurfaceLanguage();
  return (
    <div
      role="alert"
      className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-sm text-[var(--status-danger-text)]"
    >
      <div className="flex items-start gap-3">
        <Icon name="warning" className="mt-0.5" size={18} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{t(language, "surface.loadFailed")}</p>
          <p className="mt-1 leading-5">{message}</p>
        </div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-[var(--radius-md)] border border-current px-3 py-1.5 font-medium transition hover:bg-[var(--status-danger-bg)]"
          >
              {t(language, "surface.retry")}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function LoadingCards({ count = 3 }: { count?: number }) {
  const language = useSurfaceLanguage();
  return (
    <div aria-label={t(language, "surface.loading")} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className="h-28 animate-pulse rounded-[var(--radius-xl)] bg-[var(--surface-muted)]"
        />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  children,
}: {
  icon: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-xl)] border border-dashed border-[color:var(--shell-border-strong)]/50 bg-[var(--surface-muted)]/50 px-5 py-12 text-center">
      <span className="inline-flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
        <Icon name={resolveSurfaceIcon(icon)} size={26} aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-base font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  );
}
