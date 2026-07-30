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
  getLifeMapRevisionComparison,
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
  type LifeMapRevisionComparison,
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

function truthStateLabel(
  state: string,
  copy: (key: UITranslationKey) => string,
): string {
  switch (state) {
    case "draft":
    case "extracted_draft":
      return copy("lifemap.truth.draft");
    case "user_reported":
    case "reported":
      return copy("lifemap.truth.userReported");
    case "confirmed":
      return copy("lifemap.truth.confirmed");
    case "disputed":
      return copy("lifemap.truth.disputed");
    case "superseded":
      return copy("lifemap.truth.superseded");
    case "invalidated":
      return copy("lifemap.truth.invalidated");
    case "entered_in_error":
      return copy("lifemap.truth.enteredInError");
    default:
      return copy("lifemap.truth.unknown");
  }
}

function comparisonValue(value: unknown, language: "vi" | "en"): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (typeof value === "object") {
    const record = value as { kind?: unknown; item_count?: unknown; field_count?: unknown };
    if (record.kind === "list") {
      return t(language, "lifemap.replay.compareList", {
        count: String(record.item_count ?? 0),
      });
    }
    if (record.kind === "structured") {
      return t(language, "lifemap.replay.compareStructured", {
        count: String(record.field_count ?? 0),
      });
    }
  }
  return t(language, "lifemap.replay.compareStructuredUnknown");
}

function sourceSpanLabel(sourceSpan: unknown): string {
  if (!sourceSpan || typeof sourceSpan !== "object") return "";
  const record = sourceSpan as {
    start?: unknown;
    end?: unknown;
    fields?: Record<string, { start?: unknown; end?: unknown }>;
  };
  if (typeof record.start === "number" && typeof record.end === "number") {
    return `${record.start}–${record.end}`;
  }
  if (record.fields && typeof record.fields === "object") {
    const labels = Object.entries(record.fields)
      .filter(([, item]) => typeof item?.start === "number" && typeof item?.end === "number")
      .map(([field, item]) => `${field}: ${item.start}–${item.end}`);
    return labels.join(" · ");
  }
  return "";
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
  const [revisionComparison, setRevisionComparison] =
    useState<LifeMapRevisionComparison | null>(null);
  const [comparisonEventId, setComparisonEventId] = useState("");
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
            ? copy("lifemap.audit.captureEdited")
            : action === "reject"
              ? copy("lifemap.audit.captureRejected")
              : copy("lifemap.audit.captureConfirmed"),
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.review"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.abandonCapture"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.openSource"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.addTask"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.loadReplay"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.loadQuestion"));
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.saveAnswer"));
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
        permanent
          ? copy("lifemap.audit.questionDoNotAsk")
          : copy("lifemap.audit.questionLater"),
      );
      setNextQuestion(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.updateQuestion"));
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
        copy("lifemap.audit.replayCorrection"),
      );
      setEditingEvent("");
      setCorrectionText("");
      await openReplay(replay?.episode.id ?? episodeId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.saveCorrection"));
    } finally {
      setSaving(false);
    }
  };

  const compareRevision = async (item: LifeMapReplay["events"][number]) => {
    setReplayLoading(true);
    setError("");
    try {
      setComparisonEventId(item.id);
      setRevisionComparison(
        await getLifeMapRevisionComparison(
          item.id,
          item.revision,
          language,
        ),
      );
    } catch (cause) {
      setComparisonEventId("");
      setRevisionComparison(null);
      setError(
        cause instanceof Error
          ? cause.message
          : copy("lifemap.error.loadReplay"),
      );
    } finally {
      setReplayLoading(false);
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
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.submitDispute"));
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
        copy("lifemap.audit.disputeResolved"),
      );
      setDisputes(await getLifeMapDisputes());
      if (replay) await openReplay(replay.episode.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("lifemap.error.resolveDispute"));
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
        cause instanceof Error ? cause.message : copy("lifemap.error.ask"),
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
        cause instanceof Error ? cause.message : copy("lifemap.error.scanReview"),
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
          ? copy("lifemap.audit.reviewResolved")
          : copy("lifemap.audit.reviewDismissed"),
      );
      setReviewFindings((current) =>
        current.map((item) => (item.id === finding.id ? updated : item)),
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : copy("lifemap.error.reviewChoice"),
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
          : copy("lifemap.error.createSummary"),
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
                                        {truthStateLabel(claim.truth_state, copy)}
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
                        {copy("lifemap.review.title")}
                      </h2>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        {copy("lifemap.review.description")}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="fact_check"
                      loading={saving}
                      onClick={() => void scanReviewFindings()}
                    >
                      {copy("lifemap.review.scan")}
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
                                ? copy("lifemap.review.kind.contradiction")
                                : finding.kind === "duplicate"
                                  ? copy("lifemap.review.kind.duplicate")
                                  : copy("lifemap.review.kind.missing")}
                            </Badge>
                            <span className="text-xs text-[var(--text-muted)]">
                              {finding.field_key} · {finding.rule_version}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-[var(--text-secondary)]">
                            {finding.revision_ids.length
                              ? copy("lifemap.review.sourceVersions", {
                                  count: finding.revision_ids.length,
                                })
                              : copy("lifemap.review.noRequiredRecord")}
                          </p>
                          {finding.status === "pending" ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                onClick={() =>
                                  void reviewFinding(finding, "resolved")
                                }
                              >
                                {copy("lifemap.review.checked")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  void reviewFinding(finding, "dismissed")
                                }
                              >
                                {copy("lifemap.review.dismiss")}
                              </Button>
                            </div>
                          ) : (
                            <p className="mt-2 text-xs text-[var(--text-muted)]">
                              {copy("lifemap.review.recorded")}
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
                    {copy("lifemap.episodes.eyebrow")}
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                    {copy("lifemap.episodes.title")}
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
                            {copy("lifemap.episodes.createdByYou")}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon="history"
                          loading={replayLoading}
                          onClick={() => void openReplay(episode.id)}
                        >
                          {copy("lifemap.episodes.replay")}
                        </Button>
                        {questionEnabled ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            icon="help"
                            loading={saving}
                            onClick={() => void loadQuestion(episode.id)}
                          >
                            {copy("lifemap.episodes.question")}
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
                      title={copy("lifemap.episodes.emptyTitle")}
                      description={copy("lifemap.episodes.emptyDescription")}
                    />
                  </div>
                )}
              </SurfaceCard>

              {nextQuestion?.ask ? (
                <SurfaceCard className="p-5">
                  <Badge tone="brand">{copy("lifemap.question.badge")}</Badge>
                  <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
                    {nextQuestion.question}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                    {copy("lifemap.question.why", { reason: nextQuestion.why })}
                  </p>
                  <div className="mt-4 space-y-3">
                    <Textarea
                      label={copy("lifemap.question.answerLabel")}
                      value={questionAnswer}
                      onChange={(event) => setQuestionAnswer(event.target.value)}
                      hint={copy("lifemap.question.answerHint")}
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        loading={saving}
                        onClick={() => void answerQuestion()}
                      >
                        {copy("lifemap.question.createDraft")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void dismissQuestion(false)}
                      >
                        {copy("lifemap.question.later")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void dismissQuestion(true)}
                      >
                        {copy("lifemap.question.never")}
                      </Button>
                    </div>
                  </div>
                </SurfaceCard>
              ) : null}

              {baselines.length ? (
                <SurfaceCard className="p-5">
                  <h2 className="font-semibold text-[var(--text-primary)]">
                    {copy("lifemap.baseline.title")}
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    {copy("lifemap.baseline.description")}
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
                            : copy("lifemap.baseline.insufficient")}
                        </p>
                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          {copy("lifemap.baseline.sampleDays", {
                            count: item.sample_days,
                            version: item.rule_version,
                          })}
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
                      {copy("lifemap.replay.eyebrow")}
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                      {replay.episode.title}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {copy("lifemap.replay.description")}
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
                            {truthStateLabel(item.truth_state, copy)}
                          </Badge>
                          <span className="text-xs text-[var(--text-muted)]">
                            {copy("lifemap.replay.version", {
                              revision: item.revision,
                              policy: item.policy_version || copy("lifemap.replay.legacyPolicy"),
                            })}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-[var(--text-primary)]">
                          {String(item.provenance.assertion ?? item.type)}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                          {copy("lifemap.replay.why", { reason: item.why.text })}
                        </p>
                        {editingEvent === item.id ? (
                          <div className="mt-3 space-y-3">
                            <Textarea
                              label={copy("lifemap.replay.correctionLabel")}
                              value={correctionText}
                              onChange={(event) => setCorrectionText(event.target.value)}
                              hint={copy("lifemap.replay.correctionHint")}
                            />
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                loading={saving}
                                onClick={() => void correctEvent(item)}
                              >
                                {copy("lifemap.replay.saveCorrection")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setEditingEvent("")}
                              >
                                {copy("lifemap.replay.cancel")}
                              </Button>
                            </div>
                          </div>
                        ) : disputingEvent === item.id ? (
                          <div className="mt-3 space-y-3">
                            <Textarea
                              label={copy("lifemap.replay.disputeLabel")}
                              value={disputeReason}
                              onChange={(event) => setDisputeReason(event.target.value)}
                              hint={copy("lifemap.replay.disputeHint")}
                            />
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                loading={saving}
                                onClick={() => void disputeEvent(item)}
                              >
                                {copy("lifemap.replay.submitDispute")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setDisputingEvent("")}
                              >
                                {copy("lifemap.replay.cancel")}
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              icon="compare_arrows"
                              loading={
                                replayLoading && comparisonEventId === item.id
                              }
                              loadingLabel={copy("lifemap.replay.compareLoading")}
                              onClick={() => void compareRevision(item)}
                            >
                              {copy("lifemap.replay.compare")}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              icon="edit"
                              onClick={() => {
                                setEditingEvent(item.id);
                                setCorrectionText("");
                              }}
                            >
                              {copy("lifemap.replay.edit")}
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
                                {copy("lifemap.replay.dispute")}
                              </Button>
                            ) : null}
                          </div>
                        )}
                        {revisionComparison?.event_id === item.id ? (
                          <div className="mt-4 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4">
                            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                              {copy("lifemap.replay.compareTitle")}
                            </h3>
                            <p className="mt-2 text-sm text-[var(--text-secondary)]">
                              {revisionComparison.summary}
                            </p>
                            {revisionComparison.changes.length ? (
                              <dl className="mt-3 space-y-3">
                                {revisionComparison.changes.map((change) => (
                                  <div
                                    key={change.field}
                                    className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-raised)] p-3"
                                  >
                                    <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                                      {change.field === "truth_state"
                                        ? copy("lifemap.replay.compareTruthState")
                                        : change.field === "reason_code"
                                          ? copy("lifemap.replay.compareReason")
                                          : change.field.replaceAll("_", " ")}
                                    </dt>
                                    <dd className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                                      <span className="text-[var(--text-secondary)]">
                                        {copy("lifemap.replay.compareBefore")}: {comparisonValue(change.before, language)}
                                      </span>
                                      <span className="text-[var(--text-primary)]">
                                        {copy("lifemap.replay.compareAfter")}: {comparisonValue(change.after, language)}
                                      </span>
                                    </dd>
                                  </div>
                                ))}
                              </dl>
                            ) : (
                              <p className="mt-3 text-sm text-[var(--text-secondary)]">
                                {copy("lifemap.replay.compareEmpty")}
                              </p>
                            )}
                            <div className="mt-3 grid gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
                              {(["before", "after"] as const).map((position) => {
                                const source = revisionComparison.source_spans[position];
                                const span = sourceSpanLabel(source?.source_span);
                                return (
                                  <p key={position}>
                                    <span className="font-semibold text-[var(--text-primary)]">
                                      {copy(
                                        position === "before"
                                          ? "lifemap.replay.compareBefore"
                                          : "lifemap.replay.compareAfter",
                                      )}
                                      :
                                    </span>{" "}
                                    {span
                                      ? `${copy("lifemap.replay.compareSource")}: ${span}`
                                      : copy("lifemap.replay.compareNoSource")}
                                  </p>
                                );
                              })}
                            </div>
                            <p className="mt-3 text-xs text-[var(--text-muted)]">
                              {copy("lifemap.replay.compareNotice")}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    )) : (
                      <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                        {copy("lifemap.replay.empty")}
                      </p>
                    )}
                    {replay.decisions.some((item) => item.stale) ? (
                      <div
                        role="status"
                        className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]"
                      >
                        {copy("lifemap.replay.stale")}
                      </div>
                    ) : null}
                  </div>
                </SurfaceCard>
              ) : null}

              {disputes.length ? (
                <SurfaceCard className="p-5" aria-live="polite">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                      {copy("lifemap.disputes.eyebrow")}
                    </p>
                    <h2 className="mt-1 font-semibold text-[var(--text-primary)]">
                      {copy("lifemap.disputes.title")}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {copy("lifemap.disputes.description")}
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
                            {item.status === "resolved"
                              ? copy("lifemap.disputes.resolved")
                              : copy("lifemap.disputes.open")}
                          </Badge>
                          <span className="text-xs text-[var(--text-muted)]">
                            {copy("lifemap.disputes.version", {
                              eventType: item.event_type,
                              revision: item.revision,
                            })}
                          </span>
                        </div>
                        {item.requires_clinical_review && item.status === "open" ? (
                          <p className="mt-2 text-sm text-[var(--status-warn-text)]">
                            {copy("lifemap.disputes.clinicalReview")}
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
                            {copy("lifemap.disputes.resolve")}
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
                    <h2 className="font-semibold text-[var(--text-primary)]">
                      {copy("lifemap.tasks.title")}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      {copy("lifemap.tasks.description")}
                    </p>
                  </div>
                  <Link
                    href="/today"
                    className="focus-ring shrink-0 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
                  >
                    {copy("lifemap.tasks.openToday")}
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
                      {copy("lifemap.tasks.empty")}
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
                    {copy("lifemap.capture.title")}
                  </h2>
                  <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
                    {copy("lifemap.capture.description")}
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
                      {copy("lifemap.capture.deleteUpload")}
                    </Button>
                  ) : null}
                </div>
              ) : captureSession?.candidates?.length ? (
                <div className="mt-4 space-y-4" aria-live="polite">
                  {captureSession.artifacts?.length ? (
                    <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                        {copy("lifemap.capture.provenance")}
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
                          {copy("lifemap.capture.viewFile", {
                            filename: artifact.filename,
                          })}
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
                            alt={copy("lifemap.capture.sourceAlt", {
                              filename: capturePreview.artifact.filename,
                            })}
                          />
                        ) : (
                          <a
                            className="focus-ring mt-3 inline-block rounded-lg text-sm font-semibold text-[var(--text-brand)] underline"
                            href={capturePreview.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {copy("lifemap.capture.openSource")}
                          </a>
                        )
                      ) : null}
                    </div>
                  ) : null}
                  {captureSession.candidates
                    // Source rows preserve the exact original note for
                    // provenance. They are never reviewable/confirmable; show
                    // only the separately reviewable text drafts to consumers.
                    .filter((candidate) => candidate.type !== "text_source")
                    .map((candidate) => (
                    <div
                      key={candidate.id}
                      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                          {copy("lifemap.capture.draft")}
                        </p>
                        <Badge tone={candidate.status === "confirmed" ? "ok" : "neutral"}>
                          {candidate.status === "confirmed"
                            ? copy("lifemap.replay.confirmed")
                            : candidate.status === "rejected"
                              ? copy("lifemap.capture.rejected")
                              : copy("lifemap.capture.unconfirmed")}
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
                          {copy("lifemap.capture.lowConfidence")}
                        </p>
                      ) : null}
                      {candidate.missing_critical_fields.length ? (
                        <p
                          className="mt-2 text-xs font-medium text-[var(--status-warn-text)]"
                          role="alert"
                        >
                          {copy("lifemap.capture.required", {
                            fields: candidate.missing_critical_fields.join(", "),
                          })}
                        </p>
                      ) : null}
                      {candidate.security_findings.length ? (
                        <p className="mt-2 text-xs font-medium text-[var(--status-danger-text)]" role="alert">
                          {copy("lifemap.capture.unsafe")}
                        </p>
                      ) : null}
                      {candidate.type === "medication_label" &&
                      candidate.status === "draft" ? (
                        <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-3">
                          <p className="text-sm font-semibold text-[var(--text-primary)]">
                            {copy("lifemap.capture.normalizeTitle")}
                          </p>
                          {captureNormalizations[candidate.id]?.proposal ? (
                            <>
                              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                                {copy("lifemap.capture.normalizeProposal", {
                                  name:
                                    captureNormalizations[candidate.id]?.proposal
                                      ?.display_name ?? "",
                                  code:
                                    captureNormalizations[candidate.id]?.proposal
                                      ?.code ?? "",
                                })}
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
                                <span>{copy("lifemap.capture.normalizeAccept")}</span>
                              </label>
                            </>
                          ) : captureNormalizations[candidate.id] === undefined ? (
                            <p className="mt-1 text-sm text-[var(--text-secondary)]" role="status">
                              {copy("lifemap.capture.normalizeLoading")}
                            </p>
                          ) : (
                            <p className="mt-1 text-sm text-[var(--text-secondary)]">
                              {copy("lifemap.capture.normalizeEmpty")}
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
                            {copy("lifemap.capture.saveEdit")}
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            icon="delete"
                            loading={saving}
                            onClick={() => void reviewCapture(candidate, "reject")}
                          >
                            {copy("lifemap.capture.reject")}
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
                            {copy("lifemap.capture.confirm")}
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
                      {copy("lifemap.capture.cancelDelete")}
                    </Button>
                  ) : null}
                </div>
              ) : captureSession?.id ? (
                <div className="mt-4 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4" role="status">
                  <p className="text-sm text-[var(--text-secondary)]">
                    {captureJobStatus || copy("lifemap.capture.pending")}
                  </p>
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="ghost"
                    icon="close"
                    onClick={() => void abandonCapture()}
                  >
                    {copy("lifemap.capture.cancel")}
                  </Button>
                </div>
              ) : (
                <div className="mt-4 space-y-5">
                  <form className="space-y-3" onSubmit={(event) => void startCapture(event)}>
                    <Textarea
                      label={copy("lifemap.capture.textLabel")}
                      value={captureText}
                      onChange={(event) => setCaptureText(event.target.value)}
                      placeholder={copy("lifemap.capture.textPlaceholder")}
                    />
                    <Button
                      type="submit"
                      block
                      loading={saving}
                      loadingLabel={copy("lifemap.capture.processing")}
                      icon="add_notes"
                    >
                      {copy("lifemap.capture.createText")}
                    </Button>
                  </form>
                  <form
                    className="space-y-3 border-t border-[color:var(--shell-border)] pt-4"
                    onSubmit={(event) => void startArtifactCapture(event)}
                  >
                    <Select
                      label={copy("lifemap.capture.documentKind")}
                      value={captureKind}
                      onChange={(event) =>
                        setCaptureKind(
                          event.target.value as
                            | "medication_label"
                            | "visit_document",
                        )
                      }
                    >
                      <option value="medication_label">
                        {copy("lifemap.capture.medicationLabel")}
                      </option>
                      <option value="visit_document">
                        {copy("lifemap.capture.visitDocument")}
                      </option>
                    </Select>
                    <label className="block text-sm font-medium text-[var(--text-primary)]">
                      {copy("lifemap.capture.sourceFile")}
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
                      {copy("lifemap.capture.networkHint")}
                    </p>
                    <Button
                      type="submit"
                      block
                      variant="secondary"
                      loading={saving}
                      disabled={!captureFile}
                      icon="upload_file"
                    >
                      {copy("lifemap.capture.upload")}
                    </Button>
                  </form>
                </div>
              )}
            </SurfaceCard>
          ) : null}

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">
              {copy("lifemap.create.title")}
            </h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              {copy("lifemap.create.description")}
            </p>
            <Button
              as="link"
              href="/lifemap/new"
              block
              icon="arrow_forward"
              iconTrailing
              className="mt-4"
            >
              {copy("lifemap.create.start")}
            </Button>
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">
              {copy("lifemap.taskCreate.title")}
            </h2>
            <form className="mt-4 space-y-3.5" onSubmit={(event) => void makeTask(event)}>
              <Select
                label={copy("lifemap.taskCreate.episode")}
                required
                value={episodeId}
                onChange={(event) => setEpisodeId(event.target.value)}
              >
                <option value="">{copy("lifemap.taskCreate.chooseEpisode")}</option>
                {data?.episodes.map((episode) => (
                  <option key={episode.id} value={episode.id}>
                    {episode.title}
                  </option>
                ))}
              </Select>
              <Field
                label={copy("lifemap.taskCreate.label")}
                required
                value={taskTitle}
                onChange={(event) => setTaskTitle(event.target.value)}
                disabled={!episodeId}
                placeholder={copy("lifemap.taskCreate.placeholder")}
              />
              <Button
                type="submit"
                variant="secondary"
                block
                disabled={saving || !episodeId}
                icon="playlist_add"
              >
                {copy("lifemap.taskCreate.submit")}
              </Button>
            </form>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
