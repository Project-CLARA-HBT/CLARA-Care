"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/lifemap/lifemap-primitives";
import {
  addVisitConcern,
  approveVisitPack,
  createVisit,
  createVisitPack,
  grantVisitScribeConsent,
  listVisits,
  revokeVisitScribeConsent,
  shareVisitPack,
  type Visit,
  type VisitPack,
  type VisitShare,
} from "@/lib/visit-family";

const fieldClass =
  "mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25";

export default function VisitsPage() {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [concern, setConcern] = useState("");
  const [priority, setPriority] = useState("routine");
  const [pack, setPack] = useState<VisitPack | null>(null);
  const [share, setShare] = useState<VisitShare | null>(null);
  const [consented, setConsented] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selected = useMemo(
    () => visits.find((visit) => visit.id === selectedId) ?? null,
    [selectedId, visits],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await listVisits();
      setVisits(next);
      setSelectedId((current) => current || next[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải lịch khám.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => void load(), [load]);

  const addVisit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const visit = await createVisit({
        title: title.trim(),
        goal: goal.trim(),
        visit_type: "other",
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
      });
      setTitle("");
      setGoal("");
      setScheduledAt("");
      await load();
      setSelectedId(visit.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo buổi khám.");
    } finally {
      setSaving(false);
    }
  };

  const addConcern = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      await addVisitConcern(selectedId, concern.trim(), priority);
      setConcern("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu điều cần hỏi.");
    } finally {
      setSaving(false);
    }
  };

  const preparePack = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      const draft = await createVisitPack(selectedId, {
        visit_summary: true,
        confirmed_medications: true,
        concerns: true,
        recent_episode_events: true,
      });
      setPack(await approveVisitPack(draft.id));
      setShare(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chuẩn bị Visit Pack.");
    } finally {
      setSaving(false);
    }
  };

  const makeShare = async () => {
    if (!pack) return;
    setSaving(true);
    setError("");
    try {
      const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      setShare(await shareVisitPack(pack.id, expires));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo liên kết chia sẻ.");
    } finally {
      setSaving(false);
    }
  };

  const toggleConsent = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      if (consented) await revokeVisitScribeConsent(selectedId);
      else await grantVisitScribeConsent(selectedId);
      setConsented(!consented);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật đồng ý ghi âm.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title="Chuẩn bị buổi khám"
      description="Gom điều cần hỏi, thuốc đã xác nhận và diễn biến liên quan thành một gói do chính bạn duyệt."
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
          {loading ? (
            <LoadingCards count={2} />
          ) : (
            <>
              <SurfaceCard className="overflow-hidden">
                <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    Các buổi khám
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                    Chọn buổi bạn muốn chuẩn bị
                  </h2>
                </div>
                {visits.length ? (
                  <div className="grid gap-2 p-3 sm:grid-cols-2">
                    {visits.map((visit) => (
                      <button
                        key={visit.id}
                        type="button"
                        onClick={() => {
                          setSelectedId(visit.id);
                          setPack(null);
                          setShare(null);
                          setConsented(false);
                        }}
                        className={`rounded-xl border p-4 text-left transition ${
                          selectedId === visit.id
                            ? "border-[var(--brand-500)] bg-[var(--surface-brand-soft)]"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[var(--brand-300)]"
                        }`}
                      >
                        <p className="font-semibold text-[var(--text-primary)]">{visit.title}</p>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {visit.scheduled_at
                            ? new Date(visit.scheduled_at).toLocaleString("vi-VN")
                            : "Chưa đặt thời gian"}
                        </p>
                        <span className="mt-3 inline-flex rounded-full bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
                          {visit.status}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    icon="event_available"
                    title="Chưa có buổi khám"
                    description="Tạo một buổi khám để bắt đầu danh sách câu hỏi và Visit Pack."
                  />
                )}
              </SurfaceCard>

              {selected ? (
                <SurfaceCard className="p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h2 className="font-semibold text-[var(--text-primary)]">
                        Visit Pack của {selected.title}
                      </h2>
                      <p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                        CLARA chỉ chụp một bản bất biến của đúng bốn nhóm dữ liệu hiển thị
                        bên dưới. Hồ sơ khác không được chia sẻ ngầm.
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void preparePack()}
                      className="rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      {pack ? "Tạo bản mới" : "Tạo và duyệt gói"}
                    </button>
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {["Tóm tắt buổi khám", "Thuốc đã xác nhận", "Điều cần hỏi", "Diễn biến gần đây"].map(
                      (label) => (
                        <div
                          key={label}
                          className="flex items-center gap-2 rounded-xl bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-primary)]"
                        >
                          <span className="material-symbols-outlined text-base text-emerald-700 dark:text-emerald-200">
                            check_circle
                          </span>
                          {label}
                        </div>
                      ),
                    )}
                  </div>
                  {pack ? (
                    <div className="mt-5 rounded-xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-500/40 dark:bg-emerald-500/10">
                      <p className="font-semibold text-emerald-950 dark:text-emerald-50">
                        Bản {pack.version_no} đã được bạn duyệt
                      </p>
                      <button
                        type="button"
                        disabled={saving || Boolean(share)}
                        onClick={() => void makeShare()}
                        className="mt-3 rounded-lg bg-emerald-700 px-3.5 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      >
                        Tạo liên kết 7 ngày
                      </button>
                      {share ? (
                        <div className="mt-3">
                          <p className="text-xs text-emerald-900 dark:text-emerald-100">
                            Liên kết chỉ hiện một lần. Hãy gửi qua kênh bạn tin cậy.
                          </p>
                          <code className="mt-2 block break-all rounded-lg bg-white/80 p-3 text-xs text-emerald-950 dark:bg-black/20 dark:text-emerald-50">
                            {`${window.location.origin}/api/v1/visit-packs/shared/${share.token}`}
                          </code>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </SurfaceCard>
              ) : null}
            </>
          )}
        </div>

        <aside className="space-y-5">
          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Tạo buổi khám</h2>
            <form className="mt-4 space-y-3" onSubmit={(event) => void addVisit(event)}>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Tên buổi khám
                <input
                  required
                  minLength={2}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Ví dụ: Tái khám tim mạch"
                  className={fieldClass}
                />
              </label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Mục tiêu
                <textarea
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  className={`${fieldClass} min-h-20`}
                />
              </label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Thời gian dự kiến
                <input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(event) => setScheduledAt(event.target.value)}
                  className={fieldClass}
                />
              </label>
              <button
                disabled={saving}
                className="w-full rounded-xl border border-[var(--brand-500)] px-4 py-2.5 text-sm font-semibold text-[var(--brand-700)] disabled:opacity-60 dark:text-sky-200"
              >
                Lưu buổi khám
              </button>
            </form>
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Điều cần hỏi bác sĩ</h2>
            <form className="mt-4 space-y-3" onSubmit={(event) => void addConcern(event)}>
              <textarea
                required
                minLength={2}
                disabled={!selectedId}
                value={concern}
                onChange={(event) => setConcern(event.target.value)}
                placeholder="Điều gì khiến bạn băn khoăn nhất?"
                className={`${fieldClass} min-h-24 disabled:opacity-60`}
              />
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value)}
                className={fieldClass}
              >
                <option value="routine">Khi thuận tiện</option>
                <option value="soon">Nên hỏi sớm</option>
                <option value="urgent">Ưu tiên trao đổi</option>
              </select>
              <button
                disabled={saving || !selectedId}
                className="w-full rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                Thêm vào Visit Pack
              </button>
            </form>
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Ghi âm Scribe</h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              Đồng ý chỉ áp dụng cho buổi đang chọn và có thể rút lại ngay.
            </p>
            <button
              type="button"
              disabled={saving || !selectedId}
              onClick={() => void toggleConsent()}
              className="mt-4 w-full rounded-xl border border-[color:var(--shell-border)] px-4 py-2.5 text-sm font-semibold text-[var(--text-primary)] disabled:opacity-60"
            >
              {consented ? "Rút lại đồng ý ghi âm" : "Đồng ý ghi âm buổi này"}
            </button>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
