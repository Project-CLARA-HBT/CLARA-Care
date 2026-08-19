"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import Icon, { type IconName } from "@/components/ui/icon";
import { InlineError, LoadingCards } from "@/components/ui/surface";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { getLifeMapToday, type LifeMapTask, type LifeMapToday } from "@/lib/lifemap";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type TodayView = "active" | "completed" | "caught-up" | "first-time";

const quickActions: Array<{
  href: string;
  icon: IconName;
  title: "today.askTitle" | "today.medicineTitle" | "today.visitTitle" | "today.recordTitle";
  description:
    | "today.askDescription"
    | "today.medicineDescription"
    | "today.visitDescription"
    | "today.recordDescription";
}> = [
  { href: "/chat", icon: "clinical-notes", title: "today.askTitle", description: "today.askDescription" },
  { href: "/medicines", icon: "medication", title: "today.medicineTitle", description: "today.medicineDescription" },
  { href: "/visits/new", icon: "progress", title: "today.visitTitle", description: "today.visitDescription" },
  { href: "/phr", icon: "user-card", title: "today.recordTitle", description: "today.recordDescription" },
];

function dueLabel(value: string | null, language: "vi" | "en"): string {
  if (!value) return t(language, "today.noDueDate");
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? t(language, "today.noDueDate")
    : formatLocaleDate(language, date, {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function taskHref(task: LifeMapTask): string {
  return `/today/tasks/${encodeURIComponent(task.id)}`;
}

export default function TodayPage() {
  const router = useRouter();
  const language = useUILanguage();

  useEffect(() => {
    router.replace("/home");
  }, [router]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setToday(await getLifeMapToday());
    } catch (cause) {
      setToday(null);
      setError(safeUserFacingError(cause, t(language, "today.connectionError")));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void load();
  }, [load]);

  const tasks = today?.tasks ?? [];
  const completedToday = Math.max(0, today?.completed_today_count ?? 0);
  const activityDays = today?.activity_days ?? [];
  const activeDays = activityDays.filter((item) => item.completed_count > 0).length;
  const view: TodayView = tasks.length
    ? "active"
    : completedToday > 0
      ? "completed"
      : (today?.episodes.length ?? 0) > 0
        ? "caught-up"
        : "first-time";
  const nextTask = tasks[0] ?? null;
  const upcomingTasks = tasks.slice(1);
  const maxDailyCompleted = Math.max(1, ...activityDays.map((item) => item.completed_count));

  const statusLabel = useMemo(() => {
    if (view === "active") {
      return t(language, "today.openTaskCount", {
        count: formatLocaleNumber(language, tasks.length),
      });
    }
    if (view === "completed") {
      return t(language, "today.completedTaskCount", {
        count: formatLocaleNumber(language, completedToday),
      });
    }
    return t(language, "today.noOpenTasks");
  }, [completedToday, language, tasks.length, view]);

  return (
    <PageShell
      variant="plain"
      title={t(language, "today.title")}
      description={t(language, "today.description")}
    >
      {error ? (
        <InlineError message={error} onRetry={() => void load()} />
      ) : loading ? (
        <LoadingCards count={2} />
      ) : today ? (
        <div className="space-y-8">
          <section className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5" aria-labelledby="today-rhythm">
            <div className="flex items-center gap-3">
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${view === "completed" ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]" : "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"}`}>
                <Icon name={view === "completed" ? "check" : "calendar"} />
              </span>
              <div>
                <h2 id="today-rhythm" className="font-semibold text-[var(--text-primary)]">{t(language, "today.statusTitle")}</h2>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{t(language, "today.control")}</p>
              </div>
            </div>
            <span className="inline-flex min-h-9 w-fit max-w-full items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold leading-5 text-[var(--text-brand)]">
              {statusLabel}
            </span>
          </section>

          {view === "active" && nextTask ? (
            <ActiveToday
              language={language}
              nextTask={nextTask}
              upcomingTasks={upcomingTasks}
              pendingConfirmationCount={today.pending_confirmation_count}
            />
          ) : view === "completed" ? (
            <CompletedToday
              language={language}
              completedToday={completedToday}
              activeDays={activeDays}
              activityDays={activityDays}
              maxDailyCompleted={maxDailyCompleted}
            />
          ) : (
            <EmptyToday language={language} caughtUp={view === "caught-up"} />
          )}
        </div>
      ) : null}
    </PageShell>
  );
}

function ActiveToday({
  language,
  nextTask,
  upcomingTasks,
  pendingConfirmationCount,
}: {
  language: "vi" | "en";
  nextTask: LifeMapTask;
  upcomingTasks: LifeMapTask[];
  pendingConfirmationCount: number;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="relative overflow-hidden rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7">
          <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-[var(--surface-brand-soft)] blur-3xl" />
          <div className="relative">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              <Icon name="progress" size={16} className="text-[var(--status-warn-text)]" />
              {t(language, "today.next")}
            </p>
            <h2 className="mt-4 text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">{nextTask.title}</h2>
            {nextTask.episode_title ? <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{nextTask.episode_title}</p> : null}
            <div className="mt-5 flex flex-wrap items-center gap-2 text-sm text-[var(--text-secondary)]">
              <Icon name="calendar" size={17} />
              <time dateTime={nextTask.due_at ?? undefined}>{dueLabel(nextTask.due_at, language)}</time>
              {nextTask.status ? <span className="rounded-full bg-[var(--surface-muted)] px-3 py-1 text-xs font-semibold">{nextTask.status === "in_progress" ? t(language, "today.following") : t(language, "today.taskDetail.acceptedTask")}</span> : null}
            </div>
            <div className="mt-7 flex justify-end border-t border-[color:var(--shell-border)] pt-5">
              <Button as="link" href={taskHref(nextTask)} icon="arrow_forward">
                {t(language, "today.viewTask")}
              </Button>
            </div>
          </div>
        </section>

        {upcomingTasks.length ? (
          <section aria-labelledby="today-upcoming">
            <h2 id="today-upcoming" className="mb-3 flex items-center gap-2 font-semibold text-[var(--text-primary)]"><Icon name="calendar" className="text-[var(--text-muted)]" />{t(language, "today.upcoming")}</h2>
            <ul className="divide-y divide-[color:var(--shell-border)] overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              {upcomingTasks.map((task) => (
                <li key={task.id}>
                  <Link href={taskHref(task)} className="focus-ring flex min-h-16 items-center gap-4 px-4 py-3 transition hover:bg-[var(--surface-muted)]">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 border-[color:var(--shell-border-strong)]" aria-hidden="true" />
                    <span className="min-w-0 flex-1"><span className="block font-medium text-[var(--text-primary)]">{task.title}</span><time dateTime={task.due_at ?? undefined} className="mt-1 block text-sm text-[var(--text-secondary)]">{dueLabel(task.due_at, language)}</time></span>
                    <Icon name="arrow-right" className="text-[var(--text-brand)]" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {pendingConfirmationCount > 0 ? (
          <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[var(--status-warn-text)]">
            {t(language, "today.pendingConfirmations", { count: formatLocaleNumber(language, pendingConfirmationCount) })} · {t(language, "today.notConclusion")}
          </p>
        ) : null}
      </div>
      <ActionPanel language={language} compact />
    </div>
  );
}

function CompletedToday({
  language,
  completedToday,
  activeDays,
  activityDays,
  maxDailyCompleted,
}: {
  language: "vi" | "en";
  completedToday: number;
  activeDays: number;
  activityDays: Array<{ date: string; completed_count: number }>;
  maxDailyCompleted: number;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="flex min-h-72 flex-col items-center justify-center rounded-[14px] border border-t-[#2A3950] border-[color:var(--status-ok-border)] bg-[var(--surface-panel)] p-7 text-center">
          <span className="grid h-20 w-20 place-items-center rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"><Icon name="check" size={38} /></span>
          <h2 className="mt-5 text-2xl font-semibold text-[var(--text-primary)]">{t(language, "today.completedTitle")}</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">{t(language, "today.completedDescription")}</p>
          <Button as="link" href="/lifemap" variant="secondary" className="mt-6">{t(language, "today.updateChange")}</Button>
        </section>

        {activityDays.length === 7 ? (
          <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6" aria-labelledby="today-weekly-progress">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="today-weekly-progress" className="font-semibold text-[var(--text-primary)]">{t(language, "today.weeklyProgress")}</h2>
              <span className="rounded-full bg-[var(--surface-brand-soft)] px-3 py-1 text-xs font-semibold text-[var(--text-brand)]">{t(language, "today.activeDays", { count: formatLocaleNumber(language, activeDays) })}</span>
            </div>
            <div className="mt-7 flex h-40 items-end justify-between gap-2" role="list" aria-label={t(language, "today.weeklyProgress")}>
              {activityDays.map((day) => {
                const date = new Date(`${day.date}T12:00:00`);
                const label = formatLocaleDate(language, date, { weekday: "short" });
                const height = day.completed_count > 0 ? Math.max(24, Math.round((day.completed_count / maxDailyCompleted) * 100)) : 12;
                return (
                  <div key={day.date} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-2" role="listitem" aria-label={`${label}: ${formatLocaleNumber(language, day.completed_count)}`}>
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">{formatLocaleNumber(language, day.completed_count)}</span>
                    <span className={`w-full max-w-10 rounded-t-md border ${day.completed_count > 0 ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]" : "border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]"}`} style={{ height: `${height}%` }} aria-hidden="true" />
                    <span className="text-xs text-[var(--text-muted)]">{label}</span>
                  </div>
                );
              })}
            </div>
            <p className="sr-only">{t(language, "today.completedTaskCount", { count: formatLocaleNumber(language, completedToday) })}</p>
          </section>
        ) : null}
      </div>
      <ActionPanel language={language} compact />
    </div>
  );
}

function EmptyToday({ language, caughtUp }: { language: "vi" | "en"; caughtUp: boolean }) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="flex min-h-80 flex-col items-center justify-center rounded-[var(--radius-xl)] border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] p-7 text-center">
          <span className="grid h-20 w-20 place-items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]"><Icon name="calendar" size={36} /></span>
          <h2 className="mt-5 text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">{t(language, caughtUp ? "today.caughtUpTitle" : "today.firstTitle")}</h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">{t(language, caughtUp ? "today.caughtUpDescription" : "today.emptyDescription")}</p>
          <div className="mt-6 flex w-full max-w-sm flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row">
            <Button as="link" href={caughtUp ? "/lifemap" : "/lifemap/new"}>{caughtUp ? t(language, "today.viewJourney") : t(language, "today.createEpisode")}</Button>
            <Button as="link" href="/chat" variant="ghost">{t(language, "today.askTitle")}</Button>
          </div>
        </section>
        {!caughtUp ? (
          <ol className="grid gap-4 border-t border-[color:var(--shell-border)] pt-6 sm:grid-cols-3">
            {["today.stepGoal", "today.stepTask", "today.stepToday"].map((key, index) => (
              <li key={key} className="flex items-center gap-3 sm:flex-col sm:text-center"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-sm font-semibold text-[var(--text-brand)]">{index + 1}</span><span className="text-sm font-semibold text-[var(--text-secondary)]">{t(language, key as Parameters<typeof t>[1])}</span></li>
            ))}
          </ol>
        ) : null}
      </div>
      <ActionPanel language={language} />
    </div>
  );
}

function ActionPanel({ language, compact = false }: { language: "vi" | "en"; compact?: boolean }) {
  const items = compact ? quickActions.slice(0, 2) : quickActions;
  return (
    <aside className="space-y-4 lg:col-span-4" aria-labelledby="today-other-actions">
      <h2 id="today-other-actions" className="text-lg font-semibold text-[var(--text-primary)]">{t(language, compact ? "today.otherActions" : "today.startHere")}</h2>
      <div className="space-y-3">
        {items.map((item, index) => (
          <Link key={item.href} href={item.href} className={`focus-ring group flex min-h-20 items-center gap-4 rounded-[var(--radius-lg)] border p-4 transition ${index === 0 ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)]" : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:bg-[var(--surface-muted)]"}`}>
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--surface-panel)] text-[var(--text-brand)]"><Icon name={item.icon} /></span>
            <span className="min-w-0 flex-1"><span className="block font-semibold text-[var(--text-primary)]">{t(language, item.title)}</span><span className="mt-1 block text-sm leading-5 text-[var(--text-secondary)]">{t(language, item.description)}</span></span>
            <Icon name="arrow-right" className="text-[var(--text-brand)] transition group-hover:translate-x-1" />
          </Link>
        ))}
      </div>
    </aside>
  );
}
