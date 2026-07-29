"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { completeLifeMapTask, getLifeMapToday, type LifeMapTask } from "@/lib/lifemap";

function dueLabel(value: string | null): string {
  if (!value) return "Không có hạn cụ thể";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Không có hạn cụ thể"
    : date.toLocaleString("vi-VN", {
        day: "numeric",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
      });
}

export default function TodayTaskDetailPage() {
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
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại.");
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (taskId) void load();
  }, [load, taskId]);

  const complete = async () => {
    if (!task) return;
    setCompleting(true);
    setError("");
    try {
      await completeLifeMapTask(task.id);
      setCompleted(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể hoàn tất việc này.");
    } finally {
      setCompleting(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title={completed ? "Đã hoàn tất" : "Chi tiết việc hôm nay"}
      description={
        completed
          ? "Việc này đã được ghi nhận. Bạn có thể quay lại xem ưu tiên tiếp theo."
          : "Xem một việc, hiểu thời điểm cần làm, rồi mới xác nhận hoàn tất."
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
            <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">Đã ghi nhận hoàn tất</h2>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              CLARA không tự suy diễn thêm hành động chăm sóc từ việc này.
            </p>
            <Button as="link" href="/today" className="mt-5">
              Quay lại Hôm nay
            </Button>
          </SurfaceCard>
        ) : task ? (
          <SurfaceCard className="p-6">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined mt-0.5 text-[var(--text-brand)]" aria-hidden="true">
                task_alt
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-secondary)]">Việc đã được bạn chấp nhận</p>
                <h2 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{task.title}</h2>
              </div>
            </div>
            <dl className="mt-6 space-y-4 border-y border-[color:var(--shell-border)] py-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--text-secondary)]">Thời điểm</dt>
                <dd className="text-right font-medium text-[var(--text-primary)]">{dueLabel(task.due_at)}</dd>
              </div>
            </dl>
            <p className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">
              Chỉ xác nhận khi bạn đã thực hiện việc này. Nếu kế hoạch không còn phù hợp, hãy quay lại LifeMap để xem và điều chỉnh bối cảnh.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
              <Link href="/today" className="focus-ring self-center text-sm font-semibold text-[var(--text-brand)] hover:underline">
                Quay lại danh sách
              </Link>
              <Button loading={completing} onClick={() => void complete()}>
                Xác nhận hoàn tất
              </Button>
            </div>
          </SurfaceCard>
        ) : (
          <EmptyState
            icon="task_alt"
            title="Việc này không còn trong danh sách hôm nay"
            description="Có thể việc đã hoàn tất, được điều chỉnh, hoặc bạn đang mở một liên kết cũ."
          >
            <Button as="link" href="/today">Quay lại Hôm nay</Button>
          </EmptyState>
        )}
      </div>
    </PageShell>
  );
}
