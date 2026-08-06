"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { completeLifeMapTask, getLifeMapToday, type LifeMapTask } from "@/lib/lifemap";
import { useUILanguage } from "@/lib/use-ui-language";

function dueLabel(language: "vi" | "en", value: string | null): string {
  if (!value) return t(language, "today.taskDetail.noSpecificDueDate");
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? t(language, "today.taskDetail.noSpecificDueDate")
    : formatLocaleDate(language, date, {
        day: "numeric",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
      });
}

export default function TodayTaskDetailPage() {
  const language = useUILanguage();
  const params = useParams<{ taskId: string }>();
  const taskId = Array.isArray(params.taskId) ? params.taskId[0] : params.taskId;
  const [task, setTask] = useState<LifeMapTask | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const today = await getLifeMapToday();
      setTask(today.tasks.find((item) => item.id === taskId) ?? null);
    } catch {
      setError(t(language, "today.connectionError"));
    } finally {
      setLoading(false);
    }
  }, [language, taskId]);

  useEffect(() => {
    if (taskId) void load();
  }, [load, taskId]);

  const complete = async () => {
    if (!task) return;
    setCompleting(true);
    setError("");
    try {
      await completeLifeMapTask(task.id, task.version);
      setCompleted(true);
    } catch {
      setError(t(language, "today.taskDetail.completeError"));
    } finally {
      setCompleting(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title={
        completed
          ? t(language, "today.taskDetail.completedPageTitle")
          : t(language, "today.taskDetail.pageTitle")
      }
      description={
        completed
          ? t(language, "today.taskDetail.completedPageDescription")
          : t(language, "today.taskDetail.pageDescription")
      }
    >
      <div className="mx-auto max-w-2xl space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards count={1} />
        ) : completed ? (
          <SurfaceCard className="p-6 text-center">
            <span className="material-symbols-outlined text-4xl text-[var(--text-success)]" aria-hidden="true">
              task_alt
            </span>
            <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
              {t(language, "today.taskDetail.completedTitle")}
            </h2>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              {t(language, "today.taskDetail.completedDescription")}
            </p>
            <Button as="link" href="/today" className="mt-5">
              {t(language, "today.taskDetail.backToToday")}
            </Button>
          </SurfaceCard>
        ) : task ? (
          <SurfaceCard className="p-6">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined mt-0.5 text-[var(--text-brand)]" aria-hidden="true">
                task_alt
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-secondary)]">
                  {t(language, "today.taskDetail.acceptedTask")}
                </p>
                <h2 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{task.title}</h2>
              </div>
            </div>
            <dl className="mt-6 space-y-4 border-y border-[color:var(--shell-border)] py-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-secondary)]">
                  {t(language, "today.taskDetail.dueDate")}
                </dt>
                <dd className="text-right font-medium text-[var(--text-primary)]">
                  {dueLabel(language, task.due_at)}
                </dd>
              </div>
            </dl>
            <p className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">
              {t(language, "today.taskDetail.completeGuidance")}
            </p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
              <Link href="/today" className="focus-ring self-center text-sm font-semibold text-[var(--text-brand)] hover:underline">
                {t(language, "today.taskDetail.backToList")}
              </Link>
              <Button loading={completing} onClick={() => void complete()}>
                {t(language, "today.taskDetail.completeAction")}
              </Button>
            </div>
          </SurfaceCard>
        ) : (
          <EmptyState
            icon="task_alt"
            title={t(language, "today.taskDetail.notFoundTitle")}
            description={t(language, "today.taskDetail.notFoundDescription")}
          >
            <Button as="link" href="/today">
              {t(language, "today.taskDetail.backToToday")}
            </Button>
          </EmptyState>
        )}
      </div>
    </PageShell>
  );
}
