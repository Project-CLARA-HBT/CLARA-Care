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
  askLifeMap,
  correctLifeMapEvent,
  createLifeMapEpisode,
  createLifeMapTask,
  getLifeMapBaselines,
  getLifeMapNextQuestion,
  getLifeMapReplay,
  getLifeMapToday,
  getLifeMapV2Capabilities,
  recordLifeMapQuestionInteraction,
  reviewLifeMapCaptureCandidate,
  startLifeMapTextCapture,
  startLifeMapGuidedAnswer,
  type CaptureSession,
  type LifeMapBaseline,
  type LifeMapAskAnswer,
  type LifeMapQuestion,
  type LifeMapToday,
  type LifeMapReplay,
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
  const [questionEnabled, setQuestionEnabled] = useState(false);
  const [askEnabled, setAskEnabled] = useState(false);
  const [baselines, setBaselines] = useState<LifeMapBaseline[]>([]);
  const [nextQuestion, setNextQuestion] = useState<LifeMapQuestion | null>(null);
  const [questionAnswer, setQuestionAnswer] = useState("");
  const [captureText, setCaptureText] = useState("");
  const [captureSession, setCaptureSession] = useState<CaptureSession | null>(null);
  const [replay, setReplay] = useState<LifeMapReplay | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [editingEvent, setEditingEvent] = useState("");
  const [correctionText, setCorrectionText] = useState("");
  const [askQuery, setAskQuery] = useState("");
  const [askAnswer, setAskAnswer] = useState<LifeMapAskAnswer | null>(null);

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
      .then(async (context) => {
        if (!context.active_profile_id) return;
        const capabilities = await getLifeMapV2Capabilities(
          context.active_profile_id,
        );
        setCaptureEnabled(Boolean(capabilities.lifemap_capture));
        setQuestionEnabled(Boolean(capabilities.lifemap_next_question_v2));
        setAskEnabled(Boolean(capabilities.lifemap_ask_ai));
        if (capabilities.lifemap_baselines_v2) {
          setBaselines(await getLifeMapBaselines());
        }
      })
      .catch(() => {
        setCaptureEnabled(false);
        setQuestionEnabled(false);
        setAskEnabled(false);
      });
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

  const openReplay = async (selectedEpisodeId: string) => {
    setReplayLoading(true);
    setError("");
    try {
      setReplay(await getLifeMapReplay(selectedEpisodeId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải lịch sử.");
    } finally {
      setReplayLoading(false);
    }
  };

  const loadQuestion = async (selectedEpisodeId: string) => {
    setSaving(true);
    setError("");
    try {
      const result = await getLifeMapNextQuestion(selectedEpisodeId);
      setNextQuestion(result);
      setQuestionAnswer("");
      if (result.ask && result.question_id) {
        await recordLifeMapQuestionInteraction(
          selectedEpisodeId,
          result.question_id,
          "presented",
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải câu hỏi.");
    } finally {
      setSaving(false);
    }
  };

  const answerQuestion = async () => {
    if (
      !nextQuestion?.ask ||
      !nextQuestion.question_id ||
      !questionAnswer.trim()
    ) return;
    setSaving(true);
    setError("");
    try {
      const session = await startLifeMapGuidedAnswer(
        nextQuestion.episode_id,
        nextQuestion.question_id,
        { value: questionAnswer.trim() },
      );
      setCaptureSession(session);
      setNextQuestion(null);
      setQuestionAnswer("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu câu trả lời.");
    } finally {
      setSaving(false);
    }
  };

  const dismissQuestion = async (permanent = false) => {
    if (!nextQuestion?.question_id) return;
    setSaving(true);
    try {
      await recordLifeMapQuestionInteraction(
        nextQuestion.episode_id,
        nextQuestion.question_id,
        permanent ? "do_not_ask" : "dismissed",
        permanent ? "Người dùng không muốn được hỏi lại" : "Để sau",
      );
      setNextQuestion(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật lựa chọn.");
    } finally {
      setSaving(false);
    }
  };

  const correctEvent = async (
    item: LifeMapReplay["events"][number],
  ) => {
    if (!correctionText.trim()) return;
    setSaving(true);
    setError("");
    try {
      await correctLifeMapEvent(
        item.id,
        item.revision,
        { text: correctionText.trim() },
        "Người dùng sửa thông tin trong Replay",
      );
      setEditingEvent("");
      setCorrectionText("");
      await openReplay(replay?.episode.id ?? episodeId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu chỉnh sửa.");
    } finally {
      setSaving(false);
    }
  };

  const submitAsk = async (event: FormEvent) => {
    event.preventDefault();
    if (!askQuery.trim()) return;
    setSaving(true);
    setError("");
    try {
      setAskAnswer(await askLifeMap(askQuery.trim(), episodeId || undefined));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Không thể tra cứu LifeMap.",
      );
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
              {askEnabled ? (
                <SurfaceCard className="overflow-hidden">
                  <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                    <Badge tone="brand">AI có dẫn nguồn</Badge>
                    <h2 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
                      Hỏi LifeMap của tôi
                    </h2>
                    <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                      Chỉ tra cứu dữ liệu bạn được phép xem. CLARA không chẩn đoán,
                      kê đơn hay tự thay đổi LifeMap.
                    </p>
                  </div>
                  <form
                    className="space-y-3 p-5"
                    onSubmit={(event) => void submitAsk(event)}
                  >
                    <Textarea
                      label="Bạn muốn tìm điều gì?"
                      value={askQuery}
                      onChange={(event) => setAskQuery(event.target.value)}
                      placeholder="Ví dụ: Các ghi nhận đau đầu gần đây của tôi là gì?"
                      hint="Câu trả lời sẽ chỉ ra đúng bản ghi và phiên bản đã dùng."
                    />
                    <Button
                      type="submit"
                      icon="search"
                      loading={saving}
                      loadingLabel="Đang tra cứu…"
                    >
                      Tra cứu
                    </Button>
                  </form>
                  {askAnswer ? (
                    <div
                      className="border-t border-[color:var(--shell-border)] p-5"
                      aria-live="polite"
                    >
                      <p className="font-medium text-[var(--text-primary)]">
                        {askAnswer.answer}
                      </p>
                      {askAnswer.claims.length ? (
                        <ol className="mt-4 space-y-3">
                          {askAnswer.claims.map((claim) => {
                            const source = askAnswer.evidence.find((item) =>
                              claim.citation_ids.includes(item.evidence_id),
                            );
                            return (
                              <li
                                key={claim.claim_id}
                                className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4"
                              >
                                <p className="text-sm text-[var(--text-primary)]">
                                  {claim.text}
                                </p>
                                {source ? (
                                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                                    Nguồn: {source.attribution} ·{" "}
                                    {new Date(source.occurred_at).toLocaleString("vi-VN")} ·
                                    phiên bản {source.revision_id.slice(0, 8)}
                                  </p>
                                ) : null}
                              </li>
                            );
                          })}
                        </ol>
                      ) : null}
                      {askAnswer.disputed.length ||
                      askAnswer.conflicting.length ||
                      askAnswer.stale.length ? (
                        <p className="mt-3 text-sm text-[var(--status-warn-text)]">
                          Có thông tin đang tranh chấp, mâu thuẫn hoặc đã cũ; CLARA
                          không tự giải quyết thay bạn.
                        </p>
                      ) : null}
                      <p className="mt-4 text-xs text-[var(--text-muted)]">
                        Chế độ: {askAnswer.disclosure.mode}. Không phải tư vấn y tế.
                      </p>
                    </div>
                  ) : null}
                </SurfaceCard>
              ) : null}

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
                        <Button
                          variant="ghost"
                          size="sm"
                          icon="history"
                          loading={replayLoading}
                          onClick={() => void openReplay(episode.id)}
                        >
                          Xem lại
                        </Button>
                        {questionEnabled ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            icon="help"
                            loading={saving}
                            onClick={() => void loadQuestion(episode.id)}
                          >
                            Một câu hỏi
                          </Button>
                        ) : null}
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

              {nextQuestion?.ask ? (
                <SurfaceCard className="p-5">
                  <Badge tone="brand">Một câu hỏi hữu ích</Badge>
                  <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
                    {nextQuestion.question}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    Vì sao CLARA hỏi: {nextQuestion.why}
                  </p>
                  <div className="mt-4 space-y-3">
                    <Textarea
                      label="Câu trả lời của bạn"
                      value={questionAnswer}
                      onChange={(event) => setQuestionAnswer(event.target.value)}
                      hint="Câu trả lời sẽ thành bản nháp để bạn kiểm tra trước khi xác nhận."
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        loading={saving}
                        onClick={() => void answerQuestion()}
                      >
                        Tạo bản nháp
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void dismissQuestion(false)}
                      >
                        Để sau
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void dismissQuestion(true)}
                      >
                        Không hỏi lại
                      </Button>
                    </div>
                  </div>
                </SurfaceCard>
              ) : null}

              {baselines.length ? (
                <SurfaceCard className="p-5">
                  <h2 className="font-semibold text-[var(--text-primary)]">
                    Thay đổi so với chính bạn
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Đây không phải mức bình thường lâm sàng hay chẩn đoán.
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {baselines.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4"
                      >
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                          {item.signal_key}
                        </p>
                        <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">
                          {item.status === "ready"
                            ? `${item.personal_median ?? "—"} ${item.unit}`
                            : "Chưa đủ dữ liệu"}
                        </p>
                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          {item.sample_days} ngày dữ liệu · {item.rule_version}
                        </p>
                      </div>
                    ))}
                  </div>
                </SurfaceCard>
              ) : null}

              {replay ? (
                <SurfaceCard className="overflow-hidden" aria-live="polite">
                  <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                      Health Replay
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                      {replay.episode.title}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      Mỗi mục hiển thị đúng phiên bản, nguồn và quy tắc đã dùng.
                    </p>
                  </div>
                  <div className="space-y-3 p-5">
                    {replay.events.length ? replay.events.map((item) => (
                      <div
                        key={item.revision_id}
                        className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-4"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={item.truth_state === "confirmed" ? "ok" : "neutral"}>
                            {item.truth_state === "confirmed" ? "Đã xác nhận" : "Bạn đã ghi nhận"}
                          </Badge>
                          <span className="text-xs text-[var(--text-muted)]">
                            Phiên bản {item.revision} · {item.policy_version || "quy tắc cũ"}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-[var(--text-primary)]">
                          {String(item.provenance.assertion ?? item.type)}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                          Vì sao có mục này: {item.why.text}
                        </p>
                        {editingEvent === item.id ? (
                          <div className="mt-3 space-y-3">
                            <Textarea
                              label="Thông tin đúng"
                              value={correctionText}
                              onChange={(event) => setCorrectionText(event.target.value)}
                              hint="Chỉnh sửa tạo một phiên bản mới; lịch sử cũ vẫn được giữ để bạn kiểm tra."
                            />
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                loading={saving}
                                onClick={() => void correctEvent(item)}
                              >
                                Lưu phiên bản mới
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setEditingEvent("")}
                              >
                                Hủy
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <Button
                            className="mt-3"
                            size="sm"
                            variant="ghost"
                            icon="edit"
                            onClick={() => {
                              setEditingEvent(item.id);
                              setCorrectionText("");
                            }}
                          >
                            Sửa thông tin
                          </Button>
                        )}
                      </div>
                    )) : (
                      <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                        Hành trình này chưa có bản ghi nào.
                      </p>
                    )}
                    {replay.decisions.some((item) => item.stale) ? (
                      <div
                        role="status"
                        className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]"
                      >
                        Một số kết quả cũ đang được tính lại vì thông tin nguồn đã thay đổi.
                      </div>
                    ) : null}
                  </div>
                </SurfaceCard>
              ) : null}

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
