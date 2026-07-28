"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Select, Textarea } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import {
  acceptLifeMapTask,
  createLifeMapEpisode,
  createLifeMapTask,
  getLifeMapCaptureCapability,
  getLifeMapToday,
  reviewLifeMapCaptureCandidate,
  startLifeMapTextCapture,
  type CaptureSession,
  type LifeMapToday,
} from "@/lib/lifemap";
import { getProfileContext } from "@/lib/profile-context-api";

const priorities = [
  ["routine", "Khi thuận tiện"],
  ["soon", "Sớm"],
  ["urgent", "Cần ưu tiên"],
] as const;

type PriorityKey = (typeof priorities)[number][0];

function priorityTone(priority: string): "danger" | "warn" | "brand" {
  if (priority === "urgent") return "danger";
  if (priority === "soon") return "warn";
  return "brand";
}

function priorityLabel(priority: string): string {
  return priorities.find(([key]) => key === priority)?.[1] ?? priority;
}

export default function LifeMapPage() {
  const [data, setData] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState<PriorityKey>("routine");
  const [taskTitle, setTaskTitle] = useState("");
  const [episodeId, setEpisodeId] = useState("");
  const [captureEnabled, setCaptureEnabled] = useState(false);
  const [captureText, setCaptureText] = useState("");
  const [captureSession, setCaptureSession] = useState<CaptureSession | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getLifeMapToday();
      setData(next);
      setEpisodeId((current) => current || next.episodes[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void getProfileContext()
      .then((context) =>
        context.active_profile_id
          ? getLifeMapCaptureCapability(context.active_profile_id)
          : false,
      )
      .then(setCaptureEnabled)
      .catch(() => setCaptureEnabled(false));
  }, [load]);

  const startCapture = async (event: FormEvent) => {
    event.preventDefault();
    if (!captureText.trim()) return;
    setSaving(true);
    setError("");
    try {
      const session = await startLifeMapTextCapture(captureText.trim());
      setCaptureSession(session);
      if (session.persisted) setCaptureText("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể bắt đầu ghi nhận.");
    } finally {
      setSaving(false);
    }
  };

  const confirmCapture = async (candidateId: string) => {
    setSaving(true);
    setError("");
    try {
      await reviewLifeMapCaptureCandidate(candidateId, "confirm", {
        reason: "Người dùng đã kiểm tra bản ghi",
      });
      setCaptureSession((current) =>
        current
          ? {
              ...current,
              status: "completed",
              candidates: current.candidates?.map((candidate) =>
                candidate.id === candidateId
                  ? { ...candidate, status: "confirmed" }
                  : candidate,
              ),
            }
          : current,
      );
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xác nhận bản ghi.");
    } finally {
      setSaving(false);
    }
  };

  const makeEpisode = async (event: FormEvent) => {
    event.preventDefault();
    if (!episodeTitle.trim()) return;
    setSaving(true);
    setError("");
    try {
      const created = await createLifeMapEpisode({
        title: episodeTitle.trim(),
        goal: goal.trim(),
        priority,
      });
      setEpisodeTitle("");
      setGoal("");
      setEpisodeId(created.id);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo hành trình.");
    } finally {
      setSaving(false);
    }
  };

  const makeTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!taskTitle.trim() || !episodeId) return;
    setSaving(true);
    setError("");
    try {
      const created = await createLifeMapTask(episodeId, { title: taskTitle.trim() });
      await acceptLifeMapTask(created.id);
      setTaskTitle("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể thêm việc này.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title="LifeMap"
      description="Tổ chức các điều bạn muốn theo dõi thành hành trình nhỏ, có thể xem lại và thay đổi bất cứ lúc nào."
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

          {loading ? (
            <LoadingCards count={2} />
          ) : (
            <>
              <SurfaceCard className="overflow-hidden">
                <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    Hành trình đang mở
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                    Bạn đang theo dõi điều gì?
                  </h2>
                </div>
                {data?.episodes.length ? (
                  <ul className="divide-y divide-[color:var(--shell-border)]">
                    {data.episodes.map((episode) => (
                      <li key={episode.id} className="flex items-center gap-3 px-5 py-4">
                        <span
                          className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                          aria-hidden="true"
                        >
                          <span className="material-symbols-outlined">route</span>
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-[var(--text-primary)]">{episode.title}</p>
                          <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                            Một hành trình do bạn tạo
                          </p>
                        </div>
                        <Badge tone={priorityTone(episode.priority)}>
                          {priorityLabel(episode.priority)}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="p-5">
                    <EmptyState
                      icon="route"
                      title="Chưa có hành trình"
                      description="Bắt đầu bằng một mục tiêu đơn giản, ví dụ theo dõi triệu chứng hoặc chuẩn bị câu hỏi cho buổi khám."
                    />
                  </div>
                )}
              </SurfaceCard>

              <SurfaceCard className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-semibold text-[var(--text-primary)]">Việc đã được chấp nhận</h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      Chỉ các việc bạn đồng ý mới được đưa vào Today.
                    </p>
                  </div>
                  <Link
                    href="/today"
                    className="focus-ring shrink-0 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
                  >
                    Xem Today
                  </Link>
                </div>
                <div className="mt-4 space-y-2">
                  {data?.tasks.length ? (
                    data.tasks.map((task) => (
                      <div
                        key={task.id}
                        className="flex items-center gap-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3"
                      >
                        <span
                          className="material-symbols-outlined text-[var(--text-muted)]"
                          aria-hidden="true"
                        >
                          task_alt
                        </span>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{task.title}</p>
                      </div>
                    ))
                  ) : (
                    <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                      Chưa có việc nào được chấp nhận.
                    </p>
                  )}
                </div>
              </SurfaceCard>
            </>
          )}
        </div>

        <aside className="space-y-5">
          {captureEnabled ? (
            <SurfaceCard className="p-5">
              <div className="flex items-start gap-3">
                <span
                  className="material-symbols-outlined mt-0.5 text-[var(--text-brand)]"
                  aria-hidden="true"
                >
                  add_notes
                </span>
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">
                    Ghi nhận nhanh
                  </h2>
                  <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
                    CLARA tạo bản nháp để bạn xem lại. Không có thông tin nào được
                    xác nhận tự động.
                  </p>
                </div>
              </div>
              {captureSession?.emergency ? (
                <div
                  className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-sm text-[var(--status-danger-text)]"
                  role="alert"
                >
                  {captureSession.message}
                </div>
              ) : captureSession?.candidates?.length ? (
                <div className="mt-4 space-y-3">
                  {captureSession.candidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"
                    >
                      <p className="text-sm text-[var(--text-primary)]">
                        {String(candidate.value.text ?? "")}
                      </p>
                      {candidate.missing_critical_fields.length ? (
                        <p className="mt-2 text-xs text-[var(--status-warn-text)]">
                          Cần bổ sung: {candidate.missing_critical_fields.join(", ")}
                        </p>
                      ) : null}
                      {candidate.status === "draft" ? (
                        <Button
                          className="mt-3"
                          size="sm"
                          icon="verified"
                          loading={saving}
                          onClick={() => void confirmCapture(candidate.id)}
                        >
                          Tôi đã xem và xác nhận
                        </Button>
                      ) : (
                        <Badge tone="ok">Đã xác nhận</Badge>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <form className="mt-4 space-y-3" onSubmit={(event) => void startCapture(event)}>
                  <Textarea
                    label="Điều bạn muốn ghi lại"
                    value={captureText}
                    onChange={(event) => setCaptureText(event.target.value)}
                    placeholder="Ví dụ: Tối qua tôi ngủ khoảng 7 giờ"
                  />
                  <Button
                    type="submit"
                    block
                    loading={saving}
                    loadingLabel="Đang tạo bản nháp…"
                    icon="add_notes"
                  >
                    Tạo bản nháp
                  </Button>
                </form>
              )}
            </SurfaceCard>
          ) : null}

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Tạo hành trình</h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              Dùng ngôn ngữ của bạn. Đây là kế hoạch cá nhân, không phải chẩn đoán.
            </p>
            <form className="mt-4 space-y-3.5" onSubmit={(event) => void makeEpisode(event)}>
              <Field
                label="Tên hành trình"
                required
                value={episodeTitle}
                onChange={(event) => setEpisodeTitle(event.target.value)}
                placeholder="Ví dụ: Theo dõi giấc ngủ"
              />
              <Textarea
                label="Điều bạn muốn đạt được"
                optional
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
              />
              <Select
                label="Mức ưu tiên"
                value={priority}
                onChange={(event) => setPriority(event.target.value as PriorityKey)}
              >
                {priorities.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
              <Button type="submit" block loading={saving} loadingLabel="Đang lưu…" icon="add">
                Tạo hành trình
              </Button>
            </form>
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Thêm việc cho hôm nay</h2>
            <form className="mt-4 space-y-3.5" onSubmit={(event) => void makeTask(event)}>
              <Select
                label="Thuộc hành trình"
                required
                value={episodeId}
                onChange={(event) => setEpisodeId(event.target.value)}
              >
                <option value="">Chọn hành trình</option>
                {data?.episodes.map((episode) => (
                  <option key={episode.id} value={episode.id}>
                    {episode.title}
                  </option>
                ))}
              </Select>
              <Field
                label="Việc bạn muốn làm"
                required
                value={taskTitle}
                onChange={(event) => setTaskTitle(event.target.value)}
                disabled={!episodeId}
                placeholder="Ví dụ: Ghi lại thời điểm xuất hiện"
              />
              <Button
                type="submit"
                variant="secondary"
                block
                disabled={saving || !episodeId}
                icon="playlist_add"
              >
                Thêm vào Today
              </Button>
            </form>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
