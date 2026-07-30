"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Select, Textarea } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  acceptLifeMapTask,
  abandonLifeMapCaptureSession,
  actOnLifeMapReviewFinding,
  askLifeMap,
  correctLifeMapEvent,
  disputeLifeMapEvent,
  createLifeMapTask,
  getLifeMapBaselines,
  getLifeMapCaptureArtifact,
  getActiveLifeMapCaptureSession,
  getLifeMapCaptureJob,
  getLifeMapCaptureNormalization,
  getLifeMapCaptureSession,
  getLifeMapDisputes,
  getLifeMapNextQuestion,
  getLifeMapReplay,
  getLifeMapSummary,
  getLifeMapToday,
  getLifeMapV2Capabilities,
  recordLifeMapQuestionInteraction,
  scanLifeMapReviewFindings,
  reviewLifeMapCaptureCandidate,
  resolveLifeMapEvent,
  startLifeMapTextCapture,
  startLifeMapArtifactCapture,
  startLifeMapGuidedAnswer,
  uploadLifeMapCaptureArtifact,
  type CaptureArtifact,
  type CaptureCandidate,
  type CaptureSession,
  type LifeMapBaseline,
  type LifeMapAskAnswer,
  type LifeMapDisputeCase,
  type LifeMapQuestion,
  type LifeMapReviewFinding,
  type LifeMapSummary,
  type MedicationNormalizationProposal,
  type LifeMapToday,
  type LifeMapReplay,
} from "@/lib/lifemap";
import { getProfileContext } from "@/lib/profile-context-api";

function priorityTone(priority: string): "danger" | "warn" | "brand" {
  if (priority === "urgent") return "danger";
  if (priority === "soon") return "warn";
  return "brand";
}

function priorityLabel(
  priority: string,
  copy: (key: UITranslationKey) => string,
): string {
  if (priority === "urgent") return copy("lifemap.priority.urgent");
  if (priority === "soon") return copy("lifemap.priority.soon");
  if (priority === "routine") return copy("lifemap.priority.routine");
  return priority;
}

export default function LifeMapPage() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );
  const [data, setData] = useState<LifeMapToday | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [episodeId, setEpisodeId] = useState("");
  const [captureEnabled, setCaptureEnabled] = useState(false);
  const [questionEnabled, setQuestionEnabled] = useState(false);
  const [askEnabled, setAskEnabled] = useState(false);
  const [reviewEnabled, setReviewEnabled] = useState(false);
  const [summaryEnabled, setSummaryEnabled] = useState(false);
  const [summaryLevel, setSummaryLevel] = useState<"day" | "week" | "episode">(
    "day",
  );
  const [lifeMapSummary, setLifeMapSummary] = useState<LifeMapSummary | null>(
    null,
  );
  const [baselines, setBaselines] = useState<LifeMapBaseline[]>([]);
  const [nextQuestion, setNextQuestion] = useState<LifeMapQuestion | null>(null);
  const [questionAnswer, setQuestionAnswer] = useState("");
  const [captureText, setCaptureText] = useState("");
  const [captureKind, setCaptureKind] = useState<
    "medication_label" | "visit_document"
  >("medication_label");
  const [captureFile, setCaptureFile] = useState<File | null>(null);
  const [captureJobStatus, setCaptureJobStatus] = useState("");
  const [capturePreview, setCapturePreview] = useState<{
    artifact: CaptureArtifact;
    url: string;
  } | null>(null);
  const [captureSession, setCaptureSession] = useState<CaptureSession | null>(null);
  const [captureNormalizations, setCaptureNormalizations] = useState<
    Record<string, MedicationNormalizationProposal | null>
  >({});
  const [acceptedNormalizations, setAcceptedNormalizations] = useState<
    Record<string, boolean>
  >({});
  const [replay, setReplay] = useState<LifeMapReplay | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [editingEvent, setEditingEvent] = useState("");
  const [correctionText, setCorrectionText] = useState("");
  const [askQuery, setAskQuery] = useState("");
  const [askAnswer, setAskAnswer] = useState<LifeMapAskAnswer | null>(null);
  const [reviewFindings, setReviewFindings] = useState<
    LifeMapReviewFinding[]
  >([]);
  const [disputes, setDisputes] = useState<LifeMapDisputeCase[]>([]);
  const [disputingEvent, setDisputingEvent] = useState("");
  const [disputeReason, setDisputeReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getLifeMapToday();
      setData(next);
      setEpisodeId((current) => current || next.episodes[0]?.id || "");
      setDisputes(await getLifeMapDisputes());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("today.connectionError"));
    } finally {
      setLoading(false);
    }
  }, [copy]);

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
        setReviewEnabled(Boolean(capabilities.lifemap_ai_review_findings));
        setSummaryEnabled(Boolean(capabilities.lifemap_ai_summaries));
        if (capabilities.lifemap_baselines_v2) {
          setBaselines(await getLifeMapBaselines());
        }
      })
      .catch(() => {
        setCaptureEnabled(false);
        setQuestionEnabled(false);
        setAskEnabled(false);
        setReviewEnabled(false);
        setSummaryEnabled(false);
      });
  }, [load]);

  useEffect(() => {
    if (!captureEnabled) return;
    // Capture review is server-resumable and profile-scoped. Never keep a
    // health-session pointer in localStorage or browser cache.
    void getActiveLifeMapCaptureSession()
      .then(setCaptureSession)
      .catch(() => setCaptureSession(null));
  }, [captureEnabled]);

  useEffect(
    () => () => {
      if (capturePreview) URL.revokeObjectURL(capturePreview.url);
    },
    [capturePreview],
  );

  const rememberCapture = (session: CaptureSession) => {
    setCaptureSession(session);
  };

  const startCapture = async (event: FormEvent) => {
    event.preventDefault();
    if (!captureText.trim()) return;
    setSaving(true);
    setError("");
    try {
      const session = await startLifeMapTextCapture(captureText.trim());
      rememberCapture(session);
      if (session.persisted) setCaptureText("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.startCapture"));
    } finally {
      setSaving(false);
    }
  };

  const startArtifactCapture = async (event: FormEvent) => {
    event.preventDefault();
    if (!captureFile) return;
    setSaving(true);
    setError("");
    setCaptureJobStatus(copy("lifemap.capture.uploading"));
    try {
      const session = await startLifeMapArtifactCapture(captureKind);
      if (!session.id) throw new Error(copy("lifemap.error.invalidCaptureSession"));
      rememberCapture(session);
      const uploaded = await uploadLifeMapCaptureArtifact(session.id, captureFile);
      setCaptureJobStatus(copy("lifemap.capture.reading"));
      for (let attempt = 0; attempt < 45; attempt += 1) {
        const job = await getLifeMapCaptureJob(uploaded.job.id);
        if (job.status === "completed") {
          rememberCapture(await getLifeMapCaptureSession(session.id));
          setCaptureJobStatus("");
          setCaptureFile(null);
          return;
        }
        if (job.status === "escalated" || job.emergency) {
          rememberCapture({
            ...session,
            emergency: true,
            persisted: true,
            message: job.message,
          });
          setCaptureJobStatus("");
          return;
        }
        if (job.status === "failed") {
          throw new Error(copy("lifemap.error.readCapture"));
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      setCaptureJobStatus(
        copy("lifemap.capture.processing"),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.processCapture"));
    } finally {
      setSaving(false);
    }
  };

  const updateCaptureValue = (
    candidateId: string,
    field: string,
    value: string,
  ) => {
    setCaptureSession((current) =>
      current
        ? {
            ...current,
            candidates: current.candidates?.map((candidate) =>
              candidate.id === candidateId
                ? {
                    ...candidate,
                    value: { ...candidate.value, [field]: value },
                  }
                : candidate,
            ),
          }
        : current,
    );
  };

  const reviewCapture = async (
    candidate: CaptureCandidate,
    action: "edit" | "reject" | "confirm",
  ) => {
    setSaving(true);
    setError("");
    try {
      const result = await reviewLifeMapCaptureCandidate(candidate.id, action, {
        value: candidate.value,
        accept_normalization:
          action === "confirm"
            ? Boolean(acceptedNormalizations[candidate.id])
            : false,
        reason:
          action === "edit"
            ? "Người dùng chỉnh sửa trường trích xuất"
            : action === "reject"
              ? "Người dùng từ chối bản nháp"
              : "Người dùng đã kiểm tra bản ghi",
      });
      setCaptureSession((current) =>
        current
          ? {
              ...current,
              status: action === "confirm" ? "completed" : current.status,
              candidates: current.candidates?.map((item) =>
                item.id === candidate.id
                  ? { ...item, ...result.candidate }
                  : item,
              ),
            }
          : current,
      );
      if (action === "confirm") {
        await load();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu xem xét.");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const medicationCandidates =
      captureSession?.candidates?.filter(
        (candidate) =>
          candidate.type === "medication_label" && candidate.status === "draft",
      ) ?? [];
    if (!medicationCandidates.length) return;
    let active = true;
    void Promise.all(
      medicationCandidates.map(async (candidate) => {
        try {
          return [
            candidate.id,
            await getLifeMapCaptureNormalization(candidate.id),
          ] as const;
        } catch {
          return [candidate.id, null] as const;
        }
      }),
    ).then((entries) => {
      if (!active) return;
      setCaptureNormalizations((current) => ({
        ...current,
        ...Object.fromEntries(entries),
      }));
      setAcceptedNormalizations((current) => ({
        ...current,
        ...Object.fromEntries(entries.map(([candidateId]) => [candidateId, false])),
      }));
    });
    return () => {
      active = false;
    };
  }, [captureSession]);

  const abandonCapture = async () => {
    if (!captureSession?.id) return;
    setSaving(true);
    try {
      await abandonLifeMapCaptureSession(captureSession.id);
      setCaptureSession(null);
      setCaptureJobStatus("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể hủy bản nháp.");
    } finally {
      setSaving(false);
    }
  };

  const previewCaptureArtifact = async (artifact: CaptureArtifact) => {
    setSaving(true);
    try {
      const blob = await getLifeMapCaptureArtifact(artifact);
      if (capturePreview) URL.revokeObjectURL(capturePreview.url);
      setCapturePreview({ artifact, url: URL.createObjectURL(blob) });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể mở nguồn.");
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
      rememberCapture(session);
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

  const disputeEvent = async (item: LifeMapReplay["events"][number]) => {
    if (!disputeReason.trim()) return;
    setSaving(true);
    setError("");
    try {
      await disputeLifeMapEvent(item.id, item.revision, disputeReason.trim());
      setDisputingEvent("");
      setDisputeReason("");
      setDisputes(await getLifeMapDisputes());
      await openReplay(replay?.episode.id ?? episodeId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể gửi tranh chấp.");
    } finally {
      setSaving(false);
    }
  };

  const resolveDispute = async (item: LifeMapDisputeCase) => {
    setSaving(true);
    setError("");
    try {
      await resolveLifeMapEvent(
        item.event_id,
        item.revision,
        "Đã kiểm tra lại nguồn và xác nhận phiên bản này",
      );
      setDisputes(await getLifeMapDisputes());
      if (replay) await openReplay(replay.episode.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xử lý tranh chấp.");
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

  const scanReviewFindings = async () => {
    setSaving(true);
    setError("");
    try {
      setReviewFindings(await scanLifeMapReviewFindings());
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Không thể kiểm tra thông tin.",
      );
    } finally {
      setSaving(false);
    }
  };

  const reviewFinding = async (
    finding: LifeMapReviewFinding,
    action: "resolved" | "dismissed",
  ) => {
    setSaving(true);
    setError("");
    try {
      const updated = await actOnLifeMapReviewFinding(
        finding.id,
        action,
        action === "resolved"
          ? "Người dùng đã kiểm tra các bản ghi nguồn"
          : "Người dùng xác nhận không cần xử lý",
      );
      setReviewFindings((current) =>
        current.map((item) => (item.id === finding.id ? updated : item)),
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Không thể lưu lựa chọn.",
      );
    } finally {
      setSaving(false);
    }
  };

  const loadSummary = async () => {
    setSaving(true);
    setError("");
    try {
      setLifeMapSummary(
        await getLifeMapSummary(
          summaryLevel,
          summaryLevel === "episode" ? episodeId || undefined : undefined,
        ),
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Không thể tạo bản tóm tắt.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title={copy("lifemap.title")}
      description={copy("lifemap.description")}
    >
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

          {loading ? (
            <LoadingCards count={2} />
          ) : (
            <>
              {askEnabled ? (
                <SurfaceCard className="overflow-hidden">
                  <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                    <Badge tone="brand">{copy("lifemap.ask.badge")}</Badge>
                    <h2 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
                      {copy("lifemap.ask.title")}
                    </h2>
                    <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                      {copy("lifemap.ask.description")}
                    </p>
                  </div>
                  <form
                    className="space-y-3 p-5"
                    onSubmit={(event) => void submitAsk(event)}
                  >
                    <Textarea
                      label={copy("lifemap.ask.label")}
                      value={askQuery}
                      onChange={(event) => setAskQuery(event.target.value)}
                      placeholder={copy("lifemap.ask.placeholder")}
                      hint={copy("lifemap.ask.hint")}
                    />
                    <Button
                      type="submit"
                      icon="search"
                      loading={saving}
                      loadingLabel={copy("lifemap.ask.loading")}
                    >
                      {copy("lifemap.ask.submit")}
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
                                    {copy("lifemap.ask.source", {
                                      attribution: source.attribution,
                                      date: formatLocaleDate(language, source.occurred_at, {
                                        dateStyle: "medium",
                                        timeStyle: "short",
                                      }),
                                      revision: source.revision_id.slice(0, 8),
                                    })}
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
                          {copy("lifemap.ask.caution")}
                        </p>
                      ) : null}
                      <p className="mt-4 text-xs text-[var(--text-muted)]">
                        {copy("lifemap.ask.disclosure", {
                          mode: askAnswer.disclosure.mode,
                        })}
                      </p>
                    </div>
                  ) : null}
                </SurfaceCard>
              ) : null}

              {summaryEnabled ? (
                <SurfaceCard className="p-5">
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <Badge tone="brand">{copy("lifemap.summary.badge")}</Badge>
                      <h2 className="mt-2 font-semibold text-[var(--text-primary)]">
                        {copy("lifemap.summary.title")}
                      </h2>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        {copy("lifemap.summary.description")}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-end gap-2">
                      <Select
                        label={copy("lifemap.summary.scope")}
                        value={summaryLevel}
                        onChange={(event) => {
                          setSummaryLevel(
                            event.target.value as "day" | "week" | "episode",
                          );
                          setLifeMapSummary(null);
                        }}
                      >
                        <option value="day">{copy("lifemap.summary.day")}</option>
                        <option value="week">{copy("lifemap.summary.week")}</option>
                        <option value="episode" disabled={!episodeId}>
                          {copy("lifemap.summary.episode")}
                        </option>
                      </Select>
                      <Button
                        size="sm"
                        variant="secondary"
                        icon="summarize"
                        loading={saving}
                        onClick={() => void loadSummary()}
                      >
                        {copy("lifemap.summary.create")}
                      </Button>
                    </div>
                  </div>
                  {lifeMapSummary ? (
                    <div className="mt-4" aria-live="polite">
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {lifeMapSummary.summary}
                      </p>
                      {lifeMapSummary.children.length ? (
                        <ol className="mt-3 space-y-3">
                          {lifeMapSummary.children.map((group) => (
                            <li
                              key={group.group}
                              className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4"
                            >
                              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                                {group.group}
                              </p>
                              <ul className="mt-2 space-y-2">
                                {group.claims.map((claim) => (
                                  <li
                                    key={`${group.group}-${claim.citation_ids.join("-")}`}
                                    className="text-sm text-[var(--text-primary)]"
                                  >
                                    <p>{claim.text}</p>
                                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                      {copy("lifemap.summary.citation", {
                                        attribution: claim.attribution,
                                        date: formatLocaleDate(language, claim.occurred_at, {
                                          dateStyle: "medium",
                                          timeStyle: "short",
                                        }),
                                        sources: claim.citation_ids.join(", "),
                                      })}
                                    </p>
                                    {claim.truth_state !== "confirmed" ? (
                                      <Badge tone="warn">
                                        {claim.truth_state}
                                      </Badge>
                                    ) : null}
                                  </li>
                                ))}
                              </ul>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <p className="mt-2 text-sm text-[var(--text-secondary)]">
                          {copy("lifemap.summary.empty")}
                        </p>
                      )}
                      <p className="mt-3 text-xs text-[var(--text-muted)]">
                        {copy("lifemap.summary.notice")}
                      </p>
                    </div>
                  ) : null}
                </SurfaceCard>
              ) : null}

              {reviewEnabled ? (
                <SurfaceCard className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-semibold text-[var(--text-primary)]">
                        Thông tin cần bạn kiểm tra
                      </h2>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        Quy tắc chỉ phát hiện khả năng trùng hoặc mâu thuẫn; CLARA
                        không tự chọn bản nào đúng.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="fact_check"
                      loading={saving}
                      onClick={() => void scanReviewFindings()}
                    >
                      Kiểm tra
                    </Button>
                  </div>
                  {reviewFindings.length ? (
                    <ul className="mt-4 space-y-3">
                      {reviewFindings.map((finding) => (
                        <li
                          key={finding.id}
                          className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-4"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              tone={
                                finding.status === "pending" ? "warn" : "neutral"
                              }
                            >
                              {finding.kind === "contradiction"
                                ? "Có thể mâu thuẫn"
                                : finding.kind === "duplicate"
                                  ? "Có thể trùng"
                                  : "Cần bổ sung"}
                            </Badge>
                            <span className="text-xs text-[var(--text-muted)]">
                              {finding.field_key} · {finding.rule_version}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-[var(--text-secondary)]">
                            {finding.revision_ids.length
                              ? `${finding.revision_ids.length} phiên bản nguồn`
                              : "Chưa có bản ghi cho trường bắt buộc"}
                          </p>
                          {finding.status === "pending" ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                onClick={() =>
                                  void reviewFinding(finding, "resolved")
                                }
                              >
                                Tôi đã kiểm tra
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  void reviewFinding(finding, "dismissed")
                                }
                              >
                                Không cần xử lý
                              </Button>
                            </div>
                          ) : (
                            <p className="mt-2 text-xs text-[var(--text-muted)]">
                              Đã ghi nhận lựa chọn của bạn.
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
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
                          {priorityLabel(episode.priority, copy)}
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
                        ) : disputingEvent === item.id ? (
                          <div className="mt-3 space-y-3">
                            <Textarea
                              label="Vì sao bạn chưa tin thông tin này?"
                              value={disputeReason}
                              onChange={(event) => setDisputeReason(event.target.value)}
                              hint="Tranh chấp không xóa dữ liệu. CLARA giữ nguyên nguồn và tạo một hàng đợi xem xét."
                            />
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                loading={saving}
                                onClick={() => void disputeEvent(item)}
                              >
                                Gửi để xem xét
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setDisputingEvent("")}
                              >
                                Hủy
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button
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
                            {item.truth_state !== "disputed" ? (
                              <Button
                                size="sm"
                                variant="ghost"
                                icon="report"
                                onClick={() => {
                                  setDisputingEvent(item.id);
                                  setDisputeReason("");
                                }}
                              >
                                Chưa đúng / cần xem xét
                              </Button>
                            ) : null}
                          </div>
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

              {disputes.length ? (
                <SurfaceCard className="p-5" aria-live="polite">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                      Hàng đợi tranh chấp
                    </p>
                    <h2 className="mt-1 font-semibold text-[var(--text-primary)]">
                      Thông tin đang được xem xét
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      CLARA không tự chọn bên nào đúng. Mỗi quyết định tạo một
                      phiên bản mới và giữ lại lịch sử nguồn.
                    </p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {disputes.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-4"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={item.status === "resolved" ? "ok" : "warn"}>
                            {item.status === "resolved" ? "Đã xử lý" : "Đang mở"}
                          </Badge>
                          <span className="text-xs text-[var(--text-muted)]">
                            {item.event_type} · phiên bản {item.revision}
                          </span>
                        </div>
                        {item.requires_clinical_review && item.status === "open" ? (
                          <p className="mt-2 text-sm text-[var(--status-warn-text)]">
                            Loại thông tin này cần người có quyền lâm sàng xem
                            nguồn trước khi xác nhận lại.
                          </p>
                        ) : null}
                        {!item.requires_clinical_review && item.status === "open" ? (
                          <Button
                            className="mt-3"
                            size="sm"
                            variant="secondary"
                            loading={saving}
                            onClick={() => void resolveDispute(item)}
                          >
                            Xác nhận sau khi kiểm tra nguồn
                          </Button>
                        ) : null}
                      </div>
                    ))}
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

        <aside className="min-w-0 space-y-5">
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
                  {captureSession.id ? (
                    <Button
                      className="mt-3"
                      size="sm"
                      variant="secondary"
                      icon="delete"
                      onClick={() => void abandonCapture()}
                    >
                      Xóa tệp đã tải lên
                    </Button>
                  ) : null}
                </div>
              ) : captureSession?.candidates?.length ? (
                <div className="mt-4 space-y-4" aria-live="polite">
                  {captureSession.artifacts?.length ? (
                    <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                        Nguồn gốc
                      </p>
                      {captureSession.artifacts.map((artifact) => (
                        <Button
                          key={artifact.id}
                          className="mt-2"
                          size="sm"
                          variant="secondary"
                          icon="visibility"
                          onClick={() => void previewCaptureArtifact(artifact)}
                        >
                          Xem {artifact.filename}
                        </Button>
                      ))}
                      {capturePreview ? (
                        capturePreview.artifact.media_type.startsWith("image/") ? (
                          // The URL is a short-lived authenticated blob URL,
                          // never the object-store location.
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            className="mt-3 max-h-64 w-full rounded-lg object-contain"
                            src={capturePreview.url}
                            alt={`Nguồn ${capturePreview.artifact.filename}`}
                          />
                        ) : (
                          <a
                            className="focus-ring mt-3 inline-block rounded-lg text-sm font-semibold text-[var(--text-brand)] underline"
                            href={capturePreview.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Mở bản nguồn trong thẻ mới
                          </a>
                        )
                      ) : null}
                    </div>
                  ) : null}
                  {captureSession.candidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                          Bản nháp cần xem lại
                        </p>
                        <Badge tone={candidate.status === "confirmed" ? "ok" : "neutral"}>
                          {candidate.status === "confirmed"
                            ? "Đã xác nhận"
                            : candidate.status === "rejected"
                              ? "Đã từ chối"
                              : "Chưa xác nhận"}
                        </Badge>
                      </div>
                      {candidate.status === "draft" ? (
                        <div className="mt-3 space-y-3">
                          {Object.entries(candidate.value).map(([field, rawValue]) => (
                            <Field
                              key={field}
                              label={field.replaceAll("_", " ")}
                              value={
                                typeof rawValue === "object"
                                  ? JSON.stringify(rawValue)
                                  : String(rawValue ?? "")
                              }
                              onChange={(event) =>
                                updateCaptureValue(
                                  candidate.id,
                                  field,
                                  event.target.value,
                                )
                              }
                            />
                          ))}
                        </div>
                      ) : (
                        <dl className="mt-3 space-y-1 text-sm">
                          {Object.entries(candidate.value).map(([field, rawValue]) => (
                            <div key={field} className="flex gap-2">
                              <dt className="font-medium text-[var(--text-secondary)]">
                                {field.replaceAll("_", " ")}:
                              </dt>
                              <dd className="text-[var(--text-primary)]">
                                {typeof rawValue === "object"
                                  ? JSON.stringify(rawValue)
                                  : String(rawValue ?? "")}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      )}
                      {Object.values(candidate.field_confidence ?? {}).some(
                        (score) => score < 0.8,
                      ) ? (
                        <p className="mt-2 text-xs text-[var(--status-warn-text)]">
                          Một số trường có độ tin cậy thấp. Hãy đối chiếu với nguồn.
                        </p>
                      ) : null}
                      {candidate.missing_critical_fields.length ? (
                        <p
                          className="mt-2 text-xs font-medium text-[var(--status-warn-text)]"
                          role="alert"
                        >
                          Cần bổ sung: {candidate.missing_critical_fields.join(", ")}
                        </p>
                      ) : null}
                      {candidate.security_findings.length ? (
                        <p className="mt-2 text-xs font-medium text-[var(--status-danger-text)]" role="alert">
                          Nguồn có nội dung không an toàn; chỉ có thể từ chối bản nháp này.
                        </p>
                      ) : null}
                      {candidate.type === "medication_label" &&
                      candidate.status === "draft" ? (
                        <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-3">
                          <p className="text-sm font-semibold text-[var(--text-primary)]">
                            Chuẩn hóa tên thuốc
                          </p>
                          {captureNormalizations[candidate.id]?.proposal ? (
                            <>
                              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                                CLARA đề xuất{" "}
                                <span className="font-medium text-[var(--text-primary)]">
                                  {
                                    captureNormalizations[candidate.id]?.proposal
                                      ?.display_name
                                  }
                                </span>{" "}
                                · RxNorm{" "}
                                {
                                  captureNormalizations[candidate.id]?.proposal
                                    ?.code
                                }
                              </p>
                              <label className="mt-2 flex cursor-pointer items-start gap-2 text-sm text-[var(--text-secondary)]">
                                <input
                                  type="checkbox"
                                  className="mt-0.5 size-4 accent-[var(--brand-primary)]"
                                  checked={Boolean(
                                    acceptedNormalizations[candidate.id],
                                  )}
                                  onChange={(event) =>
                                    setAcceptedNormalizations((current) => ({
                                      ...current,
                                      [candidate.id]: event.target.checked,
                                    }))
                                  }
                                />
                                <span>
                                  Dùng mã chuẩn này cho hồ sơ thuốc. Bản ghi chỉ
                                  được tạo sau khi bạn xác nhận bên dưới.
                                </span>
                              </label>
                            </>
                          ) : captureNormalizations[candidate.id] === undefined ? (
                            <p className="mt-1 text-sm text-[var(--text-secondary)]" role="status">
                              Đang kiểm tra từ điển thuốc…
                            </p>
                          ) : (
                            <p className="mt-1 text-sm text-[var(--text-secondary)]">
                              Chưa tìm thấy mã chuẩn phù hợp. Tên gốc vẫn được giữ
                              nguyên và chưa được chuẩn hóa.
                            </p>
                          )}
                        </div>
                      ) : null}
                      {candidate.status === "draft" ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            icon="save"
                            loading={saving}
                            onClick={() => void reviewCapture(candidate, "edit")}
                          >
                            Lưu chỉnh sửa
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            icon="delete"
                            loading={saving}
                            onClick={() => void reviewCapture(candidate, "reject")}
                          >
                            Từ chối
                          </Button>
                          <Button
                            size="sm"
                            icon="verified"
                            loading={saving}
                            disabled={
                              candidate.missing_critical_fields.length > 0 ||
                              candidate.security_findings.length > 0
                            }
                            onClick={() => void reviewCapture(candidate, "confirm")}
                          >
                            Xác nhận sau khi đối chiếu
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {captureSession.status !== "completed" ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon="close"
                      onClick={() => void abandonCapture()}
                    >
                      Hủy và xóa bản nháp
                    </Button>
                  ) : null}
                </div>
              ) : captureSession?.id ? (
                <div className="mt-4 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4" role="status">
                  <p className="text-sm text-[var(--text-secondary)]">
                    {captureJobStatus || "Bản nháp đã lưu. Đang chờ kết quả đọc tệp."}
                  </p>
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="ghost"
                    icon="close"
                    onClick={() => void abandonCapture()}
                  >
                    Hủy bản nháp
                  </Button>
                </div>
              ) : (
                <div className="mt-4 space-y-5">
                  <form className="space-y-3" onSubmit={(event) => void startCapture(event)}>
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
                      Tạo bản nháp văn bản
                    </Button>
                  </form>
                  <form
                    className="space-y-3 border-t border-[color:var(--shell-border)] pt-4"
                    onSubmit={(event) => void startArtifactCapture(event)}
                  >
                    <Select
                      label="Loại tài liệu"
                      value={captureKind}
                      onChange={(event) =>
                        setCaptureKind(
                          event.target.value as
                            | "medication_label"
                            | "visit_document",
                        )
                      }
                    >
                      <option value="medication_label">Nhãn thuốc</option>
                      <option value="visit_document">Tài liệu sau khám</option>
                    </Select>
                    <label className="block text-sm font-medium text-[var(--text-primary)]">
                      Tệp nguồn
                      <input
                        className="focus-ring mt-1 block w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-raised)] p-2 text-sm"
                        type="file"
                        accept={
                          captureKind === "medication_label"
                            ? "image/png,image/jpeg"
                            : "image/png,image/jpeg,application/pdf,text/plain"
                        }
                        onChange={(event) =>
                          setCaptureFile(event.target.files?.[0] ?? null)
                        }
                      />
                    </label>
                    <p className="text-xs text-[var(--text-muted)]">
                      Cần kết nối mạng. CLARA chỉ tạo bản nháp và giữ nguồn để bạn
                      đối chiếu.
                    </p>
                    <Button
                      type="submit"
                      block
                      variant="secondary"
                      loading={saving}
                      disabled={!captureFile}
                      icon="upload_file"
                    >
                      Tải lên và tạo bản nháp
                    </Button>
                  </form>
                </div>
              )}
            </SurfaceCard>
          ) : null}

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Tạo hành trình</h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              Hoàn thành từng thông tin trên một trang riêng, sau đó kiểm tra trước khi tạo.
            </p>
            <Button
              as="link"
              href="/lifemap/new"
              block
              icon="arrow_forward"
              iconTrailing
              className="mt-4"
            >
              Bắt đầu từng bước
            </Button>
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
