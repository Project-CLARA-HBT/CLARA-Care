"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import FlowTimelinePanel from "@/components/research/flow-timeline-panel";
import MarkdownAnswer from "@/components/research/markdown-answer";
import TelemetryDetailsPanel from "@/components/research/telemetry-details-panel";
import {
  createConversationItem,
  createConversationItemFromPersisted,
  formatHistoryTime,
  resolveFlowModeFromResult
} from "@/components/research/lib/research-page-helpers";
import { ConversationItem, ResearchResult } from "@/components/research/lib/research-page-types";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import { ChatResponse, getChatIntentDebug, getChatReply } from "@/lib/chat";
import api from "@/lib/http-client";
import {
  RESEARCH_TIER2_JOB_POLL_MS,
  ResearchExecutionMode,
  ResearchFlowEvent,
  ResearchFlowStage,
  ResearchTier,
  appendResearchConversationMessage,
  createResearchTier2Job,
  createResearchConversation,
  getResearchTier2Job,
  listResearchConversationMessages,
  listResearchConversations,
  normalizeResearchTier2JobProgress,
  normalizeResearchTier2,
  streamResearchTier2Job,
} from "@/lib/research";

const QUICK_PROMPTS: string[] = [
  "So sánh DASH và Địa Trung Hải cho bệnh tim mạch",
  "Tương tác Warfarin với thuốc giảm đau phổ biến",
  "Checklist an toàn khi dùng 5 thuốc cùng lúc",
  "Tóm tắt cảnh báo DDI theo mức độ nguy cơ"
];

const ADVANCED_LINKS: Array<{ href: string; label: string }> = [
  { href: "/research/deepdive", label: "Deepdive" },
  { href: "/research/analyze", label: "Analyze" },
  { href: "/research/citations", label: "Citations" },
  { href: "/research/details", label: "Details" }
];

const RESEARCH_MODE_OPTIONS: Array<{ id: ResearchExecutionMode; label: string }> = [
  { id: "fast", label: "Fast" },
  { id: "deep", label: "Deep" },
  { id: "deep_beta", label: "Deep Beta" }
];

const EMPTY_TELEMETRY = {
  keywords: [],
  searchPlan: { keywords: [], subqueries: [], connectors: [] },
  sourceAttempts: [],
  indexSummary: {},
  crawlSummary: { domains: [] },
  docs: [],
  scores: [],
  sourceReasoning: [],
  verificationMatrix: [],
  contradictionSummary: undefined,
  traceMetadata: {},
  errors: [],
  fallbackInfo: []
};

const JOB_FETCH_RETRY_ATTEMPTS = 3;
const JOB_FETCH_RETRY_BACKOFF_MS = 600;
const JOB_COMPLETED_RESULT_REFETCH_ATTEMPTS = 5;
const JOB_COMPLETED_RESULT_REFETCH_MS = 900;

function isAttemptLikelyFailed(status?: string, hasError?: boolean): boolean {
  if (hasError) return true;
  const text = (status ?? "").toLowerCase();
  if (!text) return false;
  return ["fail", "error", "timeout", "warn", "degraded", "reject", "deny"].some((token) =>
    text.includes(token)
  );
}

function buildTier2MetaSummary(result: Extract<ResearchResult, { tier: "tier2" }>) {
  const searchPlan = result.telemetry.searchPlan;
  const attempts = result.telemetry.sourceAttempts;
  const failedAttempts = attempts.filter((attempt) =>
    isAttemptLikelyFailed(attempt.status, Boolean(attempt.error))
  ).length;
  const primaryQuery = searchPlan.query ?? searchPlan.subqueries[0];
  const hasQueryPlan =
    Boolean(primaryQuery) ||
    searchPlan.subqueries.length > 0 ||
    searchPlan.connectors.length > 0 ||
    searchPlan.keywords.length > 0 ||
    searchPlan.topK !== undefined ||
    searchPlan.totalCandidates !== undefined;
  const hasData = hasQueryPlan || attempts.length > 0 || result.telemetry.errors.length > 0;

  return {
    hasData,
    primaryQuery,
    subqueryCount: searchPlan.subqueries.length,
    connectorCount: searchPlan.connectors.length,
    attemptCount: attempts.length,
    failedAttemptCount: failedAttempts,
    errorCount: result.telemetry.errors.length,
    topErrors: result.telemetry.errors.slice(0, 3)
  };
}

function normalizeResearchMode(value?: string): ResearchExecutionMode {
  if (value === "deep") return "deep";
  if (value === "deep_beta") return "deep_beta";
  return "fast";
}

function formatLiveEventTime(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "";
  return date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function summarizeLiveEvent(event: ResearchFlowEvent): string {
  const payload = event.payload;
  if (!payload) return "";
  const pieces: string[] = [];
  if (typeof payload.progress_percent === "number") pieces.push(`progress ${payload.progress_percent}%`);
  if (typeof payload.elapsed_seconds === "number") pieces.push(`${payload.elapsed_seconds.toFixed(1)}s`);
  if (typeof payload.pass_index === "number") pieces.push(`pass #${payload.pass_index}`);
  if (typeof payload.source_count === "number") pieces.push(`sources ${payload.source_count}`);
  if (typeof payload.total_candidates === "number") pieces.push(`candidates ${payload.total_candidates}`);
  if (typeof payload.phase === "string" && payload.phase.trim()) pieces.push(`phase ${payload.phase}`);
  return pieces.join(" · ");
}

function toResearchModeLabel(mode?: string): string {
  if (mode === "deep_beta") return "DEEP BETA";
  if (mode === "deep") return "DEEP";
  return "FAST";
}

export default function ResearchPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [selectedTier, setSelectedTier] = useState<ResearchTier>("tier1");
  const [selectedResearchMode, setSelectedResearchMode] = useState<ResearchExecutionMode>("fast");
  const [query, setQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showLiveResearchTrace, setShowLiveResearchTrace] = useState(true);
  const [liveFlowStages, setLiveFlowStages] = useState<ResearchFlowStage[]>([]);
  const [liveFlowEvents, setLiveFlowEvents] = useState<ResearchFlowEvent[]>([]);
  const [liveReasoningNotes, setLiveReasoningNotes] = useState<string[]>([]);
  const [liveStatusNote, setLiveStatusNote] = useState("");
  const [liveJobId, setLiveJobId] = useState<string | null>(null);

  const [history, setHistory] = useState<ConversationItem[]>([]);
  const [conversationTurns, setConversationTurns] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const loadConversationTurns = async (conversationId: string, fallbackItem?: ConversationItem) => {
    setIsLoadingConversation(true);
    try {
      const rows = await listResearchConversationMessages(conversationId, 160);
      if (!rows.length) {
        setConversationTurns(fallbackItem ? [fallbackItem] : []);
        return;
      }

      const turns = rows.map((row, index) => {
        const parsed = createConversationItemFromPersisted({
          id: String(conversationId),
          queryId: row.queryId,
          query: row.query,
          result: row.result,
          tier: row.tier,
          createdAt: row.createdAt,
        });
        return {
          ...parsed,
          id: `${conversationId}-${row.queryId ?? index}`,
        };
      });
      setConversationTurns(turns);
    } catch {
      setConversationTurns(fallbackItem ? [fallbackItem] : []);
    } finally {
      setIsLoadingConversation(false);
    }
  };

  useEffect(() => {
    setRole(getRole());
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadHistory = async () => {
      try {
        const rows = await listResearchConversations(60);
        if (cancelled) return;
        const items = rows.map((row) => createConversationItemFromPersisted(row));
        setHistory(items);

        if (!items.length) return;

        const firstItem = items[0];
        setActiveConversationId(firstItem.id);
        setConversationTurns([firstItem]);
        setSelectedTier(firstItem.result.tier);
        setSelectedResearchMode(
          firstItem.result.tier === "tier2" ? normalizeResearchMode(firstItem.result.researchMode) : "fast"
        );
        void loadConversationTurns(firstItem.id, firstItem);
      } catch (cause) {
        if (cancelled) return;
        setError(cause instanceof Error ? cause.message : "Không thể tải lịch sử hội thoại.");
      }
    };

    void loadHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  const conversationScrollRef = useRef<HTMLDivElement | null>(null);

  const latestTurn = useMemo(
    () => (conversationTurns.length ? conversationTurns[conversationTurns.length - 1] : null),
    [conversationTurns]
  );
  const lastResult = latestTurn?.result ?? null;

  const flowMode = useMemo(
    () => (lastResult?.tier === "tier2" ? resolveFlowModeFromResult(lastResult) : "idle"),
    [lastResult]
  );

  const latestAnswerText = useMemo(() => {
    if (!lastResult) return "";
    return lastResult.tier === "tier2" ? (lastResult.answer || "") : (lastResult.answer || "");
  }, [lastResult]);

  useEffect(() => {
    const node = conversationScrollRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [conversationTurns, isLoadingConversation, isSubmitting]);

  const createNewConversation = () => {
    setActiveConversationId(null);
    setConversationTurns([]);
    setQuery("");
    setError("");
    setLiveFlowStages([]);
    setLiveFlowEvents([]);
    setLiveReasoningNotes([]);
    setLiveStatusNote("");
    setLiveJobId(null);
  };

  const onSelectConversation = (item: ConversationItem) => {
    setActiveConversationId(item.id);
    setConversationTurns([item]);
    setSelectedTier(item.result.tier);
    setSelectedResearchMode(item.result.tier === "tier2" ? normalizeResearchMode(item.result.researchMode) : "fast");
    setError("");
    setLiveFlowStages([]);
    setLiveFlowEvents([]);
    setLiveReasoningNotes([]);
    setLiveStatusNote("");
    setLiveJobId(null);
    void loadConversationTurns(item.id, item);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isSubmitting) return;

    setError("");
    setIsSubmitting(true);

    try {
      let nextResult: ResearchResult;
      if (selectedTier === "tier1") {
        const response = await api.post<ChatResponse>("/chat", { message });
        const answer = getChatReply(response.data);
        if (!answer) {
          throw new Error("Chưa có nội dung trả lời hợp lệ.");
        }
        nextResult = {
          tier: "tier1",
          answer,
          debug: getChatIntentDebug(response.data)
        };
      } else {
        const job = await createResearchTier2Job(message, {
          researchMode: selectedResearchMode
        });
        setLiveJobId(job.job_id);

        let currentJob = job;
        let finalPayload: Record<string, unknown> | null = null;
        const applyLiveSnapshot = (snapshot: typeof currentJob) => {
          const progress = normalizeResearchTier2JobProgress(snapshot.progress);
          setLiveFlowStages(progress.flowStages);
          setLiveFlowEvents(progress.flowEvents);
          setLiveReasoningNotes(progress.reasoningNotes);
          setLiveStatusNote(progress.statusNote ?? "");
        };

        applyLiveSnapshot(currentJob);
        let streamError: string | null = null;
        try {
          await streamResearchTier2Job(job.job_id, {
            onEvent: (eventPayload) => {
              const payload = eventPayload.payload;
              if (payload && typeof payload === "object" && "status" in payload) {
                currentJob = payload as typeof currentJob;
                applyLiveSnapshot(currentJob);
              }
              if (
                eventPayload.event === "error" &&
                payload &&
                typeof payload === "object" &&
                "message" in payload
              ) {
                const messageText =
                  typeof (payload as { message?: unknown }).message === "string"
                    ? (payload as { message: string }).message
                    : "";
                streamError = messageText || "Streaming research gặp lỗi.";
              }
            },
          });
        } catch (streamCause) {
          streamError =
            streamCause instanceof Error
              ? streamCause.message
              : "Streaming research tạm gián đoạn.";
        }

        if (
          streamError &&
          currentJob.status !== "completed" &&
          currentJob.status !== "failed"
        ) {
          setLiveStatusNote(
            `${streamError} Đang tự động chuyển sang chế độ polling để giữ tiến trình.`
          );
        }

        let pollingRounds = 0;
        while (
          currentJob.status !== "completed" &&
          currentJob.status !== "failed" &&
          pollingRounds < 1200
        ) {
          pollingRounds += 1;
          await new Promise((resolve) => {
            window.setTimeout(resolve, RESEARCH_TIER2_JOB_POLL_MS);
          });
          currentJob = await fetchTier2JobWithRetry(job.job_id);
          applyLiveSnapshot(currentJob);
        }

        if (currentJob.status === "completed") {
          finalPayload =
            currentJob.result && typeof currentJob.result === "object"
              ? (currentJob.result as Record<string, unknown>)
              : null;
        } else if (currentJob.status === "failed") {
          throw new Error(currentJob.error ?? "Research job thất bại ở backend.");
        } else {
          throw new Error("Research job quá thời gian chờ. Vui lòng thử lại.");
        }

        const hasFinalResultObject = (value: unknown): value is Record<string, unknown> =>
          Boolean(value) && typeof value === "object";

        if (!hasFinalResultObject(finalPayload)) {
          let completionRefetchRound = 0;
          while (
            completionRefetchRound < JOB_COMPLETED_RESULT_REFETCH_ATTEMPTS &&
            !hasFinalResultObject(finalPayload)
          ) {
            completionRefetchRound += 1;
            await new Promise((resolve) =>
              window.setTimeout(resolve, JOB_COMPLETED_RESULT_REFETCH_MS)
            );
            currentJob = await fetchTier2JobWithRetry(job.job_id);
            applyLiveSnapshot(currentJob);
            if (hasFinalResultObject(currentJob.result)) {
              finalPayload = currentJob.result;
              break;
            }
          }
          if (!hasFinalResultObject(finalPayload)) {
            const progress = normalizeResearchTier2JobProgress(currentJob.progress);
            throw new Error(
              progress.statusNote || "Không nhận được kết quả cuối từ research job."
            );
          }
        }

        const normalized = normalizeResearchTier2(finalPayload);
        if (!normalized.answer && !normalized.citations.length) {
          throw new Error("Chưa có phản hồi chuyên sâu hợp lệ.");
        }
        if (liveFlowStages.length && !normalized.flowStages.length) {
          normalized.flowStages = liveFlowStages;
        }
        if (liveFlowEvents.length && !normalized.flowEvents.length) {
          normalized.flowEvents = liveFlowEvents;
        }
        nextResult = {
          tier: "tier2",
          ...normalized
        };
      }

      const localTurnId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const localTurn = createConversationItem(message, nextResult, { id: localTurnId });
      setConversationTurns((prev) => [...prev, localTurn]);

      let conversation = createConversationItem(message, nextResult);
      let targetConversationId = activeConversationId;

      try {
        if (targetConversationId && Number.isFinite(Number(targetConversationId)) && Number(targetConversationId) > 0) {
          const persisted = await appendResearchConversationMessage(
            targetConversationId,
            message,
            nextResult as unknown as Record<string, unknown>
          );
          conversation = createConversationItemFromPersisted(persisted);
          targetConversationId = conversation.id;
        } else {
          const persisted = await createResearchConversation(
            message,
            nextResult as unknown as Record<string, unknown>
          );
          conversation = createConversationItemFromPersisted(persisted);
          targetConversationId = conversation.id;
        }
      } catch (persistError) {
        const fallbackConversationId = targetConversationId ?? `local-${Date.now()}`;
        conversation = createConversationItem(
          message,
          nextResult,
          { id: fallbackConversationId, createdAt: Date.now() }
        );
        targetConversationId = fallbackConversationId;
        setError(
          persistError instanceof Error
            ? `Đã trả lời nhưng lưu hội thoại thất bại: ${persistError.message}`
            : "Đã trả lời nhưng lưu hội thoại thất bại."
        );
      }

      setHistory((prev) => [conversation, ...prev.filter((item) => item.id !== conversation.id)]);
      setActiveConversationId(targetConversationId);
      setQuery("");
      setLiveJobId(null);
      setLiveStatusNote("");
      setLiveReasoningNotes([]);

      if (targetConversationId && Number.isFinite(Number(targetConversationId)) && Number(targetConversationId) > 0) {
        void loadConversationTurns(String(targetConversationId), conversation);
      } else {
        setConversationTurns((prev) => prev);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xử lý câu hỏi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyAnswer = async (rawContent?: string) => {
    const content = (rawContent ?? latestAnswerText).trim();
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopyMessage("Đã copy câu trả lời.");
    } catch {
      setCopyMessage("Không thể copy tự động trên trình duyệt này.");
    }
    window.setTimeout(() => setCopyMessage(""), 2000);
  };

  const renderConversationList = (mobile = false) => (
    <>
      {!mobile ? (
        <button
          type="button"
          onClick={createNewConversation}
          className="chrome-nav-link mt-3 inline-flex min-h-[42px] w-full items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-semibold text-[var(--text-primary)]"
        >
          + Chat mới
        </button>
      ) : null}

      {!history.length ? (
        <p className="mt-3 text-xs leading-6 text-[var(--text-secondary)]">
          Chưa có lịch sử hội thoại.
        </p>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {history.slice(0, mobile ? 8 : 20).map((item) => {
            const active = item.id === activeConversationId;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelectConversation(item)}
                  className={[
                    "w-full rounded-xl border px-3 py-2 text-left transition",
                    active
                      ? "border-cyan-300/70 bg-cyan-500/10"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                  ].join(" ")}
                >
                  <p className="line-clamp-2 text-sm font-semibold text-[var(--text-primary)]">{item.query}</p>
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                    {formatHistoryTime(item.createdAt)} · {item.result.tier.toUpperCase()}
                  </p>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );

  const isTier2Running = isSubmitting && selectedTier === "tier2";

  const displayedFlowStages = useMemo(() => {
    if (isTier2Running && liveFlowStages.length) {
      return liveFlowStages;
    }
    return lastResult?.tier === "tier2" ? lastResult.flowStages : [];
  }, [isTier2Running, liveFlowStages, lastResult]);

  const displayedFlowEvents = useMemo(() => {
    if (isTier2Running && liveFlowEvents.length) {
      return liveFlowEvents;
    }
    return lastResult?.tier === "tier2" ? lastResult.flowEvents : [];
  }, [isTier2Running, liveFlowEvents, lastResult]);

  const displayedFlowMode = useMemo(() => {
    if (isTier2Running && displayedFlowEvents.length) return "flow-events";
    if (isTier2Running && displayedFlowStages.length) return "metadata-stages";
    if (isTier2Running) return "server-await";
    return flowMode;
  }, [displayedFlowEvents.length, displayedFlowStages.length, flowMode, isTier2Running]) as
    | "idle"
    | "flow-events"
    | "metadata-stages"
    | "local-fallback"
    | "server-await";

  const liveReasoningPreview = useMemo(
    () => (isTier2Running ? liveReasoningNotes.slice(-20) : []),
    [isTier2Running, liveReasoningNotes]
  );
  const liveEventPreview = useMemo(
    () => (isTier2Running ? displayedFlowEvents.slice(-24).reverse() : []),
    [displayedFlowEvents, isTier2Running]
  );

  return (
    <PageShell
      title="CLARA Chat"
      description="Mở ứng dụng là chat ngay. Luồng chuyên sâu vẫn có sẵn nhưng nằm ở lớp mở rộng phía dưới."
    >
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="chrome-panel hidden rounded-[1.35rem] p-4 lg:block">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Conversations
            </h3>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
              {history.length}
            </span>
          </div>

          {renderConversationList()}

          <div className="mt-4 border-t border-[color:var(--shell-border)] pt-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Chuyên sâu
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {ADVANCED_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="inline-flex min-h-[34px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </aside>

        <section className="space-y-4">
          <section className="chrome-panel rounded-[1.4rem] p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2.5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                  Chat-first workspace
                </p>
                <h2 className="mt-1.5 text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
                  Hôm nay bạn muốn hỏi gì?
                </h2>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex min-h-[36px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]">
                  Vai trò: {role}
                </span>

                <fieldset className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
                  <legend className="sr-only">Chọn tier</legend>
                  <button
                    type="button"
                    onClick={() => setSelectedTier("tier1")}
                    disabled={isSubmitting}
                    className={[
                      "rounded-full px-3 py-1 text-xs font-semibold transition",
                      selectedTier === "tier1"
                        ? "bg-[var(--text-primary)] text-[var(--surface-panel)]"
                        : "text-[var(--text-secondary)]"
                    ].join(" ")}
                  >
                    Quick
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedTier("tier2")}
                    disabled={isSubmitting}
                    className={[
                      "rounded-full px-3 py-1 text-xs font-semibold transition",
                      selectedTier === "tier2"
                        ? "bg-[var(--text-primary)] text-[var(--surface-panel)]"
                        : "text-[var(--text-secondary)]"
                    ].join(" ")}
                  >
                    Research
                  </button>
                </fieldset>

                {selectedTier === "tier2" ? (
                  <fieldset className="inline-flex rounded-full border border-cyan-300/70 bg-cyan-500/10 p-1">
                    <legend className="sr-only">Chọn mode research</legend>
                    {RESEARCH_MODE_OPTIONS.map((mode) => (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => setSelectedResearchMode(mode.id)}
                        disabled={isSubmitting}
                        className={[
                          "rounded-full px-3 py-1 text-xs font-semibold transition",
                          selectedResearchMode === mode.id
                            ? "bg-cyan-500 text-white"
                            : "text-cyan-700 dark:text-cyan-200"
                        ].join(" ")}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </fieldset>
                ) : null}
              </div>
            </div>
          </section>

          <details className="chrome-panel rounded-[1.3rem] p-3 lg:hidden">
            <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
              Lịch sử hội thoại ({history.length})
            </summary>
            {renderConversationList(true)}
            <div className="mt-3 flex flex-wrap gap-2">
              {ADVANCED_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="inline-flex min-h-[34px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </details>

          <section className="chrome-panel flex min-h-[66vh] max-h-[80vh] flex-col overflow-hidden rounded-[1.35rem] p-4 sm:p-5 lg:p-6">
            <div ref={conversationScrollRef} className="flex-1 space-y-4 overflow-y-auto pr-1 pb-4">
              {isLoadingConversation && !conversationTurns.length ? (
                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-4 text-sm text-[var(--text-secondary)]">
                  Đang tải hội thoại...
                </article>
              ) : null}
              {!lastResult && !isLoadingConversation ? (
                <article className="rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-6 text-sm leading-7 text-[var(--text-secondary)]">
                  Bạn chưa có phiên trả lời nào trong lượt này. Nhập câu hỏi bên dưới để bắt đầu.
                </article>
              ) : (
                <>
                  {isLoadingConversation && conversationTurns.length ? (
                    <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-4 text-sm text-[var(--text-secondary)]">
                      Đang tải hội thoại...
                    </article>
                  ) : null}
                  {conversationTurns.map((turn) => {
                    const result = turn.result;
                    const answerText = result.answer || "";
                    const answerCitations = result.tier === "tier2" ? result.citations : [];
                    const runtimeMeta =
                      result.tier === "tier2" ? buildTier2MetaSummary(result) : null;
                    const tierLabel =
                      result.tier === "tier2"
                        ? `Research ${toResearchModeLabel(result.researchMode)}`
                        : "Quick";

                    return (
                      <div key={turn.id} className="space-y-3">
                        <div className="flex justify-end">
                          <article className="max-w-[90%] rounded-2xl border border-cyan-300/60 bg-cyan-500/10 px-4 py-3 text-sm leading-7 text-[var(--text-primary)]">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300">
                              Bạn
                            </p>
                            <p className="mt-1.5 whitespace-pre-wrap">{turn.query}</p>
                          </article>
                        </div>

                        <div className="flex justify-start">
                          <article className="w-full max-w-[96%] rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-4 sm:px-5">
                            <div className="mb-3 flex flex-wrap items-center gap-2">
                              <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                                CLARA
                              </span>
                              <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                                {tierLabel}
                              </span>
                              {result.tier === "tier2" && typeof result.fallbackUsed === "boolean" ? (
                                <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                                  path: {result.fallbackUsed ? "fallback" : "rag"}
                                </span>
                              ) : null}
                              <button
                                type="button"
                                onClick={() => void copyAnswer(answerText)}
                                className="ml-auto inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                              >
                                Copy
                              </button>
                            </div>

                            <MarkdownAnswer answer={answerText} citations={answerCitations} />

                            {result.tier === "tier2" && runtimeMeta?.hasData ? (
                              <section className="mt-3 rounded-xl border border-cyan-200/70 bg-cyan-50/60 px-3 py-2.5 text-xs text-cyan-900 dark:border-cyan-900/60 dark:bg-cyan-950/25 dark:text-cyan-200">
                                <p className="font-semibold uppercase tracking-[0.1em]">
                                  Runtime metadata
                                </p>
                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                  <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                                    query_plan: {runtimeMeta.primaryQuery ? "yes" : "n/a"}
                                  </span>
                                  <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                                    subqueries: {runtimeMeta.subqueryCount}
                                  </span>
                                  <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                                    connectors: {runtimeMeta.connectorCount}
                                  </span>
                                  <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                                    source_attempts: {runtimeMeta.attemptCount}
                                  </span>
                                  <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                                    attempt_failed: {runtimeMeta.failedAttemptCount}
                                  </span>
                                  <span className="rounded-full border border-rose-300/70 bg-rose-50 px-2 py-0.5 text-rose-700 dark:border-rose-800/80 dark:bg-rose-950/35 dark:text-rose-300">
                                    errors: {runtimeMeta.errorCount}
                                  </span>
                                </div>
                                {runtimeMeta.primaryQuery ? (
                                  <p className="mt-1.5 break-words">
                                    query_plan: <span className="font-medium">{runtimeMeta.primaryQuery}</span>
                                  </p>
                                ) : null}
                                {runtimeMeta.topErrors.length ? (
                                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                                    {runtimeMeta.topErrors.map((entry, index) => (
                                      <li key={`${turn.id}-meta-error-${index}`}>{entry}</li>
                                    ))}
                                  </ul>
                                ) : null}
                              </section>
                            ) : null}

                            {result.tier === "tier1" && result.debug ? (
                              <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                                role={result.debug.role ?? "n/a"} · intent={result.debug.intent ?? "n/a"} · confidence=
                                {typeof result.debug.confidence === "number"
                                  ? result.debug.confidence.toFixed(2)
                                  : "n/a"}
                              </div>
                            ) : null}
                          </article>
                        </div>
                      </div>
                    );
                  })}

                  {copyMessage ? (
                    <p className="text-xs text-cyan-700 dark:text-cyan-300">{copyMessage}</p>
                  ) : null}
                </>
              )}
            </div>

            <div className="sticky bottom-0 z-10 mt-2 -mx-4 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 px-4 pt-4 backdrop-blur sm:-mx-5 sm:px-5 lg:-mx-6 lg:px-6">
              <div className="mb-3 flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setQuery(prompt)}
                    className="inline-flex min-h-[34px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs font-medium text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              <form onSubmit={onSubmit} className="space-y-3">
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  disabled={isSubmitting}
                  placeholder="Nhập câu hỏi y khoa..."
                  className="min-h-[120px] w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm leading-7 text-[var(--text-primary)] outline-none transition focus:border-[color:var(--shell-border-strong)]"
                />

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-[var(--text-muted)]">
                    {selectedTier === "tier2"
                      ? `Research mode: ${toResearchModeLabel(selectedResearchMode)} · hiển thị query plan/source attempts/errors + timeline.`
                      : "Quick mode: phản hồi nhanh với guard an toàn."}
                  </p>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={createNewConversation}
                      disabled={isSubmitting}
                      className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
                    >
                      Chat mới
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting || !query.trim()}
                      className="inline-flex min-h-[46px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      {isSubmitting ? "Đang xử lý..." : "Gửi"}
                    </button>
                  </div>
                </div>
              </form>

              {error ? <p className="mt-3 text-sm text-rose-500">{error}</p> : null}
              {isTier2Running ? (
                <section className="mt-3 rounded-xl border border-cyan-300/60 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-900 dark:text-cyan-200">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">
                      {liveStatusNote || "Đang chạy research nhiều bước trên backend, trạng thái sẽ cập nhật live."}
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowLiveResearchTrace((prev) => !prev)}
                      className="inline-flex min-h-[30px] items-center rounded-md border border-cyan-400/60 bg-white/70 px-2.5 text-[11px] font-semibold text-cyan-800 dark:bg-cyan-950/35 dark:text-cyan-100"
                    >
                      {showLiveResearchTrace ? "Ẩn luồng live" : "Hiện luồng live"}
                    </button>
                  </div>

                  <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                    {liveJobId ? (
                      <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                        job_id: {liveJobId}
                      </span>
                    ) : null}
                    <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                      reasoning: {liveReasoningNotes.length}
                    </span>
                    <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                      events: {displayedFlowEvents.length}
                    </span>
                    <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5">
                      stages: {displayedFlowStages.length}
                    </span>
                  </div>

                  {showLiveResearchTrace ? (
                    <div className="mt-2 grid gap-2 lg:grid-cols-2">
                      <div className="rounded-lg border border-cyan-300/60 bg-white/80 px-2.5 py-2 dark:bg-cyan-950/20">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.1em]">Reasoning feed</p>
                        {liveReasoningPreview.length ? (
                          <ol className="mt-1.5 max-h-36 space-y-1 overflow-y-auto pr-1 text-[11px]">
                            {liveReasoningPreview.map((note, index) => (
                              <li key={`${index}-${note.slice(0, 24)}`} className="rounded-md border border-cyan-200/70 bg-cyan-50/70 px-2 py-1 dark:border-cyan-900/80 dark:bg-cyan-950/35">
                                {note}
                              </li>
                            ))}
                          </ol>
                        ) : (
                          <p className="mt-1.5 text-[11px] opacity-75">Chưa có reasoning note từ backend.</p>
                        )}
                      </div>

                      <div className="rounded-lg border border-cyan-300/60 bg-white/80 px-2.5 py-2 dark:bg-cyan-950/20">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.1em]">Flow events</p>
                        {liveEventPreview.length ? (
                          <ul className="mt-1.5 max-h-36 space-y-1 overflow-y-auto pr-1 text-[11px]">
                            {liveEventPreview.map((event) => {
                              const preview = summarizeLiveEvent(event);
                              return (
                                <li key={event.id} className="rounded-md border border-cyan-200/70 bg-cyan-50/70 px-2 py-1 dark:border-cyan-900/80 dark:bg-cyan-950/35">
                                  <div className="flex flex-wrap items-center gap-1">
                                    <span className="font-semibold">{event.label}</span>
                                    <span className="rounded-full border border-cyan-300/70 px-1.5 py-0 text-[10px] uppercase">
                                      {event.status}
                                    </span>
                                    {event.timestamp ? (
                                      <span className="opacity-80">{formatLiveEventTime(event.timestamp)}</span>
                                    ) : null}
                                  </div>
                                  {event.detail ? <p className="mt-0.5 opacity-90">{event.detail}</p> : null}
                                  {preview ? <p className="mt-0.5 opacity-75">{preview}</p> : null}
                                </li>
                              );
                            })}
                          </ul>
                        ) : (
                          <p className="mt-1.5 text-[11px] opacity-75">Chưa có flow event realtime.</p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </section>
              ) : null}
            </div>
          </section>

          <section className="chrome-panel rounded-[1.35rem] p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                Chuyên sâu
              </p>
              <button
                type="button"
                onClick={() => setShowAdvanced((prev) => !prev)}
                className="inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
              >
                {showAdvanced ? "Ẩn panel" : "Mở panel"}
              </button>
            </div>

            {showAdvanced ? (
              <div className="mt-3 grid gap-3 xl:grid-cols-2">
                <FlowTimelinePanel
                  stages={displayedFlowStages}
                  events={displayedFlowEvents}
                  mode={displayedFlowMode}
                  isProcessing={isTier2Running}
                />

                <TelemetryDetailsPanel
                  telemetry={lastResult?.tier === "tier2" ? lastResult.telemetry : EMPTY_TELEMETRY}
                  isProcessing={isTier2Running}
                />
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                Flow timeline/telemetry theo các node mới (query canonicalizer, decomposition, retrieval orchestrator...) được giữ ở chế độ mở rộng.
              </p>
            )}
          </section>
        </section>
      </div>
    </PageShell>
  );
}
  const fetchTier2JobWithRetry = async (jobId: string) => {
    let lastError: unknown = null;
    for (let attempt = 1; attempt <= JOB_FETCH_RETRY_ATTEMPTS; attempt += 1) {
      try {
        return await getResearchTier2Job(jobId);
      } catch (error) {
        lastError = error;
        if (attempt < JOB_FETCH_RETRY_ATTEMPTS) {
          await new Promise((resolve) =>
            window.setTimeout(resolve, JOB_FETCH_RETRY_BACKOFF_MS * attempt)
          );
          continue;
        }
      }
    }
    throw lastError instanceof Error ? lastError : new Error("Không thể tải trạng thái research job.");
  };
