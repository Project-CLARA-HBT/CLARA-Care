"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Icon, { type IconName } from "@/components/ui/icon";
import { InlineError, LoadingCards } from "@/components/ui/surface";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import {
  completeLifeMapTask,
  getLifeMapToday,
  type LifeMapEpisode,
  type LifeMapTask,
  type LifeMapToday,
} from "@/lib/lifemap";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type TodayView = "active" | "completed" | "caught-up" | "first-time";

interface QuickActionItem {
  href: string;
  icon: IconName;
  title: "today.askTitle" | "today.medicineTitle" | "today.visitTitle" | "today.recordTitle";
  description:
    | "today.askDescription"
    | "today.medicineDescription"
    | "today.visitDescription"
    | "today.recordDescription";
}

const quickActionItems: QuickActionItem[] = [
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

function priorityTone(priority: string): "danger" | "warn" | "brand" {
  if (priority === "urgent") return "danger";
  if (priority === "soon") return "warn";
  return "brand";
}

function priorityLabel(
  priority: string,
  language: "vi" | "en",
): string {
  if (priority === "urgent") return t(language, "lifemap.priority.urgent");
  if (priority === "soon") return t(language, "lifemap.priority.soon");
  if (priority === "routine") return t(language, "lifemap.priority.routine");
  return priority;
}

export default function TodayPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [today, setToday] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [askQuery, setAskQuery] = useState("");
  const [completingTaskId, setCompletingTaskId] = useState<string | null>(null);

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

  const handleCompleteTask = async (task: LifeMapTask) => {
    setCompletingTaskId(task.id);
    try {
      await completeLifeMapTask(task.id, task.version);
      await load();
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "today.taskDetail.completeError")));
    } finally {
      setCompletingTaskId(null);
    }
  };

  const tasks = today?.tasks ?? [];
  const episodes = today?.episodes ?? [];
  const completedToday = Math.max(0, today?.completed_today_count ?? 0);
  const activityDays = today?.activity_days ?? [];
  const activeDays = activityDays.filter((item) => item.completed_count > 0).length;
  const view: TodayView = tasks.length
    ? "active"
    : completedToday > 0
      ? "completed"
      : episodes.length > 0
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

  const dateHeader = useMemo(() => {
    const todayDate = today?.generated_at ? new Date(today.generated_at) : new Date();
    return formatLocaleDate(language, todayDate, {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  }, [language, today?.generated_at]);

  const handleAskSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (askQuery.trim()) {
      router.push(`/chat?q=${encodeURIComponent(askQuery.trim())}`);
    } else {
      router.push("/chat");
    }
  };

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
          {/* 1. High-Aesthetic Hero Greeting Section */}
          <section
            className="relative overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 shadow-xs"
            aria-labelledby="today-rhythm-heading"
          >
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[var(--surface-brand-soft)] blur-3xl opacity-75"
            />
            <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-2">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-brand)]">
                  {dateHeader}
                </p>
                <h2
                  id="today-rhythm-heading"
                  className="text-2xl font-bold tracking-tight text-[var(--text-primary)] sm:text-3xl"
                >
                  {t(language, "today.rhythmGreeting")}
                </h2>
                <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">
                  {t(language, "today.heroSubtitle")} {t(language, "today.control")}
                </p>
              </div>

              {/* Progress Pills & Status Badges */}
              <div className="flex flex-wrap items-center gap-2.5">
                {view === "active" ? (
                  <span className="inline-flex items-center gap-2 rounded-full border border-[color:var(--shell-border-strong)]/40 bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-brand)] shadow-xs">
                    <span className="h-2 w-2 rounded-full bg-[var(--brand-500)] animate-pulse" />
                    <span>{statusLabel}</span>
                    <span className="hidden sm:inline text-xs font-normal text-[var(--text-secondary)]">· {t(language, "today.statusInProgress")}</span>
                  </span>
                ) : null}

                {completedToday > 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3.5 py-1.5 text-xs font-semibold text-[var(--status-ok-text)]">
                    <Icon name="check" size={14} />
                    {t(language, "today.completedTaskCount", {
                      count: formatLocaleNumber(language, completedToday),
                    })}
                  </span>
                ) : null}

                <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-muted)]">
                  <Icon name="clinical-notes" size={13} />
                  {t(language, "today.noAlerts")}
                </span>

                <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--status-ok-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--status-ok-text)]">
                  <Icon name="check" size={13} />
                  {t(language, "today.statusSafe")}
                </span>
              </div>
            </div>
          </section>

          {/* State Specific Main Content */}
          {view === "active" && nextTask ? (
            <ActiveToday
              language={language}
              nextTask={nextTask}
              upcomingTasks={upcomingTasks}
              completedToday={completedToday}
              pendingConfirmationCount={today.pending_confirmation_count}
              episodes={episodes}
              activityDays={activityDays}
              activeDays={activeDays}
              maxDailyCompleted={maxDailyCompleted}
              completingTaskId={completingTaskId}
              onCompleteTask={handleCompleteTask}
              askQuery={askQuery}
              onAskQueryChange={setAskQuery}
              onAskSubmit={handleAskSubmit}
            />
          ) : view === "completed" ? (
            <CompletedToday
              language={language}
              completedToday={completedToday}
              episodes={episodes}
              activeDays={activeDays}
              activityDays={activityDays}
              maxDailyCompleted={maxDailyCompleted}
              askQuery={askQuery}
              onAskQueryChange={setAskQuery}
              onAskSubmit={handleAskSubmit}
            />
          ) : (
            <EmptyToday
              language={language}
              caughtUp={view === "caught-up"}
              episodes={episodes}
              activityDays={activityDays}
              activeDays={activeDays}
              maxDailyCompleted={maxDailyCompleted}
              askQuery={askQuery}
              onAskQueryChange={setAskQuery}
              onAskSubmit={handleAskSubmit}
            />
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
  completedToday,
  pendingConfirmationCount,
  episodes,
  activityDays,
  activeDays,
  maxDailyCompleted,
  completingTaskId,
  onCompleteTask,
  askQuery,
  onAskQueryChange,
  onAskSubmit,
}: {
  language: "vi" | "en";
  nextTask: LifeMapTask;
  upcomingTasks: LifeMapTask[];
  completedToday: number;
  pendingConfirmationCount: number;
  episodes: LifeMapEpisode[];
  activityDays: Array<{ date: string; completed_count: number }>;
  activeDays: number;
  maxDailyCompleted: number;
  completingTaskId: string | null;
  onCompleteTask: (task: LifeMapTask) => Promise<void>;
  askQuery: string;
  onAskQueryChange: (val: string) => void;
  onAskSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      {/* Main Agenda Column */}
      <div className="space-y-6 lg:col-span-8">
        {/* 2. Next Task Hero Bento with #2A3950 border & in-situ completion trigger */}
        <section
          className="relative overflow-hidden rounded-[var(--radius-xl)] border-2 border-[#2A3950] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-[0_4px_24px_rgba(0,0,0,0.18)]"
          aria-labelledby="today-next-task-heading"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-[var(--surface-brand-soft)] blur-3xl opacity-60"
          />
          <div className="relative">
            {/* Top metadata badge row */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  <Icon name="progress" size={14} className="text-[var(--status-warn-text)] animate-pulse" />
                  {t(language, "today.nextTaskLabel")}
                </span>
                <span className="text-[var(--text-muted)]">•</span>
                <time
                  dateTime={nextTask.due_at ?? undefined}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-secondary)]"
                >
                  <Icon name="calendar" size={14} />
                  {dueLabel(nextTask.due_at, language)}
                </time>
              </div>

              {nextTask.status ? (
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                  {nextTask.status === "in_progress"
                    ? t(language, "today.following")
                    : t(language, "today.taskDetail.acceptedTask")}
                </span>
              ) : null}
            </div>

            {/* Task Card Body */}
            <div className="mt-5 flex flex-col sm:flex-row items-start gap-4">
              <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-[var(--surface-brand-soft)] border border-[color:var(--status-ok-border)] text-[var(--text-brand)]">
                <Icon name="clinical-notes" size={24} />
              </div>
              <div className="min-w-0 flex-1">
                <h2
                  id="today-next-task-heading"
                  className="text-xl font-bold text-[var(--text-primary)] sm:text-2xl"
                >
                  {nextTask.title}
                </h2>
                {nextTask.episode_title ? (
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    {nextTask.episode_title}
                  </p>
                ) : null}
              </div>
            </div>

            {/* Detailed Instructions Bento Panel */}
            <div className="mt-5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/70 p-4 sm:p-5 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-brand)] uppercase tracking-wider">
                  <Icon name="clinical-notes" size={15} />
                  <span>{t(language, "today.instructionsTitle")}</span>
                </div>
                <span className="text-[11px] text-[var(--text-muted)]">
                  {t(language, "today.control")}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                {nextTask.episode_title ? `${nextTask.episode_title} · ` : ""}
                {t(language, "today.taskDetail.completeGuidance")}
              </p>
            </div>

            {/* In-situ Completion Trigger & Action Buttons */}
            <div className="mt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-t border-[color:var(--shell-border)]/60 pt-5">
              <span className="text-xs text-[var(--text-muted)]">
                {t(language, "today.next")}
              </span>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
                <Button
                  onClick={() => void onCompleteTask(nextTask)}
                  loading={completingTaskId === nextTask.id}
                  icon="check"
                  className="w-full sm:w-auto shadow-[0_4px_14px_rgba(164,201,255,0.15)] font-semibold"
                >
                  {t(language, "today.taskDetail.completeAction")}
                </Button>
                <Button
                  as="link"
                  href={taskHref(nextTask)}
                  variant="secondary"
                  icon="arrow_forward"
                  iconTrailing
                  className="w-full sm:w-auto font-semibold"
                >
                  {t(language, "today.viewTask")}
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Upcoming Timeline with Connecting Track */}
        <section aria-labelledby="today-upcoming" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2
              id="today-upcoming"
              className="flex items-center gap-2 text-lg font-bold text-[var(--text-primary)]"
            >
              <Icon name="calendar" className="text-[var(--text-brand)]" />
              {t(language, "today.timelineHeading")}
            </h2>
            <span className="text-xs font-semibold text-[var(--text-muted)]">
              {t(language, "today.upcoming")}
            </span>
          </div>

          {/* Completed Group (Collapsible) */}
          {completedToday > 0 ? (
            <details className="group rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden">
              <summary className="flex cursor-pointer items-center justify-between p-4 hover:bg-[var(--surface-muted)] transition-colors list-none">
                <div className="flex items-center gap-3">
                  <span className="grid h-7 w-7 place-items-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]">
                    <Icon name="check" size={16} />
                  </span>
                  <span className="text-sm font-semibold text-[var(--text-secondary)]">
                    {t(language, "today.completedGroupTitle", {
                      count: formatLocaleNumber(language, completedToday),
                    })}
                  </span>
                </div>
                <Icon
                  name="arrow-right"
                  size={16}
                  className="text-[var(--text-muted)] transition-transform group-open:rotate-90"
                />
              </summary>
              <div className="border-t border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/50 p-4 text-xs text-[var(--text-muted)]">
                <p className="flex items-center gap-2">
                  <Icon name="check" size={14} className="text-[var(--status-ok-text)]" />
                  {t(language, "today.completedBadge")} ({t(language, "today.completedTaskCount", { count: formatLocaleNumber(language, completedToday) })})
                </p>
              </div>
            </details>
          ) : null}

          {/* Upcoming Timeline with Continuous Connecting Track */}
          {upcomingTasks.length ? (
            <div className="relative pl-6 sm:pl-8 space-y-4 before:absolute before:left-3 sm:before:left-4 before:top-4 before:bottom-4 before:w-0.5 before:bg-[color:var(--shell-border-strong)]/60">
              {upcomingTasks.map((task) => (
                <div
                  key={task.id}
                  className="relative rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 transition hover:border-[color:var(--shell-border-strong)] hover:shadow-xs"
                >
                  {/* Timeline Connecting Node Dot */}
                  <span className="absolute -left-6 sm:-left-8 top-4 grid h-6 w-6 place-items-center rounded-full border-2 border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-xs">
                    <span className="h-2 w-2 rounded-full bg-[var(--brand-500)]" />
                  </span>

                  {/* Task Content */}
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <time
                        dateTime={task.due_at ?? undefined}
                        className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-muted)] border border-[color:var(--shell-border)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-brand)]"
                      >
                        <Icon name="calendar" size={12} />
                        {dueLabel(task.due_at, language)}
                      </time>
                      {task.episode_title ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                          <Icon name="progress" size={12} className="text-[var(--text-brand)]" />
                          {task.episode_title}
                        </span>
                      ) : null}
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-muted)]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" />
                        {task.status === "in_progress"
                          ? t(language, "today.following")
                          : t(language, "today.taskDetail.acceptedTask")}
                      </span>
                    </div>

                    <h3 className="text-base font-semibold text-[var(--text-primary)]">
                      {task.title}
                    </h3>

                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[color:var(--shell-border)]/50">
                      <Button
                        size="sm"
                        variant="ghost"
                        icon="check"
                        loading={completingTaskId === task.id}
                        onClick={() => void onCompleteTask(task)}
                      >
                        {t(language, "today.taskDetail.completeAction")}
                      </Button>
                      <Link
                        href={taskHref(task)}
                        className="focus-ring inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                      >
                        {t(language, "today.viewTask")}
                        <Icon name="arrow-right" size={14} />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {/* 4. Pending Confirmation Section */}
        {pendingConfirmationCount > 0 ? (
          <section aria-label={t(language, "today.confirmation")}>
            <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[var(--status-warn-text)]">
              {t(language, "today.pendingConfirmations", {
                count: formatLocaleNumber(language, pendingConfirmationCount),
              })}{" "}
              · {t(language, "today.notConclusion")}
            </p>
          </section>
        ) : null}

        {/* 5. Journey Preview Section */}
        <JourneyPreviewSection language={language} episodes={episodes} />

        {/* 6. Shortcuts & Ask Bar Section */}
        <ShortcutsAndAskSection
          language={language}
          askQuery={askQuery}
          onAskQueryChange={onAskQueryChange}
          onAskSubmit={onAskSubmit}
        />
      </div>

      {/* 7. Side Widgets Column */}
      <SideWidgets
        language={language}
        activityDays={activityDays}
        activeDays={activeDays}
        maxDailyCompleted={maxDailyCompleted}
      />
    </div>
  );
}

function CompletedToday({
  language,
  completedToday,
  episodes,
  activeDays,
  activityDays,
  maxDailyCompleted,
  askQuery,
  onAskQueryChange,
  onAskSubmit,
}: {
  language: "vi" | "en";
  completedToday: number;
  episodes: LifeMapEpisode[];
  activeDays: number;
  activityDays: Array<{ date: string; completed_count: number }>;
  maxDailyCompleted: number;
  askQuery: string;
  onAskQueryChange: (val: string) => void;
  onAskSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="flex min-h-72 flex-col items-center justify-center rounded-[var(--radius-xl)] border-2 border-[#2A3950] border-[color:var(--status-ok-border)] bg-[var(--surface-panel)] p-7 text-center shadow-sm">
          <span className="grid h-20 w-20 place-items-center rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]">
            <Icon name="check" size={38} />
          </span>
          <h2 className="mt-5 text-2xl font-bold text-[var(--text-primary)]">
            {t(language, "today.completedTitle")}
          </h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
            {t(language, "today.completedDescription")}
          </p>
          <Button as="link" href="/lifemap" variant="secondary" className="mt-6">
            {t(language, "today.updateChange")}
          </Button>
        </section>

        {activityDays.length === 7 && activeDays > 0 ? (
          <WeeklyCareActivityCard
            language={language}
            activeDays={activeDays}
            activityDays={activityDays}
            maxDailyCompleted={maxDailyCompleted}
            completedToday={completedToday}
          />
        ) : null}

        {/* Journey Preview */}
        <JourneyPreviewSection language={language} episodes={episodes} />

        {/* Shortcuts & Ask bar */}
        <ShortcutsAndAskSection
          language={language}
          askQuery={askQuery}
          onAskQueryChange={onAskQueryChange}
          onAskSubmit={onAskSubmit}
        />
      </div>

      <SideWidgets
        language={language}
        activityDays={activityDays}
        activeDays={activeDays}
        maxDailyCompleted={maxDailyCompleted}
        showWeeklyChart={false}
      />
    </div>
  );
}

function EmptyToday({
  language,
  caughtUp,
  episodes,
  activityDays,
  activeDays,
  maxDailyCompleted,
  askQuery,
  onAskQueryChange,
  onAskSubmit,
}: {
  language: "vi" | "en";
  caughtUp: boolean;
  episodes: LifeMapEpisode[];
  activityDays: Array<{ date: string; completed_count: number }>;
  activeDays: number;
  maxDailyCompleted: number;
  askQuery: string;
  onAskQueryChange: (val: string) => void;
  onAskSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <section className="flex min-h-80 flex-col items-center justify-center rounded-[var(--radius-xl)] border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] p-7 text-center">
          <span className="grid h-20 w-20 place-items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
            <Icon name="calendar" size={36} />
          </span>
          <h2 className="mt-5 text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
            {t(language, caughtUp ? "today.caughtUpTitle" : "today.firstTitle")}
          </h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
            {t(language, caughtUp ? "today.caughtUpDescription" : "today.emptyDescription")}
          </p>

          {/* First-time state: Clean single primary CTA to start journey */}
          <div className="mt-6 flex w-full max-w-sm flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row">
            <Button as="link" href={caughtUp ? "/lifemap" : "/lifemap/new"}>
              {caughtUp
                ? t(language, "today.viewJourney")
                : t(language, "today.createEpisode")}
            </Button>
            {caughtUp ? (
              <Button as="link" href="/chat" variant="ghost">
                {t(language, "today.askTitle")}
              </Button>
            ) : null}
          </div>
        </section>

        {!caughtUp ? (
          <ol className="grid gap-4 border-t border-[color:var(--shell-border)] pt-6 sm:grid-cols-3">
            {["today.stepGoal", "today.stepTask", "today.stepToday"].map(
              (key, index) => (
                <li
                  key={key}
                  className="flex items-center gap-3 sm:flex-col sm:text-center"
                >
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-sm font-semibold text-[var(--text-brand)]">
                    {index + 1}
                  </span>
                  <span className="text-sm font-semibold text-[var(--text-secondary)]">
                    {t(language, key as Parameters<typeof t>[1])}
                  </span>
                </li>
              ),
            )}
          </ol>
        ) : (
          <>
            <JourneyPreviewSection language={language} episodes={episodes} />
            <ShortcutsAndAskSection
              language={language}
              askQuery={askQuery}
              onAskQueryChange={onAskQueryChange}
              onAskSubmit={onAskSubmit}
            />
          </>
        )}
      </div>

      {/* Suppress zero-stat charts in first-time state */}
      <SideWidgets
        language={language}
        activityDays={activityDays}
        activeDays={activeDays}
        maxDailyCompleted={maxDailyCompleted}
        showWeeklyChart={caughtUp && activeDays > 0}
      />
    </div>
  );
}

function JourneyPreviewSection({
  language,
  episodes,
}: {
  language: "vi" | "en";
  episodes: LifeMapEpisode[];
}) {
  return (
    <section aria-labelledby="today-journey-preview-heading" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2
          id="today-journey-preview-heading"
          className="flex items-center gap-2 text-lg font-bold text-[var(--text-primary)]"
        >
          <Icon name="progress" className="text-[var(--text-brand)]" />
          {t(language, "navigation.item.lifemap.label")}
        </h2>
        <Link
          href="/lifemap"
          className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
        >
          {t(language, "today.viewAll")}
        </Link>
      </div>

      {episodes.length ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {episodes.map((episode) => (
            <Link
              key={episode.id}
              href="/lifemap"
              className="focus-ring group flex flex-col justify-between rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 transition hover:border-[color:var(--shell-border-strong)] hover:shadow-xs"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "lifemap.episodes.eyebrow")}
                  </span>
                  <Badge tone={priorityTone(episode.priority)}>
                    {priorityLabel(episode.priority, language)}
                  </Badge>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                  {episode.title}
                </h3>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[color:var(--shell-border)]/50 pt-2">
                <span>{t(language, "lifemap.episodes.createdByYou")}</span>
                <Icon
                  name="arrow-right"
                  size={14}
                  className="text-[var(--text-brand)] transition group-hover:translate-x-0.5"
                />
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 flex items-center justify-between gap-4">
          <p className="text-xs text-[var(--text-secondary)]">
            {t(language, "lifemap.episodes.emptyDescription")}
          </p>
          <Button as="link" href="/lifemap/new" size="sm" icon="add">
            {t(language, "today.createEpisode")}
          </Button>
        </div>
      )}
    </section>
  );
}

function ShortcutsAndAskSection({
  language,
  askQuery,
  onAskQueryChange,
  onAskSubmit,
}: {
  language: "vi" | "en";
  askQuery: string;
  onAskQueryChange: (val: string) => void;
  onAskSubmit: (e: React.FormEvent) => void;
}) {
  const items = quickActionItems;

  return (
    <div className="space-y-4">
      {/* CLARA Quick Prompt Bar */}
      <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 sm:p-4 shadow-sm" aria-label={t(language, "today.askTitle")}>
        <form
          onSubmit={onAskSubmit}
          className="relative flex items-center gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border-strong)]/40 bg-[var(--surface-muted)] px-3.5 py-2.5 focus-within:border-[var(--brand-500)] focus-within:ring-1 focus-within:ring-[var(--brand-500)] transition-all"
        >
          <Icon name="clinical-notes" size={20} className="text-[var(--text-brand)] shrink-0" />
          <input
            type="text"
            value={askQuery}
            onChange={(e) => onAskQueryChange(e.target.value)}
            placeholder={t(language, "today.askPlaceholder")}
            className="w-full bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/70 focus:outline-none"
          />
          <button
            type="submit"
            className="focus-ring inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)] hover:bg-[var(--brand-600)] hover:text-white transition-colors"
            aria-label={t(language, "today.askTitle")}
          >
            <Icon name="arrow-right" size={16} />
          </button>
        </form>
        <div className="mt-2.5 flex items-center gap-2 overflow-x-auto pb-1 text-xs text-[var(--text-secondary)]">
          <Link
            href="/chat?q=huyet-ap"
            className="shrink-0 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
          >
            {t(language, "today.askPromptBp")}
          </Link>
          <Link
            href="/chat?q=thuoc-hom-nay"
            className="shrink-0 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
          >
            {t(language, "today.askPromptMeds")}
          </Link>
          <Link
            href="/chat?q=cau-hoi-bac-si"
            className="shrink-0 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
          >
            {t(language, "today.askPromptVisit")}
          </Link>
        </div>
      </section>

      {/* Quick Action Shortcuts */}
      <section className="space-y-3" aria-labelledby="today-shortcuts-heading">
        <h2
          id="today-shortcuts-heading"
          className="text-base font-bold text-[var(--text-primary)]"
        >
          {t(language, "today.startHere")}
        </h2>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {items.map((item, index) => (
            <Link
              key={item.href}
              href={item.href}
              className={`focus-ring group flex items-center gap-3.5 rounded-[var(--radius-lg)] border p-3.5 transition ${
                index === 0
                  ? "border-[color:var(--brand-500)]/60 bg-[var(--surface-brand-soft)] hover:border-[color:var(--brand-500)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-xs">
                <Icon name={item.icon} size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-[var(--text-primary)]">
                  {t(language, item.title)}
                </span>
                <span className="mt-0.5 line-clamp-1 block text-xs text-[var(--text-secondary)]">
                  {t(language, item.description)}
                </span>
              </span>
              <Icon
                name="arrow-right"
                size={16}
                className="text-[var(--text-brand)] transition group-hover:translate-x-1"
              />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function SideWidgets({
  language,
  activityDays,
  activeDays,
  maxDailyCompleted,
  showWeeklyChart = true,
}: {
  language: "vi" | "en";
  activityDays?: Array<{ date: string; completed_count: number }>;
  activeDays?: number;
  maxDailyCompleted?: number;
  showWeeklyChart?: boolean;
}) {
  return (
    <aside className="space-y-6 lg:col-span-4" aria-labelledby="today-side-widgets">
      <h2 id="today-side-widgets" className="sr-only">
        {t(language, "today.quickShortcuts")}
      </h2>

      {/* Widget 1: Emergency Medical Card Quick Trigger (WITHOUT hardcoded blood type) */}
      <section
        className="relative overflow-hidden rounded-[var(--radius-xl)] border border-t-2 border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-xs"
        aria-labelledby="today-emergency-card-title"
      >
        <div className="flex items-start gap-3.5">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] text-[var(--status-danger-text)]">
            <Icon name="user-card" size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <h3
              id="today-emergency-card-title"
              className="text-base font-bold text-[var(--text-primary)]"
            >
              {t(language, "today.emergencyCardTitle")}
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
              {t(language, "today.emergencyCardDesc")}
            </p>
          </div>
        </div>
        <div className="mt-4 border-t border-[color:var(--shell-border)]/60 pt-3">
          <Link
            href="/you/profile"
            className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs font-bold text-[var(--status-danger-text)] hover:opacity-90 transition-opacity shadow-xs"
          >
            <Icon name="user-card" size={15} />
            {t(language, "today.emergencyCardAction")}
          </Link>
        </div>
      </section>

      {/* Widget 2: 7-Day Care Rhythm Metric Card (Suppressed when first-time) */}
      {showWeeklyChart && activityDays && activityDays.length === 7 && typeof activeDays === "number" && maxDailyCompleted ? (
        <WeeklyCareActivityCard
          language={language}
          activeDays={activeDays}
          activityDays={activityDays}
          maxDailyCompleted={maxDailyCompleted}
        />
      ) : null}

      {/* Widget 3: What's changed / Recent Updates */}
      <section className="space-y-3" aria-labelledby="today-whats-new-heading">
        <div className="flex items-center justify-between">
          <h3
            id="today-whats-new-heading"
            className="text-base font-bold text-[var(--text-primary)]"
          >
            {t(language, "today.whatsNew")}
          </h3>
          <Link
            href="/phr"
            className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
          >
            {t(language, "today.viewAll")}
          </Link>
        </div>
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 space-y-2 text-xs">
          <p className="text-[var(--text-secondary)] leading-relaxed">
            {t(language, "today.whatsNewDesc")}
          </p>
          <div className="flex items-center gap-2 pt-1 text-[11px] text-[var(--text-muted)]">
            <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 font-semibold text-[var(--text-secondary)]">
              {t(language, "today.statusSafe")}
            </span>
            <span>· CLARA PHR Sync</span>
          </div>
        </div>
      </section>
    </aside>
  );
}

function WeeklyCareActivityCard({
  language,
  activeDays,
  activityDays,
  maxDailyCompleted,
  completedToday,
}: {
  language: "vi" | "en";
  activeDays: number;
  activityDays: Array<{ date: string; completed_count: number }>;
  maxDailyCompleted: number;
  completedToday?: number;
}) {
  return (
    <section
      className="rounded-[var(--radius-xl)] border border-t-2 border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-xs"
      aria-labelledby="today-weekly-progress"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3
            id="today-weekly-progress"
            className="text-base font-bold text-[var(--text-primary)]"
          >
            {t(language, "today.weeklyProgress")}
          </h3>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            {t(language, "today.careRhythmMetric")}
          </p>
        </div>
        <span className="rounded-full bg-[var(--surface-brand-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--text-brand)]">
          {t(language, "today.activeDays", {
            count: formatLocaleNumber(language, activeDays),
          })}
        </span>
      </div>
      <div
        className="mt-6 flex h-36 items-end justify-between gap-2"
        role="list"
        aria-label={t(language, "today.weeklyProgress")}
      >
        {activityDays.map((day) => {
          const date = new Date(`${day.date}T12:00:00`);
          const label = formatLocaleDate(language, date, { weekday: "short" });
          const height =
            day.completed_count > 0
              ? Math.max(24, Math.round((day.completed_count / maxDailyCompleted) * 100))
              : 12;
          return (
            <div
              key={day.date}
              className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5"
              role="listitem"
              aria-label={`${label}: ${formatLocaleNumber(language, day.completed_count)}`}
            >
              <span className="text-[11px] font-semibold text-[var(--text-secondary)]">
                {formatLocaleNumber(language, day.completed_count)}
              </span>
              <span
                className={`w-full max-w-7 rounded-t-md border transition-all ${
                  day.completed_count > 0
                    ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]"
                    : "border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                }`}
                style={{ height: `${height}%` }}
                aria-hidden="true"
              />
              <span className="text-[11px] text-[var(--text-muted)]">{label}</span>
            </div>
          );
        })}
      </div>
      {typeof completedToday === "number" ? (
        <p className="sr-only">
          {t(language, "today.completedTaskCount", {
            count: formatLocaleNumber(language, completedToday),
          })}
        </p>
      ) : null}
    </section>
  );
}
