"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
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

export function SurfaceCard({
  children,
  className = "",
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <section
      className={`rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-[var(--shadow-sm)] transition ${
        interactive
          ? "hover:-translate-y-0.5 hover:shadow-[var(--shadow-float)] hover:border-[color:var(--shell-border-strong)]/60"
          : ""
      } ${className}`}
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
            <span className="material-symbols-outlined text-xl">{icon}</span>
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
        <span className="material-symbols-outlined mt-0.5 text-lg" aria-hidden="true">
          error
        </span>
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
      <span
        className="material-symbols-outlined inline-flex h-14 w-14 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-2xl text-[var(--text-brand)]"
        aria-hidden="true"
      >
        {icon}
      </span>
      <h2 className="mt-4 text-base font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  );
}
