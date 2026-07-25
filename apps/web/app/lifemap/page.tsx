"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/lifemap/lifemap-primitives";
import { acceptLifeMapTask, createLifeMapEpisode, createLifeMapTask, getLifeMapToday, type LifeMapToday } from "@/lib/lifemap";

const priorities = [
  ["routine", "Khi thuận tiện"],
  ["soon", "Sớm"],
  ["urgent", "Cần ưu tiên"],
] as const;

function priorityStyle(priority: string) {
  if (priority === "urgent") return "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-100";
  if (priority === "soon") return "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-100";
  return "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-100";
}

export default function LifeMapPage() {
  const [data, setData] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState<"routine" | "soon" | "urgent">("routine");
  const [taskTitle, setTaskTitle] = useState("");
  const [episodeId, setEpisodeId] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { const next = await getLifeMapToday(); setData(next); setEpisodeId((current) => current || next.episodes[0]?.id || ""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const makeEpisode = async (event: FormEvent) => {
    event.preventDefault(); if (!episodeTitle.trim()) return;
    setSaving(true); setError("");
    try { const created = await createLifeMapEpisode({ title: episodeTitle.trim(), goal: goal.trim(), priority }); setEpisodeTitle(""); setGoal(""); setEpisodeId(created.id); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tạo hành trình."); }
    finally { setSaving(false); }
  };
  const makeTask = async (event: FormEvent) => {
    event.preventDefault(); if (!taskTitle.trim() || !episodeId) return;
    setSaving(true); setError("");
    try { const created = await createLifeMapTask(episodeId, { title: taskTitle.trim() }); await acceptLifeMapTask(created.id); setTaskTitle(""); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể thêm việc này."); }
    finally { setSaving(false); }
  };

  return <PageShell variant="plain" title="LifeMap" description="Tổ chức các điều bạn muốn theo dõi thành hành trình nhỏ, có thể xem lại và thay đổi bất cứ lúc nào.">
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
        {loading ? <LoadingCards count={2} /> : <>
          <SurfaceCard className="overflow-hidden">
            <div className="border-b border-[color:var(--shell-border)] px-5 py-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Hành trình đang mở</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Bạn đang theo dõi điều gì?</h2></div>
            {data?.episodes.length ? <ul className="divide-y divide-[color:var(--shell-border)]">{data.episodes.map((episode) => <li key={episode.id} className="flex items-center gap-3 px-5 py-4"><span className="material-symbols-outlined text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">route</span><div className="min-w-0 flex-1"><p className="font-medium text-[var(--text-primary)]">{episode.title}</p><p className="mt-1 text-sm text-[var(--text-secondary)]">Một hành trình do bạn tạo</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${priorityStyle(episode.priority)}`}>{priorities.find(([key]) => key === episode.priority)?.[1] ?? episode.priority}</span></li>)}</ul> : <EmptyState icon="route" title="Chưa có hành trình" description="Bắt đầu bằng một mục tiêu đơn giản, ví dụ theo dõi triệu chứng hoặc chuẩn bị câu hỏi cho buổi khám." />}
          </SurfaceCard>
          <SurfaceCard className="p-5"><div className="flex items-start justify-between gap-4"><div><h2 className="font-semibold text-[var(--text-primary)]">Việc đã được chấp nhận</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">Chỉ các việc bạn đồng ý mới được đưa vào Today.</p></div><Link href="/today" className="text-sm font-semibold text-[var(--brand-700)] hover:underline dark:text-sky-200">Xem Today</Link></div><div className="mt-4 space-y-2">{data?.tasks.length ? data.tasks.map((task) => <div key={task.id} className="flex gap-3 rounded-xl bg-[var(--surface-muted)] p-3"><span className="material-symbols-outlined text-[var(--text-muted)]" aria-hidden="true">task_alt</span><p className="text-sm font-medium text-[var(--text-primary)]">{task.title}</p></div>) : <p className="rounded-xl bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">Chưa có việc nào được chấp nhận.</p>}</div></SurfaceCard>
        </>}
      </div>
      <aside className="space-y-5">
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Tạo hành trình</h2><p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">Dùng ngôn ngữ của bạn. Đây là kế hoạch cá nhân, không phải chẩn đoán.</p><form className="mt-4 space-y-3" onSubmit={(event) => void makeEpisode(event)}><label className="block text-sm font-medium text-[var(--text-primary)]">Tên hành trình<input required value={episodeTitle} onChange={(event) => setEpisodeTitle(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25" placeholder="Ví dụ: Theo dõi giấc ngủ" /></label><label className="block text-sm font-medium text-[var(--text-primary)]">Điều bạn muốn đạt được <span className="font-normal text-[var(--text-muted)]">(không bắt buộc)</span><textarea value={goal} onChange={(event) => setGoal(event.target.value)} className="mt-1.5 min-h-20 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25" /></label><label className="block text-sm font-medium text-[var(--text-primary)]">Mức ưu tiên<select value={priority} onChange={(event) => setPriority(event.target.value as typeof priority)} className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)]">{priorities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button disabled={saving} className="w-full rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-700)] disabled:opacity-60">{saving ? "Đang lưu…" : "Tạo hành trình"}</button></form></SurfaceCard>
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Thêm việc cho hôm nay</h2><form className="mt-4 space-y-3" onSubmit={(event) => void makeTask(event)}><label className="block text-sm font-medium text-[var(--text-primary)]">Thuộc hành trình<select required value={episodeId} onChange={(event) => setEpisodeId(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)]"><option value="">Chọn hành trình</option>{data?.episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.title}</option>)}</select></label><label className="block text-sm font-medium text-[var(--text-primary)]">Việc bạn muốn làm<input required value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} disabled={!episodeId} placeholder="Ví dụ: Ghi lại thời điểm xuất hiện" className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25 disabled:cursor-not-allowed disabled:opacity-60" /></label><button disabled={saving || !episodeId} className="w-full rounded-xl border border-[color:var(--brand-500)] px-4 py-2.5 text-sm font-semibold text-[var(--brand-700)] hover:bg-[var(--surface-brand-soft)] disabled:opacity-60 dark:text-sky-200">Thêm vào Today</button></form></SurfaceCard>
      </aside>
    </div>
  </PageShell>;
}
