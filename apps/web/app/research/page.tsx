"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
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
  createResearchTier2Job,
  createResearchConversation,
  getResearchTier2Job,
  listResearchConversations,
  normalizeResearchTier2JobProgress,
  normalizeResearchTier2,
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

const EMPTY_TELEMETRY = {
  keywords: [],
  searchPlan: { keywords: [], subqueries: [], connectors: [] },
  sourceAttempts: [],
  indexSummary: {},
  crawlSummary: { domains: [] },
  docs: [],
  scores: [],
  sourceReasoning: [],
  errors: []
};

export default function ResearchPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [selectedTier, setSelectedTier] = useState<ResearchTier>("tier1");
  const [selectedResearchMode, setSelectedResearchMode] = useState<ResearchExecutionMode>("fast");
  const [query, setQuery] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [liveFlowStages, setLiveFlowStages] = useState<ResearchFlowStage[]>([]);
  const [liveFlowEvents, setLiveFlowEvents] = useState<ResearchFlowEvent[]>([]);
  const [liveReasoningNotes, setLiveReasoningNotes] = useState<string[]>([]);
  const [liveStatusNote, setLiveStatusNote] = useState("");
  const [liveJobId, setLiveJobId] = useState<string | null>(null);

  const [history, setHistory] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ResearchResult | null>(null);

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
        setLastQuestion(firstItem.query);
        setLastResult(firstItem.result);
        setSelectedTier(firstItem.result.tier);
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

  const activeConversation = useMemo(
    () => history.find((item) => item.id === activeConversationId) ?? null,
    [history, activeConversationId]
  );

  const flowMode = useMemo(
    () => (lastResult?.tier === "tier2" ? resolveFlowModeFromResult(lastResult) : "idle"),
    [lastResult]
  );

  const displayedQuestion = activeConversation?.query ?? lastQuestion;
  const answerText =
    lastResult?.tier === "tier2"
      ? lastResult.answer || "Chưa có nội dung trả lời."
      : lastResult?.answer || "Chưa có nội dung trả lời.";
  const answerCitations = lastResult?.tier === "tier2" ? lastResult.citations : [];

  const createNewConversation = () => {
    setActiveConversationId(null);
    setLastQuestion("");
    setLastResult(null);
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
    setLastQuestion(item.query);
    setLastResult(item.result);
    setSelectedTier(item.result.tier);
    setError("");
    setLiveFlowStages([]);
    setLiveFlowEvents([]);
    setLiveReasoningNotes([]);
    setLiveStatusNote("");
    setLiveJobId(null);
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
        let pollingRounds = 0;
        while (pollingRounds < 240) {
          pollingRounds += 1;
          const progress = normalizeResearchTier2JobProgress(currentJob.progress);
          setLiveFlowStages(progress.flowStages);
          setLiveFlowEvents(progress.flowEvents);
          setLiveReasoningNotes(progress.reasoningNotes);
          setLiveStatusNote(progress.statusNote ?? "");

          if (currentJob.status === "completed") {
            finalPayload =
              currentJob.result && typeof currentJob.result === "object"
                ? (currentJob.result as Record<string, unknown>)
                : {};
            break;
          }
          if (currentJob.status === "failed") {
            throw new Error(currentJob.error ?? "Research job thất bại ở backend.");
          }

          await new Promise((resolve) => {
            window.setTimeout(resolve, RESEARCH_TIER2_JOB_POLL_MS);
          });
          currentJob = await getResearchTier2Job(job.job_id);
        }

        if (!finalPayload) {
          throw new Error("Research job quá thời gian chờ. Vui lòng thử lại.");
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

      setLastQuestion(message);
      setLastResult(nextResult);

      let conversation = createConversationItem(message, nextResult);
      try {
        const persisted = await createResearchConversation(
          message,
          nextResult as unknown as Record<string, unknown>
        );
        conversation = createConversationItemFromPersisted(persisted);
      } catch (persistError) {
        setError(
          persistError instanceof Error
            ? `Đã trả lời nhưng lưu hội thoại thất bại: ${persistError.message}`
            : "Đã trả lời nhưng lưu hội thoại thất bại."
        );
      }

      setHistory((prev) => [conversation, ...prev.filter((item) => item.id !== conversation.id)]);
      setActiveConversationId(conversation.id);
      setQuery("");
      setLiveJobId(null);
      setLiveStatusNote("");
      setLiveReasoningNotes([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xử lý câu hỏi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyAnswer = async () => {
    const content = answerText.trim();
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

  const displayedFlowStages = useMemo(() => {
    if (isSubmitting && selectedTier === "tier2" && liveFlowStages.length) {
      return liveFlowStages;
    }
    return lastResult?.tier === "tier2" ? lastResult.flowStages : [];
  }, [isSubmitting, selectedTier, liveFlowStages, lastResult]);

  const displayedFlowEvents = useMemo(() => {
    if (isSubmitting && selectedTier === "tier2" && liveFlowEvents.length) {
      return liveFlowEvents;
    }
    return lastResult?.tier === "tier2" ? lastResult.flowEvents : [];
  }, [isSubmitting, selectedTier, liveFlowEvents, lastResult]);

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
                    <button
                      type="button"
                      onClick={() => setSelectedResearchMode("fast")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-semibold transition",
                        selectedResearchMode === "fast"
                          ? "bg-cyan-500 text-white"
                          : "text-cyan-700 dark:text-cyan-200"
                      ].join(" ")}
                    >
                      Fast
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedResearchMode("deep")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-semibold transition",
                        selectedResearchMode === "deep"
                          ? "bg-cyan-500 text-white"
                          : "text-cyan-700 dark:text-cyan-200"
                      ].join(" ")}
                    >
                      Deep
                    </button>
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

          <section className="chrome-panel flex min-h-[66vh] flex-col rounded-[1.35rem] p-4 sm:p-5 lg:p-6">
            <div className="flex-1 space-y-4 overflow-y-auto pr-1">
              {!lastResult ? (
                <article className="rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-6 text-sm leading-7 text-[var(--text-secondary)]">
                  Bạn chưa có phiên trả lời nào trong lượt này. Nhập câu hỏi bên dưới để bắt đầu.
                </article>
              ) : (
                <>
                  <div className="flex justify-end">
                    <article className="max-w-[90%] rounded-2xl border border-cyan-300/60 bg-cyan-500/10 px-4 py-3 text-sm leading-7 text-[var(--text-primary)]">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300">
                        Bạn
                      </p>
                      <p className="mt-1.5 whitespace-pre-wrap">{displayedQuestion}</p>
                    </article>
                  </div>

                  <div className="flex justify-start">
                    <article className="w-full max-w-[96%] rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-4 sm:px-5">
                      <div className="mb-3 flex flex-wrap items-center gap-2">
                        <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                          CLARA
                        </span>
                        <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                          {lastResult.tier === "tier2" ? `Research ${lastResult.researchMode?.toUpperCase() ?? ""}` : "Quick"}
                        </span>
                        {lastResult.tier === "tier2" && typeof lastResult.fallbackUsed === "boolean" ? (
                          <span className="inline-flex min-h-[30px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                            path: {lastResult.fallbackUsed ? "fallback" : "rag"}
                          </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void copyAnswer()}
                          className="ml-auto inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                        >
                          Copy
                        </button>
                      </div>

                      <MarkdownAnswer answer={answerText} citations={answerCitations} />

                      {lastResult.tier === "tier1" && lastResult.debug ? (
                        <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                          role={lastResult.debug.role ?? "n/a"} · intent={lastResult.debug.intent ?? "n/a"} · confidence=
                          {typeof lastResult.debug.confidence === "number"
                            ? lastResult.debug.confidence.toFixed(2)
                            : "n/a"}
                        </div>
                      ) : null}

                      {copyMessage ? (
                        <p className="mt-2 text-xs text-cyan-700 dark:text-cyan-300">{copyMessage}</p>
                      ) : null}
                    </article>
                  </div>
                </>
              )}
            </div>

            <div className="mt-4 border-t border-[color:var(--shell-border)] pt-4">
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
                      ? `Research mode: ${selectedResearchMode.toUpperCase()} · trả lời kèm nguồn và timeline.`
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
              {isSubmitting && selectedTier === "tier2" ? (
                <div className="mt-3 rounded-xl border border-cyan-300/60 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-800 dark:text-cyan-200">
                  <p>
                    {liveStatusNote || "Đang chạy research nhiều bước trên backend, trạng thái sẽ cập nhật live."}
                  </p>
                  {liveJobId ? <p className="mt-1 opacity-80">job_id: {liveJobId}</p> : null}
                  {liveReasoningNotes.length ? (
                    <ul className="mt-1 list-disc space-y-0.5 pl-4">
                      {liveReasoningNotes.slice(-4).map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
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
                  mode={flowMode}
                  isProcessing={isSubmitting && selectedTier === "tier2"}
                />

                <TelemetryDetailsPanel
                  telemetry={lastResult?.tier === "tier2" ? lastResult.telemetry : EMPTY_TELEMETRY}
                  isProcessing={isSubmitting && selectedTier === "tier2"}
                />
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                Flow timeline, telemetry và các route Deepdive/Analyze/Citations/Details được giữ lại ở chế độ mở rộng.
              </p>
            )}
          </section>
        </section>
      </div>
    </PageShell>
  );
}
