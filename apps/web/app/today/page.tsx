"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  StatCard,
  SurfaceCard,
} from "@/components/ui/surface";
import { completeLifeMapTask, getLifeMapToday, type LifeMapToday } from "@/lib/lifemap";

function dueLabel(value: string | null): string {
  if (!value) return "Không có hạn cụ thể";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Không có hạn cụ thể"
    : date.toLocaleString("vi-VN", {
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
  const [completing, setCompleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setToday(await getLifeMapToday());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const complete = async (id: string) => {
    setCompleting(id);
    setError("");
    try {
      await completeLifeMapTask(id);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể hoàn tất việc này.");
    } finally {
      setCompleting(null);
    }
  };

  const tasks = today?.tasks ?? [];

  return (
    <PageShell
      variant="plain"
      title="Hôm nay"
      description="Một nhịp chăm sóc rõ ràng: chỉ những việc bạn đã chấp nhận mới xuất hiện ở đây."
    >
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                label="Việc đang chờ"
                value={tasks.length}
                hint="Đã đồng ý thực hiện"
                icon="task_alt"
                tone="brand"
              />
              <StatCard
                label="Hành trình đang mở"
                value={today?.episodes.length ?? 0}
                hint="Theo dõi cùng bạn"
                icon="route"
              />
              <StatCard
                label="Cần xác nhận"
                value={today?.pending_confirmation_count ?? 0}
                hint="Chưa dùng làm kết luận"
                icon="pending_actions"
                tone={today?.pending_confirmation_count ? "warn" : "neutral"}
              />
            </div>

            <SurfaceCard className="overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[color:var(--shell-border)] px-5 py-4">
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">Việc nên làm tiếp theo</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Bạn luôn có quyền bỏ qua hoặc điều chỉnh kế hoạch.
                  </p>
                </div>
                <Link
                  href="/lifemap"
                  className="focus-ring shrink-0 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
                >
                  Mở LifeMap
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
                          {dueLabel(task.due_at)}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        loading={completing === task.id}
                        onClick={() => void complete(task.id)}
                      >
                        Hoàn tất
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-5">
                  <EmptyState
                    icon="calendar_add_on"
                    title="Hôm nay chưa có việc nào"
                    description="Khi bạn chấp nhận một việc trong LifeMap, nó sẽ xuất hiện ở đây. CLARA không tự thêm việc thay bạn."
                  >
                    <Button as="link" href="/lifemap">
                      Tạo hành trình
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
