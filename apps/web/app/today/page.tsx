"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/lifemap/lifemap-primitives";
import { completeLifeMapTask, getLifeMapToday, type LifeMapToday } from "@/lib/lifemap";

function dueLabel(value: string | null): string {
  if (!value) return "Không có hạn cụ thể";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Không có hạn cụ thể" : date.toLocaleString("vi-VN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function TodayPage() {
  const [today, setToday] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setToday(await getLifeMapToday()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại."); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const complete = async (id: string) => {
    setCompleting(id); setError("");
    try { await completeLifeMapTask(id); await load(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể hoàn tất việc này."); } finally { setCompleting(null); }
  };
  const tasks = today?.tasks ?? [];

  return <PageShell variant="plain" title="Hôm nay" description="Một nhịp chăm sóc rõ ràng: chỉ những việc bạn đã chấp nhận mới xuất hiện ở đây.">
    <div className="space-y-5">
      {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
      {loading ? <LoadingCards /> : <>
        <div className="grid gap-3 sm:grid-cols-3">
          <SurfaceCard className="p-4"><p className="text-sm text-[var(--text-secondary)]">Việc đang chờ</p><p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{tasks.length}</p><p className="mt-1 text-xs text-[var(--text-muted)]">Đã đồng ý thực hiện</p></SurfaceCard>
          <SurfaceCard className="p-4"><p className="text-sm text-[var(--text-secondary)]">Hành trình đang mở</p><p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{today?.episodes.length ?? 0}</p><p className="mt-1 text-xs text-[var(--text-muted)]">Theo dõi cùng bạn</p></SurfaceCard>
          <SurfaceCard className="p-4"><p className="text-sm text-[var(--text-secondary)]">Cần xác nhận</p><p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{today?.pending_confirmation_count ?? 0}</p><p className="mt-1 text-xs text-[var(--text-muted)]">Chưa dùng làm kết luận</p></SurfaceCard>
        </div>
        <SurfaceCard className="overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-[color:var(--shell-border)] px-5 py-4"><div><h2 className="font-semibold text-[var(--text-primary)]">Việc nên làm tiếp theo</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">Bạn luôn có quyền bỏ qua hoặc điều chỉnh kế hoạch.</p></div><Link href="/lifemap" className="shrink-0 text-sm font-semibold text-[var(--brand-700)] hover:underline dark:text-sky-200">Mở LifeMap</Link></div>
          {tasks.length ? <ul className="divide-y divide-[color:var(--shell-border)]">{tasks.map((task) => <li key={task.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center"><span className="material-symbols-outlined text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">task_alt</span><div className="min-w-0 flex-1"><p className="font-medium text-[var(--text-primary)]">{task.title}</p><p className="mt-1 text-sm text-[var(--text-secondary)]">{dueLabel(task.due_at)}</p></div><button type="button" disabled={completing === task.id} onClick={() => void complete(task.id)} className="rounded-xl bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-700)] disabled:cursor-wait disabled:opacity-60">{completing === task.id ? "Đang lưu…" : "Hoàn tất"}</button></li>)}</ul> : <EmptyState icon="calendar_add_on" title="Hôm nay chưa có việc nào" description="Khi bạn chấp nhận một việc trong LifeMap, nó sẽ xuất hiện ở đây. CLARA không tự thêm việc thay bạn."><Link href="/lifemap" className="rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-700)]">Tạo hành trình</Link></EmptyState>}
        </SurfaceCard>
      </>}
    </div>
  </PageShell>;
}
