"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/ui/surface";
import { getLifeMapToday, type LifeMapToday } from "@/lib/lifemap";
import { t } from "@/lib/i18n/catalog";
import { getStoredUILanguage, onUILanguageChange, type UILanguage } from "@/lib/ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

function dueLabel(value: string | null, language: UILanguage): string {
  if (!value) return t(language, "today.noDueDate");
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? t(language, "today.noDueDate")
    : date.toLocaleString(language === "vi" ? "vi-VN" : "en-US", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
}

const QUICK_ACTIONS = [
  {
    href: "/chat",
    icon: "chat_paste_go",
    title: "today.askTitle",
    description: "today.askDescription",
  },
  {
    href: "/medicines",
    icon: "medication",
    title: "today.medicineTitle",
    description: "today.medicineDescription",
  },
  {
    href: "/phr",
    icon: "description",
    title: "today.recordTitle",
    description: "today.recordDescription",
  },
  {
    href: "/lifemap/visit-prep",
    icon: "event_available",
    title: "today.visitTitle",
    description: "today.visitDescription",
  },
] as const;

export default function TodayPage() {
  const [today, setToday] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [language, setLanguage] = useState<UILanguage>("vi");

  useEffect(() => {
    setLanguage(getStoredUILanguage());
    return onUILanguageChange(setLanguage);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setToday(await getLifeMapToday());
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "today.connectionError")));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void load();
  }, [load]);

  const tasks = today?.tasks ?? [];

  return (
    <PageShell
      variant="plain"
      title={t(language, "today.title")}
      description={t(language, "today.description")}
    >
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        <SurfaceCard className="p-5">
          <div className="max-w-2xl">
            <h2 className="font-semibold text-[var(--text-primary)]">
              {t(language, "today.startHere")}
            </h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {t(language, "today.startHereDescription")}
            </p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {QUICK_ACTIONS.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="focus-ring group flex min-h-28 items-start gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/45 p-4 transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-panel)]"
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                  <span className="material-symbols-outlined text-xl" aria-hidden="true">
                    {action.icon}
                  </span>
                </span>
                <span className="min-w-0">
                  <span className="block font-medium text-[var(--text-primary)]">
                    {t(language, action.title)}
                  </span>
                  <span className="mt-1 block text-sm leading-5 text-[var(--text-secondary)]">
                    {t(language, action.description)}
                  </span>
                  <span className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-[var(--text-brand)]">
                    {t(language, "today.openAction")}
                    <span className="material-symbols-outlined text-base" aria-hidden="true">
                      arrow_forward
                    </span>
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </SurfaceCard>

        {loading ? (
          <LoadingCards />
        ) : (
          <>
            <SurfaceCard className="overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[color:var(--shell-border)] px-5 py-4">
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">{t(language, "today.next")}</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    {t(language, "today.control")}
                  </p>
                </div>
                <Link
                  href="/lifemap"
                  className="focus-ring shrink-0 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {t(language, "today.openLifeMap")}
                </Link>
              </div>

              {tasks.length ? (
                <ul className="divide-y divide-[color:var(--shell-border)]">
                  {tasks.map((task) => (
                    <li
                      key={task.id}
                      className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center"
                    >
                      <span
                        className="material-symbols-outlined text-[var(--text-brand)]"
                        aria-hidden="true"
                      >
                        task_alt
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-[var(--text-primary)]">{task.title}</p>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {dueLabel(task.due_at, language)}
                        </p>
                      </div>
                      <Button as="link" href={`/today/tasks/${encodeURIComponent(task.id)}`} size="sm">
                        {t(language, "today.viewTask")}
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-5">
                  <EmptyState
                    icon="calendar_add_on"
                    title={t(language, "today.emptyTitle")}
                    description={t(language, "today.emptyDescription")}
                  >
                    <Button as="link" href="/lifemap">
                      {t(language, "today.createEpisode")}
                    </Button>
                  </EmptyState>
                </div>
              )}
            </SurfaceCard>
          </>
        )}
      </div>
    </PageShell>
  );
}
