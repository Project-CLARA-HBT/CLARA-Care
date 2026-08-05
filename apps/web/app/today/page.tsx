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
                    <div className="flex flex-col items-center gap-3 sm:flex-row">
                      <Button as="link" href="/lifemap/new">
                        {t(language, "today.createEpisode")}
                      </Button>
                      <Link
                        href="/chat"
                        className="focus-ring rounded-lg px-3 py-2 text-sm font-semibold text-[var(--text-brand)] hover:underline"
                      >
                        {t(language, "today.askTitle")}
                      </Link>
                    </div>
                  </EmptyState>
                </div>
              )}
            </SurfaceCard>

            {tasks.length ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-1 text-sm text-[var(--text-secondary)]">
                <span>
                  {today?.pending_confirmation_count ?? 0} {t(language, "today.notConclusion").toLocaleLowerCase(language === "vi" ? "vi-VN" : "en-US")}
                </span>
                <span>{today?.episodes.length ?? 0} · {t(language, "today.following")}</span>
                <Link href="/lifemap" className="focus-ring rounded-md font-semibold text-[var(--text-brand)] hover:underline">
                  {t(language, "today.openLifeMap")}
                </Link>
                <Link href="/chat" className="focus-ring rounded-md font-semibold text-[var(--text-brand)] hover:underline">
                  {t(language, "today.askTitle")}
                </Link>
              </div>
            ) : null}

            <details className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <summary className="focus-ring cursor-pointer rounded-md text-sm font-semibold text-[var(--text-primary)]">
                {t(language, "today.startHere")}
              </summary>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                {t(language, "today.startHereDescription")}
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {[
                  ["/chat", "today.askTitle", "today.askDescription"],
                  ["/medicines", "today.medicineTitle", "today.medicineDescription"],
                  ["/phr", "today.recordTitle", "today.recordDescription"],
                  ["/visits", "today.visitTitle", "today.visitDescription"],
                ].map(([href, title, description]) => (
                  <Link key={href} href={href} className="focus-ring rounded-lg p-3 hover:bg-[var(--surface-muted)]">
                    <span className="block text-sm font-semibold text-[var(--text-brand)]">
                      {t(language, title as Parameters<typeof t>[1])} · {t(language, "today.openAction")}
                    </span>
                    <span className="mt-1 block text-sm text-[var(--text-secondary)]">
                      {t(language, description as Parameters<typeof t>[1])}
                    </span>
                  </Link>
                ))}
              </div>
            </details>
          </>
        )}
      </div>
    </PageShell>
  );
}
