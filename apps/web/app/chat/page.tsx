"use client";

import Link from "next/link";
import { FormEvent, UIEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  createConversationItem,
  createConversationItemFromPersisted,
} from "@/components/research/lib/research-page-helpers";
import { ConversationItem, ResearchResult } from "@/components/research/lib/research-page-types";
import ChatComposer from "@/components/chat-workspace/chat-composer";
import ChatTurn from "@/components/chat-workspace/chat-turn";
import PageShell from "@/components/ui/page-shell";
import { clearTokens, getRole, type UserRole } from "@/lib/auth-store";
import api from "@/lib/http-client";
import {
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
  type ResearchTier2Result,
  appendResearchConversationMessage,
  createResearchConversation,
  listResearchConversations,
  listResearchConversationMessages,
  normalizeResearchTier2,
  normalizeResearchTier2JobProgress,
} from "@/lib/research";
import { executeResearchTier2Job } from "@/lib/research-tier2-job-runner";
import {
  WorkspaceConversationShare,
  WorkspaceConversationShareListItem,
  WorkspaceConversationItem,
  WorkspaceFolder,
  WorkspaceNote,
  WorkspaceSearchResponse,
  WorkspaceSuggestion,
  WorkspaceSummary,
  bulkUpdateWorkspaceConversationMeta,
  createWorkspaceConversationShare,
  createWorkspaceFolder,
  createWorkspaceNote,
  deleteWorkspaceConversation,
  deleteWorkspaceFolder,
  deleteWorkspaceNote,
  getWorkspaceConversationShare,
  getWorkspaceSummary,
  listWorkspaceConversations,
  listWorkspaceFolders,
  listWorkspaceNotes,
  listWorkspaceShares,
  exportWorkspaceConversation,
  exportWorkspaceDocxFromMarkdown,
  listWorkspaceSuggestions,
  revokeWorkspaceConversationShare,
  searchWorkspace,
  updateWorkspaceConversation,
  updateWorkspaceConversationMeta,
  updateWorkspaceFolder,
  updateWorkspaceNote,
} from "@/lib/workspace";

const QUICK_PROMPTS: string[] = [
  "Tóm tắt tương tác thuốc chính của metformin",
  "So sánh ưu nhược điểm DASH và Địa Trung Hải",
  "Lập checklist theo dõi khi dùng warfarin",
  "Gợi ý câu hỏi cần hỏi bác sĩ cho bệnh nhân tăng huyết áp",
];

const LOCAL_WORKSPACE_MAX_ITEMS = 80;

type WorkspaceLeftView = "all" | "chat" | "notes" | "discover" | "shares";
type WorkspaceCommandAction = {
  id: string;
  label: string;
  hint?: string;
  keywords: string[];
  disabled?: boolean;
  run: () => void;
};
type ConversationVirtualItem = {
  key: string;
  item: WorkspaceConversationItem;
  dayLabel: string | null;
};

const WORKSPACE_LEFT_VIEW_OPTIONS: Array<{
  id: WorkspaceLeftView;
  label: string;
  title: string;
}> = [
  { id: "all", label: "AL", title: "All" },
  { id: "chat", label: "CH", title: "Chat" },
  { id: "notes", label: "NT", title: "Notes" },
  { id: "discover", label: "DS", title: "Discover" },
  { id: "shares", label: "SH", title: "Shares" },
];

function parsePromptText(value: string | null): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function parseTagsInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .slice(0, 20);
}

function buildConversationPreview(item: WorkspaceConversationItem): string {
  const candidate = item.title || item.preview || "Conversation";
  return candidate.length > 80 ? `${candidate.slice(0, 80)}...` : candidate;
}

function toConversationTimestamp(item: WorkspaceConversationItem): number {
  const lastTs = Date.parse(item.last_message_at || "");
  if (Number.isFinite(lastTs) && lastTs > 0) return lastTs;
  const createdTs = Date.parse(item.created_at || "");
  if (Number.isFinite(createdTs) && createdTs > 0) return createdTs;
  return 0;
}

function toDayKey(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) return "Unknown";
  const date = new Date(ts);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfThatDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const dayDiff = Math.floor((startOfToday - startOfThatDay) / (24 * 60 * 60 * 1000));
  if (dayDiff === 0) return "Hôm nay";
  if (dayDiff === 1) return "Hôm qua";
  if (dayDiff <= 7) return "7 ngày qua";
  return "Cũ hơn";
}

function latestAnswerFromTurn(turn: ConversationItem | null): string {
  if (!turn) return "";
  const result = turn.result;
  return result.answer || "";
}

function asConversationId(value: number | null): number | null {
  if (!Number.isFinite(value) || value === null || value <= 0) return null;
  return Math.trunc(value);
}

function isNotFoundLikeError(cause: unknown): boolean {
  if (!(cause instanceof Error)) return false;
  const message = cause.message.toLowerCase();
  return (
    message.includes("not found") ||
    message.includes("404") ||
    message.includes("không tồn tại")
  );
}

function buildConversationMarkdownExport(
  title: string,
  turns: ConversationItem[]
): string {
  const lines: string[] = [
    `# ${title || "CLARA Conversation Export"}`,
    "",
    `- Exported at: \`${new Date().toISOString()}\``,
    "",
  ];

  for (const turn of turns) {
    const query = (turn.query || "").trim();
    const answer = (turn.result?.answer || "").trim();
    lines.push("## User");
    lines.push("");
    lines.push(query || "_(empty)_");
    lines.push("");
    lines.push("## CLARA");
    lines.push("");
    lines.push(answer || "_(empty)_");
    lines.push("");
    lines.push("---");
    lines.push("");
  }

  return lines.join("\n").trim();
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

function isEditableElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

type SourceIntelStatus = "active" | "connecting" | "error";

function normalizeSourceStatus(status?: string, hasError?: boolean): SourceIntelStatus {
  if (hasError) return "error";
  const text = (status ?? "").trim().toLowerCase();
  if (!text) return "active";
  if (
    text.includes("fail") ||
    text.includes("error") ||
    text.includes("timeout") ||
    text.includes("denied") ||
    text.includes("rejected")
  ) {
    return "error";
  }
  if (
    text.includes("pending") ||
    text.includes("queue") ||
    text.includes("running") ||
    text.includes("connect") ||
    text.includes("in_progress")
  ) {
    return "connecting";
  }
  return "active";
}

function isVietnamMedicalSource(name: string): boolean {
  const normalized = name.toLowerCase();
  return (
    normalized.includes("dav") ||
    normalized.includes("kcb") ||
    normalized.includes(".vn") ||
    normalized.includes("vietnam")
  );
}

type LogicFlowNodeStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "warning"
  | "failed"
  | "skipped";

type LogicFlowNode = {
  id: string;
  label: string;
  status: LogicFlowNodeStatus;
  detail?: string;
};

const LOGIC_FLOW_BLUEPRINT: Array<{
  id: LogicFlowNode["id"];
  label: LogicFlowNode["label"];
  stageIds: string[];
}> = [
  {
    id: "semantic_parsing",
    label: "Semantic Parsing",
    stageIds: [
      "input_gateway",
      "session_guard",
      "safety_ingress",
      "legal_guard",
      "role_router",
      "intent_router",
      "query_canonicalizer",
      "query_decomposition",
      "planner",
      "llm_query_planner",
      "keyword_filter",
      "query_plan",
    ],
  },
  {
    id: "evidence_retrieval",
    label: "Evidence Retrieval",
    stageIds: [
      "retrieval_orchestrator",
      "retrieval_internal",
      "retrieval_scientific",
      "retrieval_web",
      "retrieval_file",
      "evidence_index",
      "contradiction_miner",
      "collect_evidence",
      "source_attempts",
      "evidence_review",
      "deep_research",
      "deep_beta_consensus",
      "deep_beta_reasoning",
    ],
  },
  {
    id: "synthesis_engine",
    label: "Synthesis Engine",
    stageIds: [
      "synthesis",
      "answer_synthesis",
      "llm_generation",
      "llm_generation_retry",
      "deep_report_synthesis",
      "deep_beta_chain_synthesis",
      "deep_beta_report_synthesis",
      "verification",
      "verification_matrix",
      "citation_selection",
      "responder",
      "final_response",
    ],
  },
];

function normalizeLogicFlowStatus(status?: string): LogicFlowNodeStatus {
  const text = (status ?? "").trim().toLowerCase();
  if (!text) return "pending";
  if (
    text.includes("failed") ||
    text.includes("error") ||
    text.includes("deny") ||
    text.includes("reject") ||
    text.includes("timeout")
  ) {
    return "failed";
  }
  if (text.includes("warning") || text.includes("warn") || text.includes("degraded")) {
    return "warning";
  }
  if (
    text.includes("running") ||
    text.includes("in_progress") ||
    text.includes("active") ||
    text.includes("processing") ||
    text.includes("started") ||
    text.includes("streaming")
  ) {
    return "in_progress";
  }
  if (
    text.includes("completed") ||
    text.includes("complete") ||
    text.includes("done") ||
    text.includes("success") ||
    text.includes("verified") ||
    text.includes("pass") ||
    text.includes("allow")
  ) {
    return "completed";
  }
  if (text.includes("skip") || text.includes("skipped") || text.includes("cancel")) {
    return "skipped";
  }
  return "pending";
}

function pickLogicFlowStatus(statuses: LogicFlowNodeStatus[]): LogicFlowNodeStatus {
  if (!statuses.length) return "pending";
  if (statuses.includes("failed")) return "failed";
  if (statuses.includes("in_progress")) return "in_progress";
  if (statuses.includes("warning")) return "warning";
  if (statuses.includes("completed")) return "completed";
  if (statuses.includes("skipped")) return "skipped";
  return "pending";
}

function buildLogicFlowNodes(result: ResearchTier2Result | null): LogicFlowNode[] {
  const flowStages = result?.flowStages ?? [];
  const normalizedStages = flowStages.map((stage) => ({
    ...stage,
    normalizedId: stage.id.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_"),
    normalizedStatus: normalizeLogicFlowStatus(stage.status),
  }));

  const answerText = (result?.answer ?? "").trim();
  const hasAnswer = answerText.length > 0;
  const keywordCount = result?.telemetry.keywords.length ?? 0;
  const sourceAttemptCount = result?.telemetry.sourceAttempts.length ?? 0;
  const docCount = result?.telemetry.docs.length ?? 0;
  const citationCount = result?.citations.length ?? 0;
  const telemetryErrorCount = result?.telemetry.errors.length ?? 0;

  const fallbackStatusForNode = (nodeId: LogicFlowNode["id"]): LogicFlowNodeStatus => {
    if (!result) return "pending";

    if (nodeId === "semantic_parsing") {
      if (keywordCount > 0 || result.steps.length > 0 || hasAnswer) return "completed";
      return "pending";
    }

    if (nodeId === "evidence_retrieval") {
      if (docCount > 0 || citationCount > 0) return telemetryErrorCount > 0 ? "warning" : "completed";
      if (sourceAttemptCount > 0) return "in_progress";
      if (telemetryErrorCount > 0) return "failed";
      return hasAnswer ? "completed" : "pending";
    }

    if (nodeId === "synthesis_engine") {
      if (hasAnswer) return "completed";
      if (docCount > 0 || citationCount > 0) return "in_progress";
      return "pending";
    }

    return "pending";
  };

  const fallbackDetailForNode = (nodeId: LogicFlowNode["id"]): string | undefined => {
    if (!result) return undefined;
    if (nodeId === "semantic_parsing" && keywordCount > 0) {
      return `keyword filter: ${keywordCount} terms`;
    }
    if (nodeId === "evidence_retrieval" && (docCount > 0 || sourceAttemptCount > 0)) {
      return `${docCount} docs · ${sourceAttemptCount} source attempts`;
    }
    if (nodeId === "synthesis_engine" && hasAnswer) {
      return "Answer generated";
    }
    return undefined;
  };

  return LOGIC_FLOW_BLUEPRINT.map((node) => {
    const stageIdSet = new Set(node.stageIds);
    const matchedStages = normalizedStages.filter((stage) => stageIdSet.has(stage.normalizedId));
    const matchedStatuses = matchedStages.map((stage) => stage.normalizedStatus);
    const status = matchedStatuses.length
      ? pickLogicFlowStatus(matchedStatuses)
      : fallbackStatusForNode(node.id);
    const detail =
      matchedStages
        .slice()
        .reverse()
        .find((stage) => stage.detail)?.detail ?? fallbackDetailForNode(node.id);
    return {
      id: node.id,
      label: node.label,
      status,
      detail,
    };
  });
}

function normalizeConfidenceRatio(value: number | undefined): number | undefined {
  if (value === undefined || !Number.isFinite(value) || value < 0) return undefined;
  if (value <= 1) return value;
  if (value <= 100) return value / 100;
  return undefined;
}

function extractConfidenceFromScores(
  scores: ResearchTier2Result["telemetry"]["scores"],
  preferredKeywords: string[]
): number | undefined {
  for (const score of scores) {
    if (typeof score.value !== "number") continue;
    const label = score.label.trim().toLowerCase();
    if (!preferredKeywords.some((keyword) => label.includes(keyword))) continue;
    const normalized = normalizeConfidenceRatio(score.value);
    if (normalized !== undefined) return normalized;
  }
  return undefined;
}

function resolveTelemetryConfidence(result: ResearchTier2Result | null): number | undefined {
  if (!result) return undefined;

  const explicit = normalizeConfidenceRatio(result.verificationStatus?.confidence);
  if (explicit !== undefined) return explicit;

  const matrixConfidences = result.telemetry.verificationMatrix
    .map((item) => normalizeConfidenceRatio(item.confidence))
    .filter((value): value is number => value !== undefined);
  if (matrixConfidences.length) {
    const avg = matrixConfidences.reduce((sum, value) => sum + value, 0) / matrixConfidences.length;
    return Math.max(0, Math.min(1, avg));
  }

  const scoreConfidence = extractConfidenceFromScores(result.telemetry.scores, [
    "verification confidence",
    "confidence",
  ]);
  if (scoreConfidence !== undefined) return scoreConfidence;

  const relevanceConfidenceRaw = extractConfidenceFromScores(result.telemetry.scores, [
    "relevance",
    "retrieval score",
    "score",
  ]);
  if (relevanceConfidenceRaw !== undefined && relevanceConfidenceRaw > 0) return relevanceConfidenceRaw;

  const routing = normalizeConfidenceRatio(result.debug.routing?.confidence);
  if (routing !== undefined) return routing;

  const hasAnswer = Boolean(result.answer?.trim());
  const citationCount = result.citations.length;
  const docCount = result.telemetry.docs.length;
  const sourceAttemptCount = result.telemetry.sourceAttempts.length;
  const flowStageCount = result.flowStages.length;
  const verificationCount = result.telemetry.verificationMatrix.length;
  const errorCount = result.telemetry.errors.length;

  const hasSignal =
    hasAnswer ||
    citationCount > 0 ||
    docCount > 0 ||
    sourceAttemptCount > 0 ||
    flowStageCount > 0 ||
    verificationCount > 0;

  if (!hasSignal) return undefined;

  let heuristic = 0.5;
  heuristic += Math.min(6, citationCount) * 0.03;
  heuristic += Math.min(10, docCount) * 0.015;
  heuristic += Math.min(6, sourceAttemptCount) * 0.01;
  heuristic += Math.min(4, flowStageCount) * 0.02;
  heuristic += Math.min(3, verificationCount) * 0.025;
  if (hasAnswer) heuristic += 0.08;
  if (errorCount > 0) heuristic -= Math.min(0.18, errorCount * 0.06);
  if (relevanceConfidenceRaw === 0 && (citationCount > 0 || docCount > 0)) {
    heuristic = Math.max(heuristic, 0.58);
  }

  return Math.max(0.18, Math.min(0.92, heuristic));
}

function logicFlowStatusMeta(status: LogicFlowNodeStatus): {
  dotClass: string;
  labelClass: string;
  detailClass: string;
} {
  if (status === "completed") {
    return {
      dotClass: "bg-emerald-500 ring-4 ring-emerald-500/25",
      labelClass: "text-[var(--text-primary)]",
      detailClass: "text-emerald-700 dark:text-emerald-300",
    };
  }
  if (status === "in_progress") {
    return {
      dotClass: "bg-cyan-500 ring-4 ring-cyan-500/25",
      labelClass: "text-[var(--text-primary)]",
      detailClass: "text-cyan-700 dark:text-cyan-300",
    };
  }
  if (status === "warning") {
    return {
      dotClass: "bg-amber-500 ring-4 ring-amber-500/25",
      labelClass: "text-[var(--text-primary)]",
      detailClass: "text-amber-700 dark:text-amber-300",
    };
  }
  if (status === "failed") {
    return {
      dotClass: "bg-rose-500 ring-4 ring-rose-500/25",
      labelClass: "text-[var(--text-primary)]",
      detailClass: "text-rose-700 dark:text-rose-300",
    };
  }
  if (status === "skipped") {
    return {
      dotClass: "bg-slate-400 ring-4 ring-slate-400/20",
      labelClass: "text-[var(--text-secondary)]",
      detailClass: "text-[var(--text-muted)]",
    };
  }
  return {
    dotClass: "bg-slate-300 ring-4 ring-slate-300/20 dark:bg-slate-600 dark:ring-slate-600/20",
    labelClass: "text-[var(--text-muted)]",
    detailClass: "text-[var(--text-muted)]",
  };
}

export default function ChatWorkspacePage() {
  const [query, setQuery] = useState("");
  const [searchText, setSearchText] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState(true);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isLoadingTurns, setIsLoadingTurns] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [folders, setFolders] = useState<WorkspaceFolder[]>([]);
  const [conversations, setConversations] = useState<WorkspaceConversationItem[]>([]);
  const [notes, setNotes] = useState<WorkspaceNote[]>([]);
  const [suggestions, setSuggestions] = useState<WorkspaceSuggestion[]>([]);
  const [searchResult, setSearchResult] = useState<WorkspaceSearchResponse | null>(null);
  const [shareInfo, setShareInfo] = useState<WorkspaceConversationShare | null>(null);
  const [shares, setShares] = useState<WorkspaceConversationShareListItem[]>([]);
  const [localFallbackConversations, setLocalFallbackConversations] = useState<
    WorkspaceConversationItem[]
  >([]);
  const [localTurnsByConversationId, setLocalTurnsByConversationId] = useState<
    Record<number, ConversationItem[]>
  >({});
  const [workspaceApiUnavailable, setWorkspaceApiUnavailable] = useState(false);

  const [noteTitleDraft, setNoteTitleDraft] = useState("");
  const [noteMarkdownDraft, setNoteMarkdownDraft] = useState("");
  const [noteTagsDraft, setNoteTagsDraft] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [conversationTitleDraft, setConversationTitleDraft] = useState("");
  const [folderManagerSearch, setFolderManagerSearch] = useState("");

  const [selectedFolderFilterId, setSelectedFolderFilterId] = useState<number | null>(null);
  const [bulkFolderTarget, setBulkFolderTarget] = useState<string>("skip");

  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversationMeta, setActiveConversationMeta] = useState<WorkspaceConversationItem | null>(null);
  const [conversationTurns, setConversationTurns] = useState<ConversationItem[]>([]);
  const [selectedConversationIds, setSelectedConversationIds] = useState<number[]>([]);
  const [draggingConversationId, setDraggingConversationId] = useState<number | null>(null);

  const [selectedResearchMode, setSelectedResearchMode] =
    useState<ResearchExecutionMode>("fast");
  const [selectedRetrievalStackMode, setSelectedRetrievalStackMode] =
    useState<ResearchRetrievalStackMode>("auto");
  const [workspaceLeftView, setWorkspaceLeftView] = useState<WorkspaceLeftView>("chat");
  const [liveStatusNote, setLiveStatusNote] = useState("");
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [commandPaletteQuery, setCommandPaletteQuery] = useState("");
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);
  const [visibleConversationLimit, setVisibleConversationLimit] = useState(40);
  const [isScopeManagerOpen, setIsScopeManagerOpen] = useState(false);
  const [scopeFolderDraft, setScopeFolderDraft] = useState("");
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [accountRole, setAccountRole] = useState<UserRole>("normal");

  const isFastResearchMode = selectedResearchMode === "fast";
  const conversationScrollRef = useRef<HTMLDivElement | null>(null);
  const conversationListViewportRef = useRef<HTMLDivElement | null>(null);
  const didAutoSelectInitialConversationRef = useRef(false);

  const latestTurn = useMemo(
    () => (conversationTurns.length ? conversationTurns[conversationTurns.length - 1] : null),
    [conversationTurns]
  );
  const latestAnswer = useMemo(() => latestAnswerFromTurn(latestTurn), [latestTurn]);
  const selectedConversationSet = useMemo(
    () => new Set(selectedConversationIds),
    [selectedConversationIds]
  );
  const localConversationIdSet = useMemo(
    () =>
      new Set(localFallbackConversations.map((item) => item.conversation_id)),
    [localFallbackConversations]
  );
  const mergedConversations = useMemo(() => {
    if (!localFallbackConversations.length) return conversations;
    const merged = new Map<number, WorkspaceConversationItem>();
    for (const item of localFallbackConversations) {
      merged.set(item.conversation_id, item);
    }
    for (const item of conversations) {
      merged.set(item.conversation_id, item);
    }
    return Array.from(merged.values()).sort((a, b) => {
      const aTs = Date.parse(a.last_message_at || a.created_at || "") || 0;
      const bTs = Date.parse(b.last_message_at || b.created_at || "") || 0;
      return bTs - aTs;
    });
  }, [conversations, localFallbackConversations]);
  const effectiveSummary = useMemo(() => {
    if (summary) return summary;
    const localMessages = mergedConversations.reduce(
      (acc, item) => acc + Math.max(item.message_count || 0, 0),
      0
    );
    const pinnedNotes = notes.filter((note) => note.is_pinned).length;
    return {
      conversations: mergedConversations.length,
      messages: localMessages,
      folders: folders.length,
      channels: 0,
      notes: notes.length,
      pinned_notes: pinnedNotes,
    } satisfies WorkspaceSummary;
  }, [folders.length, mergedConversations, notes, summary]);
  const focusById = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (!element) return;
    if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
      element.focus();
      const length = element.value.length;
      element.setSelectionRange(length, length);
      return;
    }
    (element as HTMLElement).focus();
  }, []);

  useEffect(() => {
    const node = conversationScrollRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [conversationTurns, isLoadingTurns, isSubmitting]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 2500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    setConversationTitleDraft(activeConversationMeta?.title ?? "");
  }, [activeConversationMeta?.title]);

  useEffect(() => {
    if (!isMobileSidebarOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobileSidebarOpen]);

  useEffect(() => {
    setAccountRole(getRole());
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setIsMobileSidebarOpen(false);
      }
    };
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }
    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedMode = window.localStorage.getItem("clara_chat_research_mode");
    const storedStack = window.localStorage.getItem("clara_chat_retrieval_stack_mode");
    if (storedMode === "fast" || storedMode === "deep" || storedMode === "deep_beta") {
      setSelectedResearchMode(storedMode);
    }
    if (storedStack === "auto" || storedStack === "full") {
      setSelectedRetrievalStackMode(storedStack);
    }
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated || typeof window === "undefined") return;
    window.localStorage.setItem("clara_chat_research_mode", selectedResearchMode);
  }, [isHydrated, selectedResearchMode]);

  useEffect(() => {
    if (!isHydrated || typeof window === "undefined") return;
    window.localStorage.setItem("clara_chat_retrieval_stack_mode", selectedRetrievalStackMode);
  }, [isHydrated, selectedRetrievalStackMode]);

  const refreshSummary = useCallback(async () => {
    try {
      const nextSummary = await getWorkspaceSummary();
      setSummary(nextSummary);
    } catch {
      // Keep existing summary when refresh fails.
    }
  }, []);

  const loadConversations = useCallback(async (activeIdOverride?: number | null) => {
    setIsLoadingConversations(true);
    try {
      if (workspaceApiUnavailable) {
        try {
          const fallbackRows = await listResearchConversations(80);
          const fallbackItems: WorkspaceConversationItem[] = fallbackRows.map((row) => {
            const created = new Date(row.createdAt || Date.now()).toISOString();
            const preview = row.query || "Research conversation";
            const normalizedId = Math.trunc(Number(row.id));
            const normalizedQueryId = row.queryId ? Math.trunc(Number(row.queryId)) : null;
            return {
              conversation_id: Number.isFinite(normalizedId) ? normalizedId : Date.now(),
              title: preview.slice(0, 255),
              preview: preview.slice(0, 260),
              query_id:
                normalizedQueryId !== null && Number.isFinite(normalizedQueryId)
                  ? normalizedQueryId
                  : null,
              message_count: 1,
              created_at: created,
              last_message_at: created,
              folder_id: null,
              channel_id: null,
              is_favorite: false,
            };
          });
          setConversations(fallbackItems);
          return fallbackItems;
        } catch {
          setConversations([]);
          return [];
        }
      }
      const items = await listWorkspaceConversations({
        limit: 80,
        folderId: selectedFolderFilterId ?? undefined,
        favoritesOnly: false,
      });
      setWorkspaceApiUnavailable(false);
      setConversations(items);
      const resolvedActiveId =
        typeof activeIdOverride === "number" ? activeIdOverride : activeConversationId;
      if (resolvedActiveId === null) return items;
      const activeItem = items.find((item) => item.conversation_id === resolvedActiveId) ?? null;
      if (activeItem) {
        setActiveConversationMeta(activeItem);
      }
      return items;
    } catch (cause) {
      if (isNotFoundLikeError(cause)) {
        setWorkspaceApiUnavailable(true);
        try {
          const fallbackRows = await listResearchConversations(80);
          const fallbackItems: WorkspaceConversationItem[] = fallbackRows.map((row) => {
            const created = new Date(row.createdAt || Date.now()).toISOString();
            const preview = row.query || "Research conversation";
            const normalizedId = Math.trunc(Number(row.id));
            const normalizedQueryId = row.queryId ? Math.trunc(Number(row.queryId)) : null;
            return {
              conversation_id: Number.isFinite(normalizedId) ? normalizedId : Date.now(),
              title: preview.slice(0, 255),
              preview: preview.slice(0, 260),
              query_id:
                normalizedQueryId !== null && Number.isFinite(normalizedQueryId)
                  ? normalizedQueryId
                  : null,
              message_count: 1,
              created_at: created,
              last_message_at: created,
              folder_id: null,
              channel_id: null,
              is_favorite: false,
            };
          });
          setConversations(fallbackItems);
          setNotice(
            "Workspace API chưa sẵn sàng, đang dùng lịch sử research làm nguồn conversation."
          );
          return fallbackItems;
        } catch {
          // continue to generic error handler below.
        }
      }
      setError(
        cause instanceof Error
          ? cause.message
          : "Không thể tải danh sách hội thoại workspace."
      );
      return [];
    } finally {
      setIsLoadingConversations(false);
    }
  }, [
    activeConversationId,
    selectedFolderFilterId,
    workspaceApiUnavailable,
  ]);

  const loadNotes = useCallback(async () => {
    try {
      const list = await listWorkspaceNotes({ limit: 100 });
      setNotes(list);
    } catch {
      // Notes block should not break chat flow.
    }
  }, []);

  const loadSuggestions = useCallback(async () => {
    try {
      const list = await listWorkspaceSuggestions(12);
      setSuggestions(list);
    } catch {
      // Suggestions are optional.
    }
  }, []);

  const loadShares = useCallback(async () => {
    if (workspaceApiUnavailable) {
      setShares([]);
      return;
    }
    try {
      const rows = await listWorkspaceShares({ limit: 80, activeOnly: false });
      setShares(rows);
    } catch {
      // Shares should not block workspace.
    }
  }, [workspaceApiUnavailable]);

  const loadStaticWorkspaceData = useCallback(async () => {
    setIsLoadingWorkspace(true);
    setError("");
    try {
      const [summaryResult, foldersResult] = await Promise.allSettled([
        getWorkspaceSummary(),
        listWorkspaceFolders(false),
      ]);

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      }
      if (foldersResult.status === "fulfilled") {
        setFolders(foldersResult.value);
      }
      await Promise.allSettled([
        loadNotes(),
        loadSuggestions(),
        loadConversations(),
        loadShares(),
      ]);

      const bootstrapErrors: string[] = [];
      if (summaryResult.status === "rejected") bootstrapErrors.push("summary");
      if (foldersResult.status === "rejected") bootstrapErrors.push("folders");
      const workspaceMissingSignals = [
        summaryResult.status === "rejected" ? summaryResult.reason : null,
        foldersResult.status === "rejected" ? foldersResult.reason : null,
      ].filter((item) => item !== null);
      if (workspaceMissingSignals.some((item) => isNotFoundLikeError(item))) {
        setWorkspaceApiUnavailable(true);
      }
      if (bootstrapErrors.length) {
        setNotice(`Workspace loaded with partial data (${bootstrapErrors.join(", ")}).`);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải workspace chat.");
    } finally {
      setIsLoadingWorkspace(false);
    }
  }, [loadConversations, loadNotes, loadShares, loadSuggestions]);

  const loadConversationTurns = useCallback(async (conversationId: number, fallbackItem?: WorkspaceConversationItem) => {
    setIsLoadingTurns(true);
    try {
      const rows = await listResearchConversationMessages(conversationId, 180);
      if (!rows.length) {
        const localTurns = localTurnsByConversationId[conversationId];
        if (Array.isArray(localTurns) && localTurns.length) {
          setConversationTurns(localTurns);
          return;
        }
        setConversationTurns([]);
        if (fallbackItem) {
          setNotice(`Conversation #${fallbackItem.conversation_id} chưa có message chi tiết.`);
        }
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
    } catch (cause) {
      const localTurns = localTurnsByConversationId[conversationId];
      if (Array.isArray(localTurns) && localTurns.length) {
        setConversationTurns(localTurns);
        setNotice(`Đang hiển thị bản local cache cho conversation #${conversationId}.`);
      } else {
        setConversationTurns([]);
      }
      setError(
        cause instanceof Error
          ? cause.message
          : "Không thể tải tin nhắn của conversation."
      );
    } finally {
      setIsLoadingTurns(false);
    }
  }, [localTurnsByConversationId]);

  useEffect(() => {
    void loadStaticWorkspaceData();
  }, [loadStaticWorkspaceData]);

  useEffect(() => {
    if (searchText.trim()) return;
    void loadConversations();
  }, [loadConversations, searchText]);

  useEffect(() => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) {
      setShareInfo(null);
      return;
    }
    let active = true;
    const run = async () => {
      try {
        const share = await getWorkspaceConversationShare(conversationId);
        if (!active) return;
        setShareInfo(share);
      } catch {
        if (!active) return;
        setShareInfo(null);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [activeConversationId]);

  const copyText = useCallback(async (value: string, successNotice = "Đã copy.") => {
    if (!value.trim()) return;
    try {
      await navigator.clipboard.writeText(value);
      setNotice(successNotice);
    } catch {
      window.prompt("Copy", value);
    }
  }, []);

  useEffect(() => {
    const keyword = searchText.trim();
    if (!keyword) {
      setSearchResult(null);
      return;
    }

    let active = true;
    const timer = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const result = await searchWorkspace(keyword, 16);
        if (!active) return;
        setSearchResult(result);
      } catch (cause) {
        if (!active) return;
        setSearchResult(null);
        setError(cause instanceof Error ? cause.message : "Không thể tìm kiếm trong workspace.");
      } finally {
        if (active) setIsSearching(false);
      }
    }, 250);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [searchText]);

  const displayedConversations = useMemo(() => {
    if (searchResult) return searchResult.conversations;
    return mergedConversations;
  }, [mergedConversations, searchResult]);
  const visibleConversations = useMemo(
    () => displayedConversations.slice(0, visibleConversationLimit),
    [displayedConversations, visibleConversationLimit]
  );
  const conversationVirtualItems = useMemo<ConversationVirtualItem[]>(() => {
    let previousDayKey: string | null = null;
    return visibleConversations.map((item) => {
      const currentDayKey = toDayKey(toConversationTimestamp(item));
      const dayLabel = currentDayKey !== previousDayKey ? currentDayKey : null;
      previousDayKey = currentDayKey;
      return {
        key: `row-${item.conversation_id}-${item.last_message_at || item.created_at || "na"}`,
        item,
        dayLabel,
      };
    });
  }, [visibleConversations]);
  const displayedConversationMessageCount = useMemo(
    () =>
      displayedConversations.reduce(
        (acc, item) => acc + Math.max(item.message_count || 0, 0),
        0
      ),
    [displayedConversations]
  );

  useEffect(() => {
    if (!selectedConversationIds.length) return;
    const visible = new Set(displayedConversations.map((item) => item.conversation_id));
    setSelectedConversationIds((prev) => prev.filter((id) => visible.has(id)));
  }, [displayedConversations, selectedConversationIds.length]);

  useEffect(() => {
    if (isSelectionMode) return;
    if (!selectedConversationIds.length) return;
    setSelectedConversationIds([]);
  }, [isSelectionMode, selectedConversationIds.length]);

  useEffect(() => {
    setVisibleConversationLimit(40);
  }, [searchText, selectedFolderFilterId]);
  const conversationVirtualizer = useVirtualizer({
    count: conversationVirtualItems.length,
    getScrollElement: () => conversationListViewportRef.current,
    estimateSize: () => 96,
    overscan: 10,
  });

  const displayedNotes = useMemo(() => {
    if (searchResult) return searchResult.notes;
    return notes;
  }, [notes, searchResult]);

  const displayedSuggestions = useMemo(() => {
    if (searchResult?.suggestions?.length) return searchResult.suggestions;
    return suggestions;
  }, [searchResult, suggestions]);

  const folderFilterList = useMemo(() => {
    if (searchResult?.folders?.length) return searchResult.folders;
    return folders;
  }, [folders, searchResult]);
  const folderManagerItems = useMemo(() => {
    const keyword = folderManagerSearch.trim().toLowerCase();
    if (!keyword) return folders;
    return folders.filter((folder) => folder.name.toLowerCase().includes(keyword));
  }, [folderManagerSearch, folders]);

  const setConversationMetaPatch = useCallback(
    (conversationId: number, patch: Partial<WorkspaceConversationItem>) => {
      setConversations((prev) =>
        prev.map((item) =>
          item.conversation_id === conversationId ? { ...item, ...patch } : item
        )
      );
      setLocalFallbackConversations((prev) =>
        prev.map((item) =>
          item.conversation_id === conversationId ? { ...item, ...patch } : item
        )
      );
      setSearchResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          conversations: prev.conversations.map((item) =>
            item.conversation_id === conversationId ? { ...item, ...patch } : item
          ),
        };
      });
      setActiveConversationMeta((prev) => {
        if (!prev || prev.conversation_id !== conversationId) return prev;
        return { ...prev, ...patch };
      });
    },
    []
  );

  const toggleConversationSelection = useCallback((conversationId: number, checked: boolean) => {
    setSelectedConversationIds((prev) => {
      if (checked) {
        if (prev.includes(conversationId)) return prev;
        return [...prev, conversationId];
      }
      return prev.filter((id) => id !== conversationId);
    });
  }, []);

  const applyBulkMetaUpdate = useCallback(
    async (payload: { folderId?: number | null; isFavorite?: boolean }) => {
      if (workspaceApiUnavailable) {
        setNotice("Workspace API chưa sẵn sàng nên bulk metadata đang tạm khóa.");
        return;
      }
      if (!selectedConversationIds.length) {
        setNotice("Hãy chọn conversation trước khi chạy bulk action.");
        return;
      }
      try {
        const result = await bulkUpdateWorkspaceConversationMeta({
          conversationIds: selectedConversationIds,
          folderId: payload.folderId,
          isFavorite: payload.isFavorite,
          touched: false,
        });
        const updatedIds = new Set(result.updated_ids);
        setConversations((prev) =>
          prev.map((item) =>
            updatedIds.has(item.conversation_id)
              ? {
                  ...item,
                  folder_id:
                    payload.folderId !== undefined ? (payload.folderId ?? null) : item.folder_id,
                  is_favorite:
                    payload.isFavorite !== undefined ? payload.isFavorite : item.is_favorite,
                }
              : item
          )
        );
        setSearchResult((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            conversations: prev.conversations.map((item) =>
              updatedIds.has(item.conversation_id)
                ? {
                    ...item,
                    folder_id:
                      payload.folderId !== undefined ? (payload.folderId ?? null) : item.folder_id,
                    is_favorite:
                      payload.isFavorite !== undefined ? payload.isFavorite : item.is_favorite,
                  }
                : item
            ),
          };
        });
        if (activeConversationId && updatedIds.has(activeConversationId)) {
          setActiveConversationMeta((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              folder_id:
                payload.folderId !== undefined ? (payload.folderId ?? null) : prev.folder_id,
              is_favorite:
                payload.isFavorite !== undefined ? payload.isFavorite : prev.is_favorite,
            };
          });
        }
        await refreshSummary();
        setNotice(`Đã cập nhật ${result.updated_count} conversation.`);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể cập nhật bulk metadata.");
      }
    },
    [activeConversationId, refreshSummary, selectedConversationIds, workspaceApiUnavailable]
  );

  const bulkDeleteSelectedConversations = useCallback(async () => {
    if (!selectedConversationIds.length) {
      setNotice("Hãy chọn conversation trước khi xóa.");
      return;
    }
    const confirmed = window.confirm(`Xóa ${selectedConversationIds.length} conversation đã chọn?`);
    if (!confirmed) return;
    let deletedCount = 0;
    for (const conversationId of selectedConversationIds) {
      try {
        const isLocal = localConversationIdSet.has(conversationId);
        if (!isLocal || !workspaceApiUnavailable) {
          await deleteWorkspaceConversation(conversationId);
        }
        deletedCount += 1;
      } catch {
        // Continue deleting remaining items.
      }
    }
    setLocalFallbackConversations((prev) =>
      prev.filter((item) => !selectedConversationIds.includes(item.conversation_id))
    );
    setLocalTurnsByConversationId((prev) => {
      if (!selectedConversationIds.length) return prev;
      const next = { ...prev };
      for (const id of selectedConversationIds) {
        delete next[id];
      }
      return next;
    });
    setSelectedConversationIds([]);
    if (activeConversationId && selectedConversationIds.includes(activeConversationId)) {
      setActiveConversationId(null);
      setActiveConversationMeta(null);
      setConversationTurns([]);
    }
    await Promise.all([loadConversations(), refreshSummary()]);
    setNotice(`Đã xóa ${deletedCount}/${selectedConversationIds.length} conversation.`);
  }, [
    activeConversationId,
    loadConversations,
    localConversationIdSet,
    refreshSummary,
    selectedConversationIds,
    workspaceApiUnavailable,
  ]);

  const bulkExportSelectedConversations = useCallback(
    async (format: "markdown" | "docx") => {
      if (!selectedConversationIds.length) {
        setNotice("Hãy chọn conversation trước khi export.");
        return;
      }
      let successCount = 0;
      for (const conversationId of selectedConversationIds) {
        try {
          const isLocal = localConversationIdSet.has(conversationId);
          if (!isLocal && !workspaceApiUnavailable) {
            const blob = await exportWorkspaceConversation(conversationId, format);
            triggerBlobDownload(
              blob,
              `conversation-${conversationId}.${format === "markdown" ? "md" : "docx"}`
            );
            successCount += 1;
            continue;
          }

          const turns = localTurnsByConversationId[conversationId] ?? [];
          const item = displayedConversations.find(
            (row) => row.conversation_id === conversationId
          );
          const markdown = buildConversationMarkdownExport(
            item?.title || `Conversation ${conversationId}`,
            turns
          );
          if (format === "markdown") {
            triggerBlobDownload(
              new Blob([markdown], { type: "text/markdown;charset=utf-8" }),
              `conversation-${conversationId}.md`
            );
          } else {
            try {
              const docx = await exportWorkspaceDocxFromMarkdown({
                markdown,
                title: `conversation-${conversationId}`,
              });
              triggerBlobDownload(docx, `conversation-${conversationId}.docx`);
            } catch {
              triggerBlobDownload(
                new Blob([markdown], { type: "text/markdown;charset=utf-8" }),
                `conversation-${conversationId}.md`
              );
            }
          }
          successCount += 1;
        } catch {
          // Keep exporting remaining conversations.
        }
      }
      setNotice(`Đã export ${successCount}/${selectedConversationIds.length} conversation (${format}).`);
    },
    [
      displayedConversations,
      localConversationIdSet,
      localTurnsByConversationId,
      selectedConversationIds,
      workspaceApiUnavailable,
    ]
  );

  const onSelectConversation = useCallback(
    async (item: WorkspaceConversationItem) => {
      const conversationId = asConversationId(item.conversation_id);
      if (!conversationId) return;
      setActiveConversationId(conversationId);
      setActiveConversationMeta(item);
      setIsMobileSidebarOpen(false);
      setError("");
      setLiveJobId(null);
      setLiveStatusNote("");
      const localTurns = localTurnsByConversationId[conversationId];
      if (Array.isArray(localTurns) && localTurns.length) {
        setConversationTurns(localTurns);
      }
      await loadConversationTurns(conversationId, item);
      if (workspaceApiUnavailable) {
        return;
      }
      try {
        await updateWorkspaceConversationMeta(conversationId, { touched: true });
      } catch {
        // Ignore touched update failure.
      }
    },
    [loadConversationTurns, localTurnsByConversationId, workspaceApiUnavailable]
  );

  useEffect(() => {
    if (didAutoSelectInitialConversationRef.current) return;
    if (activeConversationId !== null) return;
    if (isLoadingWorkspace || isLoadingConversations) return;
    if (!displayedConversations.length) return;
    const firstConversation = displayedConversations[0];
    if (!firstConversation) return;
    didAutoSelectInitialConversationRef.current = true;
    void onSelectConversation(firstConversation);
  }, [
    activeConversationId,
    displayedConversations,
    isLoadingConversations,
    isLoadingWorkspace,
    onSelectConversation,
  ]);

  const onDragConversationStart = (conversationId: number) => {
    setDraggingConversationId(conversationId);
  };

  const onDragConversationEnd = () => {
    setDraggingConversationId(null);
  };

  const createNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setActiveConversationMeta(null);
    setConversationTurns([]);
    setSelectedConversationIds([]);
    setShareInfo(null);
    setConversationTitleDraft("");
    setQuery("");
    setError("");
    setLiveStatusNote("");
    setLiveJobId(null);
    setIsMobileSidebarOpen(false);
    setIsCommandPaletteOpen(false);
    setCommandPaletteQuery("");
    setAccountMenuOpen(false);
  }, []);

  const onGoBack = useCallback(() => {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/dashboard";
  }, []);

  const onLogout = useCallback(() => {
    void (async () => {
      try {
        await api.post("/auth/logout");
      } catch {
        // Fall back to client-side token cleanup on API failures.
      } finally {
        clearTokens();
        window.location.href = "/login";
      }
    })();
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const withCommand = event.metaKey || event.ctrlKey;

      if (isCommandPaletteOpen) {
        if (key === "escape") {
          event.preventDefault();
          setIsCommandPaletteOpen(false);
          setCommandPaletteQuery("");
        }
        return;
      }

      if (withCommand && event.shiftKey && key === "p") {
        event.preventDefault();
        setIsCommandPaletteOpen(true);
        return;
      }

      if (withCommand && key === "k") {
        event.preventDefault();
        focusById("workspace-search");
        return;
      }

      if (withCommand && event.shiftKey && key === "n") {
        event.preventDefault();
        createNewConversation();
        focusById("chat-composer-input");
        return;
      }

      if (!withCommand && !event.altKey && key === "/" && !isEditableElement(event.target)) {
        event.preventDefault();
        focusById("chat-composer-input");
        return;
      }

      if (key === "escape") {
        setIsCommandPaletteOpen(false);
        setCommandPaletteQuery("");
        setIsScopeManagerOpen(false);
        setIsMobileSidebarOpen(false);
        setAccountMenuOpen(false);
      }

      if (
        event.altKey &&
        (event.key === "ArrowDown" || event.key === "ArrowUp") &&
        !isEditableElement(event.target) &&
        displayedConversations.length
      ) {
        event.preventDefault();
        const currentIndex = activeConversationId
          ? displayedConversations.findIndex(
              (item) => item.conversation_id === activeConversationId
            )
          : -1;
        const delta = event.key === "ArrowDown" ? 1 : -1;
        const nextIndexRaw =
          currentIndex < 0 ? 0 : (currentIndex + delta + displayedConversations.length) % displayedConversations.length;
        const nextItem = displayedConversations[nextIndexRaw];
        if (nextItem) {
          void onSelectConversation(nextItem);
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [
    activeConversationId,
    createNewConversation,
    displayedConversations,
    focusById,
    isCommandPaletteOpen,
    onSelectConversation,
  ]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isSubmitting) return;

    setIsSubmitting(true);
    setError("");

    try {
      const { finalPayload } = await executeResearchTier2Job(message, {
        researchMode: selectedResearchMode,
        retrievalStackMode: selectedRetrievalStackMode,
        onJobCreated: (job) => {
          setLiveJobId(job.job_id);
        },
        onSnapshot: (snapshot) => {
          const progress = normalizeResearchTier2JobProgress(snapshot.progress);
          setLiveStatusNote(progress.statusNote ?? "");
        },
        onStreamingFallback: (streamMessage) => {
          setLiveStatusNote(`${streamMessage} Đang fallback sang polling.`);
        },
      });

      const normalized = normalizeResearchTier2(finalPayload);
      if (!normalized.answer && !normalized.citations.length) {
        throw new Error("Chưa có phản hồi research hợp lệ.");
      }

      const nextResult: ResearchResult = {
        tier: "tier2",
        ...normalized,
      };

      const localTurn = createConversationItem(message, nextResult, {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      });
      setConversationTurns((prev) => [...prev, localTurn]);

      let targetConversationId = activeConversationId;
      let didPersistConversation = false;
      let didPersistLocally = false;

      try {
        if (targetConversationId) {
          const persisted = await appendResearchConversationMessage(
            targetConversationId,
            message,
            nextResult as unknown as Record<string, unknown>
          );
          targetConversationId = asConversationId(Number(persisted.id));
          didPersistConversation = true;
        } else {
          const persisted = await createResearchConversation(
            message,
            nextResult as unknown as Record<string, unknown>
          );
          targetConversationId = asConversationId(Number(persisted.id));
          didPersistConversation = true;
        }
      } catch (persistError) {
        const fallbackConversationId = targetConversationId ?? Date.now();
        targetConversationId = fallbackConversationId;
        const nowIso = new Date().toISOString();
        const localConversationItem: WorkspaceConversationItem = {
          conversation_id: fallbackConversationId,
          title: message.slice(0, 255),
          preview: message.slice(0, 260),
          query_id: null,
          message_count: Math.max(
            1,
            (activeConversationMeta?.conversation_id === fallbackConversationId
              ? activeConversationMeta.message_count
              : 0) + 1
          ),
          created_at:
            activeConversationMeta?.conversation_id === fallbackConversationId
              ? activeConversationMeta.created_at
              : nowIso,
          last_message_at: nowIso,
          folder_id: activeConversationMeta?.folder_id ?? null,
          channel_id: null,
          is_favorite: activeConversationMeta?.is_favorite ?? false,
        };
        setLocalFallbackConversations((prev) => {
          const filtered = prev.filter(
            (item) => item.conversation_id !== fallbackConversationId
          );
          return [localConversationItem, ...filtered].slice(
            0,
            LOCAL_WORKSPACE_MAX_ITEMS
          );
        });
        setLocalTurnsByConversationId((prev) => {
          const existing =
            prev[fallbackConversationId] && Array.isArray(prev[fallbackConversationId])
              ? prev[fallbackConversationId]
              : [];
          return {
            ...prev,
            [fallbackConversationId]: [...existing, localTurn],
          };
        });
        setActiveConversationMeta(localConversationItem);
        didPersistLocally = true;
        setError(
          persistError instanceof Error
            ? `Đã trả lời nhưng lưu hội thoại thất bại: ${persistError.message}`
            : "Đã trả lời nhưng lưu hội thoại thất bại."
        );
        setNotice(
          "Đã lưu local cache cho conversation hiện tại. Backend sync sẽ tự khôi phục sau."
        );
      }

      if (targetConversationId) {
        setActiveConversationId(targetConversationId);
        if (didPersistConversation) {
          await loadConversationTurns(targetConversationId);
        } else if (didPersistLocally) {
          setConversationTurns((prev) => [...prev]);
        }
      }

      setQuery("");
      setLiveJobId(null);
      setLiveStatusNote("");
      const [refreshedItems] = await Promise.all([
        loadConversations(targetConversationId),
        refreshSummary(),
        loadShares(),
      ]);

      if (targetConversationId && refreshedItems.length) {
        const found =
          refreshedItems.find((item) => item.conversation_id === targetConversationId) ?? null;
        if (found) setActiveConversationMeta(found);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xử lý câu hỏi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const onUpdateActiveConversationMeta = async (payload: {
    folderId?: number | null;
    isFavorite?: boolean;
  }) => {
    if (workspaceApiUnavailable) {
      setNotice("Workspace API chưa sẵn sàng nên metadata conversation đang tạm khóa.");
      return;
    }
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;

    try {
      const updated = await updateWorkspaceConversationMeta(conversationId, payload);
      setConversationMetaPatch(conversationId, {
        folder_id: updated.folder_id ?? null,
        is_favorite: updated.is_favorite,
      });
      await refreshSummary();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật metadata conversation.");
    }
  };

  const onCreateFolder = async (nameInput?: string) => {
    const name = parsePromptText(nameInput ?? scopeFolderDraft);
    if (!name) return;
    try {
      const created = await createWorkspaceFolder({ name });
      setFolders((prev) => [created, ...prev]);
      setScopeFolderDraft("");
      await refreshSummary();
      setNotice(`Đã tạo folder \"${created.name}\".`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo folder.");
    }
  };

  const onRenameFolder = async (folder: WorkspaceFolder) => {
    const name = parsePromptText(window.prompt("Đổi tên folder", folder.name));
    if (!name) return;
    try {
      const updated = await updateWorkspaceFolder(folder.id, { name });
      setFolders((prev) => prev.map((item) => (item.id === folder.id ? updated : item)));
      setNotice(`Đã cập nhật folder \"${updated.name}\".`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đổi tên folder.");
    }
  };

  const onDeleteFolder = async (folder: WorkspaceFolder) => {
    const confirmed = window.confirm(`Xóa folder "${folder.name}"?`);
    if (!confirmed) return;
    try {
      await deleteWorkspaceFolder(folder.id);
      setFolders((prev) => prev.filter((item) => item.id !== folder.id));
      if (selectedFolderFilterId === folder.id) setSelectedFolderFilterId(null);
      await refreshSummary();
      setNotice("Đã xóa folder.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa folder.");
    }
  };

  const onCreateInlineNote = async (fromLatestAnswer: boolean) => {
    if (fromLatestAnswer) {
      if (!latestAnswer.trim()) {
        setNotice("Chưa có câu trả lời để lưu note.");
        return;
      }
      setEditingNoteId(null);
      setNoteTitleDraft(latestTurn?.query.slice(0, 90) || "Ghi chú từ câu trả lời mới");
      setNoteMarkdownDraft(latestAnswer);
      setNoteTagsDraft("answer,auto");
      return;
    }
    setEditingNoteId(null);
    setNoteTitleDraft("Ghi chú mới");
    setNoteMarkdownDraft("");
    setNoteTagsDraft("");
  };

  const onSaveNoteDraft = async () => {
    const title = parsePromptText(noteTitleDraft);
    if (!title) {
      setError("Tiêu đề note không được để trống.");
      return;
    }
    const content = noteMarkdownDraft.trim();
    const tags = parseTagsInput(noteTagsDraft);
    const activeId = asConversationId(activeConversationId);
    try {
      if (editingNoteId) {
        const updated = await updateWorkspaceNote(editingNoteId, {
          title,
          contentMarkdown: content,
          tags,
          conversationId: activeId,
        });
        setNotes((prev) => prev.map((item) => (item.id === editingNoteId ? updated : item)));
        setNotice("Đã cập nhật note.");
      } else {
        const created = await createWorkspaceNote({
          title,
          contentMarkdown: content,
          tags,
          conversationId: activeId,
        });
        setNotes((prev) => [created, ...prev]);
        setNotice("Đã lưu note thành công.");
      }
      setEditingNoteId(null);
      setNoteTitleDraft("");
      setNoteMarkdownDraft("");
      setNoteTagsDraft("");
      await refreshSummary();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu note.");
    }
  };

  const onEditNote = (note: WorkspaceNote) => {
    setEditingNoteId(note.id);
    setNoteTitleDraft(note.title);
    setNoteMarkdownDraft(note.content_markdown);
    setNoteTagsDraft((note.tags || []).join(", "));
  };

  const onDeleteNote = async (note: WorkspaceNote) => {
    const confirmed = window.confirm(`Xóa note "${note.title}"?`);
    if (!confirmed) return;
    try {
      await deleteWorkspaceNote(note.id);
      setNotes((prev) => prev.filter((item) => item.id !== note.id));
      if (editingNoteId === note.id) {
        setEditingNoteId(null);
        setNoteTitleDraft("");
        setNoteMarkdownDraft("");
        setNoteTagsDraft("");
      }
      await refreshSummary();
      setNotice("Đã xóa note.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa note.");
    }
  };

  const onShareActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    if (workspaceApiUnavailable) {
      setNotice("Workspace API chưa sẵn sàng nên chưa thể tạo public share lúc này.");
      return;
    }

    try {
      const share = await createWorkspaceConversationShare(conversationId, {
        expiresInHours: 168,
        rotate: false,
      });
      setShareInfo(share);
      await loadShares();
      await copyText(share.public_url, "Đã copy link share public.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chia sẻ conversation.");
    }
  };

  const onRevokeShareActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    if (workspaceApiUnavailable) {
      setNotice("Workspace API chưa sẵn sàng nên chưa thể revoke share lúc này.");
      return;
    }
    try {
      await revokeWorkspaceConversationShare(conversationId);
      setShareInfo(null);
      await loadShares();
      setNotice("Đã thu hồi liên kết public.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể thu hồi liên kết.");
    }
  };

  const onOpenConversationFromShare = useCallback(
    async (shareItem: WorkspaceConversationShareListItem) => {
      const found =
        displayedConversations.find((item) => item.conversation_id === shareItem.conversation_id) ||
        mergedConversations.find((item) => item.conversation_id === shareItem.conversation_id);
      if (found) {
        await onSelectConversation(found);
        return;
      }
      const refreshed = await loadConversations(shareItem.conversation_id);
      const resolved =
        refreshed.find((item) => item.conversation_id === shareItem.conversation_id) || null;
      if (resolved) {
        await onSelectConversation(resolved);
        return;
      }
      setNotice(`Không tìm thấy conversation #${shareItem.conversation_id} trong workspace hiện tại.`);
    },
    [displayedConversations, loadConversations, mergedConversations, onSelectConversation]
  );

  const onExportActiveConversation = async (format: "markdown" | "docx") => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    const localTurns = localTurnsByConversationId[conversationId] ?? [];
    const localMarkdown = buildConversationMarkdownExport(
      activeConversationMeta?.title || `Conversation ${conversationId}`,
      localTurns
    );
    try {
      if (!workspaceApiUnavailable) {
        const blob = await exportWorkspaceConversation(conversationId, format);
        triggerBlobDownload(blob, `conversation-${conversationId}.${format === "markdown" ? "md" : "docx"}`);
        setNotice(`Đã export conversation #${conversationId} (${format}).`);
        return;
      }
      if (format === "markdown") {
        triggerBlobDownload(new Blob([localMarkdown], { type: "text/markdown;charset=utf-8" }), `conversation-${conversationId}.md`);
        setNotice(`Đã export conversation #${conversationId} (markdown local).`);
        return;
      }
      if (format === "docx" && localMarkdown.trim()) {
        const fallbackBlob = await exportWorkspaceDocxFromMarkdown({
          markdown: localMarkdown,
          title: "clara-chat-export",
        });
        triggerBlobDownload(fallbackBlob, "clara-chat-export.docx");
        setNotice("Đã export DOCX từ nội dung hiện tại.");
      }
    } catch (cause) {
      if (format === "docx" && localMarkdown.trim()) {
        try {
          const fallbackBlob = await exportWorkspaceDocxFromMarkdown({
            markdown: localMarkdown,
            title: "clara-chat-export",
          });
          triggerBlobDownload(fallbackBlob, "clara-chat-export.docx");
          setNotice("Đã export DOCX từ nội dung hiện tại.");
          return;
        } catch {
          triggerBlobDownload(
            new Blob([localMarkdown], { type: "text/markdown;charset=utf-8" }),
            `conversation-${conversationId}.md`
          );
          setNotice(
            "DOCX chưa sẵn ở backend hiện tại, đã fallback export Markdown để không mất dữ liệu."
          );
          return;
        }
      }
      setError(cause instanceof Error ? cause.message : "Không thể export conversation.");
    }
  };

  const onRenameActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    const title = parsePromptText(conversationTitleDraft);
    if (!conversationId || !title) return;
    const isLocal = localConversationIdSet.has(conversationId);
    if (workspaceApiUnavailable || isLocal) {
      setConversationMetaPatch(conversationId, { title });
      setLocalFallbackConversations((prev) =>
        prev.map((item) =>
          item.conversation_id === conversationId ? { ...item, title } : item
        )
      );
      setNotice("Đã đổi tên conversation (local cache).");
      return;
    }
    try {
      const updated = await updateWorkspaceConversation(conversationId, { title });
      setConversationMetaPatch(conversationId, { title: updated.title });
      setNotice("Đã đổi tên conversation.");
      await loadConversations(conversationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đổi tên conversation.");
    }
  };

  const onDeleteActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    const confirmed = window.confirm("Xóa conversation hiện tại?");
    if (!confirmed) return;
    const localExists = localFallbackConversations.some(
      (item) => item.conversation_id === conversationId
    );
    try {
      if (!localExists || !workspaceApiUnavailable) {
        await deleteWorkspaceConversation(conversationId);
      }
      setConversations((prev) => prev.filter((item) => item.conversation_id !== conversationId));
      setLocalFallbackConversations((prev) =>
        prev.filter((item) => item.conversation_id !== conversationId)
      );
      setLocalTurnsByConversationId((prev) => {
        if (!(conversationId in prev)) return prev;
        const next = { ...prev };
        delete next[conversationId];
        return next;
      });
      setSelectedConversationIds((prev) => prev.filter((id) => id !== conversationId));
      setActiveConversationId(null);
      setActiveConversationMeta(null);
      setConversationTurns([]);
      setShareInfo(null);
      await refreshSummary();
      setNotice("Đã xóa conversation.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa conversation.");
    }
  };

  const commandActions = useMemo<WorkspaceCommandAction[]>(() => {
    const activeConversation = asConversationId(activeConversationId);
    const canExport = Boolean(activeConversation);
    const canShare = Boolean(activeConversation) && !workspaceApiUnavailable;
    const hasLatestAnswer = latestAnswer.trim().length > 0;
    return [
      {
        id: "new-chat",
        label: "New chat",
        hint: "Ctrl/⌘+Shift+N",
        keywords: ["new", "chat", "conversation"],
        run: () => createNewConversation(),
      },
      {
        id: "focus-search",
        label: "Focus workspace search",
        hint: "Ctrl/⌘+K",
        keywords: ["focus", "search", "workspace"],
        run: () => focusById("workspace-search"),
      },
      {
        id: "focus-composer",
        label: "Focus chat composer",
        hint: "/",
        keywords: ["focus", "composer", "input", "prompt"],
        run: () => focusById("chat-composer-input"),
      },
      {
        id: "mode-fast",
        label: "Switch mode: Fast",
        keywords: ["mode", "fast", "research"],
        run: () => {
          setSelectedResearchMode("fast");
          setSelectedRetrievalStackMode("auto");
        },
      },
      {
        id: "mode-deep",
        label: "Switch mode: Deep",
        keywords: ["mode", "deep", "research"],
        run: () => setSelectedResearchMode("deep"),
      },
      {
        id: "mode-deep-beta",
        label: "Switch mode: Deep Beta",
        keywords: ["mode", "deep", "beta", "research"],
        run: () => setSelectedResearchMode("deep_beta"),
      },
      {
        id: "stack-auto",
        label: "Retrieval stack: Auto",
        keywords: ["retrieval", "stack", "auto"],
        run: () => setSelectedRetrievalStackMode("auto"),
      },
      {
        id: "stack-full",
        label: "Retrieval stack: Full",
        disabled: isFastResearchMode,
        keywords: ["retrieval", "stack", "full"],
        run: () => setSelectedRetrievalStackMode("full"),
      },
      {
        id: "export-docx",
        label: "Export active conversation as DOCX",
        disabled: !canExport,
        keywords: ["export", "docx", "word"],
        run: () => {
          void onExportActiveConversation("docx");
        },
      },
      {
        id: "export-markdown",
        label: "Export active conversation as Markdown",
        disabled: !canExport,
        keywords: ["export", "markdown", "md"],
        run: () => {
          void onExportActiveConversation("markdown");
        },
      },
      {
        id: "share-active",
        label: "Create public share link",
        disabled: !canShare,
        keywords: ["share", "public", "link"],
        run: () => {
          void onShareActiveConversation();
        },
      },
      {
        id: "revoke-share",
        label: "Revoke active share link",
        disabled: !canShare || !shareInfo,
        keywords: ["share", "revoke", "public"],
        run: () => {
          void onRevokeShareActiveConversation();
        },
      },
      {
        id: "save-note",
        label: "Save latest answer as note draft",
        disabled: !hasLatestAnswer,
        keywords: ["note", "save", "latest", "answer"],
        run: () => {
          void onCreateInlineNote(true);
        },
      },
      {
        id: "open-shares-page",
        label: "Open shares manager",
        keywords: ["shares", "manager", "public"],
        run: () => {
          window.location.href = "/chat/shares";
        },
      },
    ];
  }, [
    activeConversationId,
    createNewConversation,
    focusById,
    isFastResearchMode,
    latestAnswer,
    onCreateInlineNote,
    onExportActiveConversation,
    onRevokeShareActiveConversation,
    onShareActiveConversation,
    shareInfo,
    workspaceApiUnavailable,
  ]);
  const filteredCommandActions = useMemo(() => {
    const keyword = commandPaletteQuery.trim().toLowerCase();
    if (!keyword) return commandActions;
    return commandActions.filter((action) => {
      const haystack = [action.label, action.hint || "", ...action.keywords]
        .join(" ")
        .toLowerCase();
      return haystack.includes(keyword);
    });
  }, [commandActions, commandPaletteQuery]);
  const executeCommandAction = useCallback((action: WorkspaceCommandAction) => {
    if (action.disabled) return;
    action.run();
    setIsCommandPaletteOpen(false);
    setCommandPaletteQuery("");
  }, []);

  useEffect(() => {
    if (!isCommandPaletteOpen) return;
    const timer = window.setTimeout(() => {
      focusById("chat-command-palette-input");
    }, 10);
    return () => window.clearTimeout(timer);
  }, [focusById, isCommandPaletteOpen]);

  const onConversationListScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const element = event.currentTarget;
      const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
      if (remaining > 320) return;
      setVisibleConversationLimit((prev) =>
        Math.min(displayedConversations.length, prev + 30)
      );
    },
    [displayedConversations.length]
  );

  const latestTier2Turn = useMemo(
    () =>
      [...conversationTurns]
        .reverse()
        .find((item) => item.result.tier === "tier2") ?? null,
    [conversationTurns]
  );

  const latestTier2Result = latestTier2Turn?.result.tier === "tier2" ? latestTier2Turn.result : null;
  const logicFlowNodes = useMemo(
    () => buildLogicFlowNodes(latestTier2Result),
    [latestTier2Result]
  );
  const confidenceRatio = resolveTelemetryConfidence(latestTier2Result);
  const confidenceRingPercent = Math.max(0, Math.min(100, Math.round((confidenceRatio ?? 0.24) * 100)));
  const confidencePercent = Math.max(
    0,
    Math.min(100, Math.round((confidenceRatio ?? 0) * 100))
  );
  const confidenceDisplay = confidenceRatio === undefined ? "--" : confidenceRatio.toFixed(2);
  const confidenceLabel =
    confidenceRatio === undefined
      ? "Signal Pending"
      : confidencePercent >= 70
        ? "High Reliability"
        : "Needs Review";
  const telemetryBars = latestTier2Result
    ? [
        Math.min(96, Math.max(18, latestTier2Result.debug.flowEventCount * 4)),
        Math.min(96, Math.max(22, latestTier2Result.debug.telemetryDocCount * 5)),
        Math.min(96, Math.max(20, latestTier2Result.debug.telemetryKeywordCount * 6)),
        Math.min(96, Math.max(24, latestTier2Result.citations.length * 14)),
        Math.min(96, Math.max(20, latestTier2Result.debug.telemetrySourceAttemptCount * 12)),
        Math.min(96, Math.max(18, latestTier2Result.telemetry.errors.length ? 88 : 42)),
        Math.min(96, Math.max(16, latestTier2Result.debug.stageCount * 10)),
      ]
    : [30, 45, 60, 85, 70, 50, 35];

  const sourceIntel = useMemo(() => {
    const merged = new Map<
      string,
      { name: string; status: SourceIntelStatus; query?: string; attempts: number }
    >();

    for (const attempt of latestTier2Result?.telemetry.sourceAttempts ?? []) {
      const sourceName = (attempt.source || "unknown").trim() || "unknown";
      const key = sourceName.toLowerCase();
      const nextStatus = normalizeSourceStatus(attempt.status, Boolean(attempt.error));
      const current = merged.get(key);
      const status =
        current?.status === "error" || nextStatus === "error"
          ? "error"
          : current?.status === "connecting" || nextStatus === "connecting"
            ? "connecting"
            : "active";
      merged.set(key, {
        name: current?.name ?? sourceName,
        status,
        query: current?.query ?? attempt.query ?? attempt.subquery,
        attempts: (current?.attempts ?? 0) + 1,
      });
    }

    for (const citation of latestTier2Result?.citations ?? []) {
      const sourceName = (citation.source || citation.title || "").trim();
      if (!sourceName) continue;
      const key = sourceName.toLowerCase();
      if (!merged.has(key)) {
        merged.set(key, {
          name: sourceName,
          status: "active",
          query: undefined,
          attempts: 0,
        });
      }
    }

    const items = Array.from(merged.values()).sort((left, right) => {
      const severity = (value: SourceIntelStatus) =>
        value === "error" ? 0 : value === "connecting" ? 1 : 2;
      const diff = severity(right.status) - severity(left.status);
      if (diff !== 0) return diff;
      return right.attempts - left.attempts;
    });

    const globalSources = items.filter((item) => !isVietnamMedicalSource(item.name));
    const vietnamSources = items.filter((item) => isVietnamMedicalSource(item.name));
    const activeCount = items.filter((item) => item.status === "active").length;

    return {
      activeCount,
      all: items,
      global: globalSources,
      vietnam: vietnamSources,
    };
  }, [latestTier2Result]);

  const neuralLoadPercent = Math.round(
    telemetryBars.reduce((sum, value) => sum + value, 0) / Math.max(1, telemetryBars.length)
  );
  const sourceIntelGlobal = sourceIntel.global.slice(0, 10);
  const sourceIntelVietnam = sourceIntel.vietnam.slice(0, 6);

  return (
    <PageShell
      variant="plain"
      title=""
    >
      <div className="relative h-[calc(100dvh-11.5rem)] min-h-[640px] overflow-hidden rounded-[1.2rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-[var(--shadow-soft)] sm:h-[calc(100dvh-10.5rem)] lg:h-[calc(100dvh-8.75rem)]">
        {isMobileSidebarOpen ? (
          <button
            type="button"
            aria-label="Đóng sidebar"
            onClick={() => setIsMobileSidebarOpen(false)}
            className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[2px] lg:hidden"
          />
        ) : null}

        <div className="grid h-full min-h-0 gap-0 lg:grid-cols-[16rem_minmax(0,1fr)_18rem]">
        <aside
          className={[
            "fixed inset-y-0 left-0 z-50 flex w-[min(88vw,23rem)] flex-col overflow-hidden border-r border-[color:var(--shell-border)] bg-[#f1f4f7]/95 p-4 transition-transform duration-200 dark:bg-[#001c39]/95 lg:static lg:inset-auto lg:z-0 lg:h-full lg:w-auto lg:max-h-none lg:translate-x-0",
            isMobileSidebarOpen ? "translate-x-0" : "-translate-x-[110%] lg:translate-x-0",
          ].join(" ")}
        >
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500/80 dark:text-slate-400">
                Clinical Authority
              </p>
              <h2 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Precision Curator</h2>
            </div>
            <button
              type="button"
              onClick={() => setIsMobileSidebarOpen(false)}
              className="inline-flex min-h-[34px] min-w-[34px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-semibold text-[var(--text-secondary)] lg:hidden"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>

          <button
            type="button"
            onClick={createNewConversation}
            className="mt-3 inline-flex min-h-[40px] w-full items-center justify-center gap-1 rounded-xl border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 dark:text-cyan-300"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            New consultation
          </button>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {WORKSPACE_LEFT_VIEW_OPTIONS.map((option) => {
              const active = workspaceLeftView === option.id;
              return (
                <button
                  key={`mobile-${option.id}`}
                  type="button"
                  onClick={() => setWorkspaceLeftView(option.id)}
                  className={[
                    "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]",
                    active
                      ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
                  ].join(" ")}
                >
                  {option.title}
                </button>
              );
            })}
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Chats</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{effectiveSummary.conversations}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Messages</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{effectiveSummary.messages}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Notes</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{effectiveSummary.notes}</p>
            </div>
          </div>

          <div className="mt-3">
            <label htmlFor="workspace-search" className="text-xs font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
              Search
            </label>
            <div className="mt-1.5 flex gap-2">
              <input
                id="workspace-search"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Tìm nguồn, hội thoại, note..."
                className="min-h-[38px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[color:var(--shell-border-strong)]"
              />
              {searchText.trim() ? (
                <button
                  type="button"
                  onClick={() => setSearchText("")}
                  className="inline-flex min-h-[38px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                >
                  Clear
                </button>
              ) : null}
            </div>
            {isSearching ? <p className="mt-1 text-[11px] text-[var(--text-muted)]">Đang tìm...</p> : null}
          </div>

          <div className="mt-3 flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
            {(workspaceLeftView === "all" || workspaceLeftView === "chat") ? (
              <section className="rounded-xl bg-[var(--surface-muted)] p-2.5">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                  Folder
                </p>
                <div className="grid grid-cols-1 gap-2">
                  <select
                    value={String(selectedFolderFilterId ?? "none")}
                    onChange={(event) => {
                      const raw = event.target.value;
                      setSelectedFolderFilterId(raw === "none" ? null : Number(raw));
                    }}
                    className="min-h-[34px] rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 text-[11px] text-[var(--text-primary)]"
                  >
                    <option value="none">Folder: All</option>
                    {folderFilterList.map((folder) => (
                      <option key={`filter-folder-${folder.id}`} value={String(folder.id)}>
                        Folder: {folder.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsScopeManagerOpen(true)}
                    className="rounded border border-cyan-300/70 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-700 dark:text-cyan-300"
                  >
                    Manage folders
                  </button>
                  {selectedFolderFilterId !== null ? (
                    <button
                      type="button"
                      onClick={() => setSelectedFolderFilterId(null)}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Clear filter
                    </button>
                  ) : null}
                </div>
              </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "chat") ? (
            <section className="flex min-h-0 flex-1 flex-col rounded-xl bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Conversations</p>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-[var(--text-muted)]">
                    {visibleConversations.length}/{displayedConversations.length} chats · {displayedConversationMessageCount} msg
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsSelectionMode((prev) => !prev)}
                    className={[
                      "rounded border px-2 py-1 text-[10px] font-semibold",
                      isSelectionMode
                        ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"
                        : "border-[color:var(--shell-border)] text-[var(--text-secondary)]",
                    ].join(" ")}
                  >
                    {isSelectionMode ? "Done" : "Select"}
                  </button>
                </div>
              </div>
              {isSelectionMode && selectedConversationIds.length ? (
                <div className="mb-2 space-y-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                    Bulk actions
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <select
                      value={bulkFolderTarget}
                      disabled={workspaceApiUnavailable}
                      onChange={(event) => setBulkFolderTarget(event.target.value)}
                      className="min-h-[28px] rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 text-[10px] text-[var(--text-secondary)]"
                    >
                      <option value="skip">Folder: Skip</option>
                      <option value="none">Folder: None</option>
                      {folders.map((folder) => (
                        <option key={`bulk-folder-${folder.id}`} value={String(folder.id)}>
                          Folder: {folder.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={workspaceApiUnavailable}
                      onClick={() => {
                        if (bulkFolderTarget === "skip") return;
                        const folderId =
                          bulkFolderTarget === "none" ? null : Number(bulkFolderTarget);
                        void applyBulkMetaUpdate({ folderId });
                      }}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Apply folder
                    </button>
                    <button
                      type="button"
                      disabled={workspaceApiUnavailable}
                      onClick={() => void applyBulkMetaUpdate({ isFavorite: true })}
                      className="rounded border border-amber-300/70 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Favorite
                    </button>
                    <button
                      type="button"
                      disabled={workspaceApiUnavailable}
                      onClick={() => void applyBulkMetaUpdate({ isFavorite: false })}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Unfavorite
                    </button>
                    <button
                      type="button"
                      disabled={workspaceApiUnavailable}
                      onClick={() => void applyBulkMetaUpdate({ folderId: null })}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Clear folder
                    </button>
                    <button
                      type="button"
                      disabled={workspaceApiUnavailable}
                      onClick={() => void bulkExportSelectedConversations("markdown")}
                      className="rounded border border-cyan-300/70 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-700"
                    >
                      Export .md
                    </button>
                    <button
                      type="button"
                      onClick={() => void bulkExportSelectedConversations("docx")}
                      className="rounded border border-cyan-300/70 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold text-cyan-700"
                    >
                      Export .docx
                    </button>
                    <button
                      type="button"
                      onClick={() => void bulkDeleteSelectedConversations()}
                      className="rounded border border-rose-300/70 bg-rose-500/10 px-2 py-1 text-[10px] font-semibold text-rose-700"
                    >
                      Delete selected
                    </button>
                  </div>
                </div>
              ) : null}
              {isLoadingWorkspace || isLoadingConversations ? (
                <p className="text-xs text-[var(--text-muted)]">Đang tải...</p>
              ) : displayedConversations.length ? (
                <div
                  ref={conversationListViewportRef}
                  onScroll={onConversationListScroll}
                  className="min-h-0 flex-1 overflow-y-auto pr-1"
                >
                  <div
                    style={{ height: `${conversationVirtualizer.getTotalSize()}px` }}
                    className="relative w-full"
                  >
                    {conversationVirtualizer.getVirtualItems().map((virtualRow) => {
                      const row = conversationVirtualItems[virtualRow.index];
                      if (!row) return null;
                      const item = row.item;
                      const isActive = item.conversation_id === activeConversationId;
                      const isChecked = selectedConversationSet.has(item.conversation_id);
                      const isLocalOnly = localConversationIdSet.has(item.conversation_id);
                      const ts = toConversationTimestamp(item);
                      const timeLabel =
                        ts > 0
                          ? new Date(ts).toLocaleTimeString("vi-VN", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "--:--";
                      return (
                        <div
                          key={row.key}
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            transform: `translateY(${virtualRow.start}px)`,
                          }}
                          className="space-y-1.5 pb-1"
                        >
                          {row.dayLabel ? (
                            <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                              {row.dayLabel}
                            </p>
                          ) : null}
                          <div
                            draggable
                            onDragStart={() => onDragConversationStart(item.conversation_id)}
                            onDragEnd={onDragConversationEnd}
                            onClick={() => {
                              if (isSelectionMode) return;
                              void onSelectConversation(item);
                            }}
                            className={[
                              "w-full cursor-pointer rounded-lg border px-2.5 py-2 text-left",
                              isActive
                                ? "border-cyan-300/70 bg-cyan-500/10"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
                              draggingConversationId === item.conversation_id
                                ? "opacity-70"
                                : "",
                            ].join(" ")}
                          >
                            <div className="flex items-start gap-2">
                              {isSelectionMode ? (
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={(event) =>
                                    toggleConversationSelection(
                                      item.conversation_id,
                                      event.target.checked
                                    )
                                  }
                                  className="mt-0.5 h-3.5 w-3.5"
                                />
                              ) : null}
                              <button
                                type="button"
                                onClick={() => void onSelectConversation(item)}
                                className="flex-1 text-left"
                              >
                                <p className="line-clamp-2 text-xs font-semibold text-[var(--text-primary)]">
                                  {buildConversationPreview(item)}
                                </p>
                                <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                                  #{item.conversation_id} · {item.message_count} msg · {timeLabel}
                                  {item.is_favorite ? " · fav" : ""}
                                  {isLocalOnly ? " · local-cache" : ""}
                                </p>
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {visibleConversations.length < displayedConversations.length ? (
                    <p className="px-1 py-1 text-[10px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
                      Đang tải thêm conversations...
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">Không có conversation phù hợp filter hiện tại.</p>
              )}
            </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "notes") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Notes</p>
                <button
                  type="button"
                  onClick={() => void onCreateInlineNote(false)}
                  className="text-[11px] font-semibold text-cyan-700 dark:text-cyan-300"
                >
                  + Draft
                </button>
              </div>
              {(noteTitleDraft || noteMarkdownDraft || editingNoteId !== null) ? (
                <div className="mb-2 space-y-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
                  <input
                    value={noteTitleDraft}
                    onChange={(event) => setNoteTitleDraft(event.target.value)}
                    placeholder="Tiêu đề note"
                    className="min-h-[32px] w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-[11px] text-[var(--text-primary)]"
                  />
                  <textarea
                    value={noteMarkdownDraft}
                    onChange={(event) => setNoteMarkdownDraft(event.target.value)}
                    placeholder="Nội dung markdown"
                    className="min-h-[74px] w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1.5 text-[11px] text-[var(--text-primary)]"
                  />
                  <input
                    value={noteTagsDraft}
                    onChange={(event) => setNoteTagsDraft(event.target.value)}
                    placeholder="tags: warfarin, ddi,..."
                    className="min-h-[32px] w-full rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-[11px] text-[var(--text-primary)]"
                  />
                  <div className="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingNoteId(null);
                        setNoteTitleDraft("");
                        setNoteMarkdownDraft("");
                        setNoteTagsDraft("");
                      }}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      onClick={() => void onSaveNoteDraft()}
                      className="rounded border border-cyan-300/70 bg-cyan-500/10 px-2 py-1 text-[11px] font-semibold text-cyan-700 dark:text-cyan-300"
                    >
                      Save
                    </button>
                  </div>
                </div>
              ) : null}
              {displayedNotes.length ? (
                <ul className="space-y-1.5">
                  {displayedNotes.slice(0, 10).map((note) => (
                    <li key={note.id} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-2">
                      <p className="line-clamp-1 text-xs font-semibold text-[var(--text-primary)]">{note.title}</p>
                      <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">{note.summary || note.content_markdown || "(Trống)"}</p>
                      <div className="mt-1.5 flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => onEditNote(note)}
                          className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDeleteNote(note)}
                          className="rounded border border-rose-300/70 px-1.5 py-0.5 text-[10px] text-rose-600"
                        >
                          Del
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">Chưa có note.</p>
              )}
            </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "discover") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Suggestions</p>
              <div className="flex flex-wrap gap-1.5">
                {displayedSuggestions.length ? (
                  displayedSuggestions.slice(0, 12).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setQuery(item.text)}
                      className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]"
                    >
                      {item.text}
                    </button>
                  ))
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">Chưa có suggestion.</p>
                )}
              </div>
            </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "shares") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Shares</p>
                <Link
                  href="/chat/shares"
                  className="text-[11px] font-semibold text-cyan-700 dark:text-cyan-300"
                >
                  Manage
                </Link>
              </div>
              {workspaceApiUnavailable ? (
                <p className="text-xs text-[var(--text-muted)]">
                  Workspace API chưa sẵn sàng, share/public link đang tạm khóa.
                </p>
              ) : null}
              {!workspaceApiUnavailable && shares.length ? (
                <ul className="space-y-1.5">
                  {shares.slice(0, 8).map((item) => (
                    <li
                      key={`${item.conversation_id}-${item.share_token}`}
                      className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1.5"
                    >
                      <p className="line-clamp-1 text-[11px] font-semibold text-[var(--text-primary)]">
                        #{item.conversation_id} · {item.conversation_title}
                      </p>
                      <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                        {item.is_active ? "Active" : "Revoked"} · {item.message_count} messages
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        <button
                          type="button"
                          onClick={() => void onOpenConversationFromShare(item)}
                          className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          onClick={() => void copyText(item.public_url, "Đã copy public URL.")}
                          className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                        >
                          Copy
                        </button>
                        <a
                          href={item.public_url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded border border-cyan-300/70 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-700 dark:border-cyan-700/70 dark:text-cyan-300"
                        >
                          Visit
                        </a>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : !workspaceApiUnavailable ? (
                <p className="text-xs text-[var(--text-muted)]">Chưa có public share.</p>
              ) : null}
            </section>
            ) : null}
          </div>

          <div className="mt-3 border-t border-[color:var(--shell-border)] pt-3">
            <div className="relative">
              {accountMenuOpen ? (
                <div className="absolute bottom-full left-0 mb-2 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-xl">
                  <button
                    type="button"
                    onClick={onGoBack}
                    className="mb-1 inline-flex min-h-[34px] w-full items-center justify-start rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                  >
                    ← Go back
                  </button>
                  <Link
                    href="/dashboard"
                    className="mb-1 inline-flex min-h-[34px] w-full items-center justify-start rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                  >
                    Go to CLARA workspace
                  </Link>
                  <Link
                    href="/"
                    className="mb-1 inline-flex min-h-[34px] w-full items-center justify-start rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                  >
                    Go to CLARA website
                  </Link>
                  <button
                    type="button"
                    onClick={onLogout}
                    className="inline-flex min-h-[34px] w-full items-center justify-start rounded-lg border border-rose-300/70 bg-rose-500/10 px-3 text-xs font-semibold text-rose-700 dark:border-rose-700/70 dark:text-rose-300"
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => setAccountMenuOpen((prev) => !prev)}
                className="inline-flex min-h-[42px] w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3"
                aria-expanded={accountMenuOpen}
                aria-haspopup="menu"
              >
                <span className="inline-flex items-center gap-2">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-cyan-300/60 bg-cyan-500/10 text-[11px] font-bold text-cyan-700 dark:border-cyan-700/60 dark:text-cyan-300">
                    {accountRole.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="text-left">
                    <span className="block text-xs font-semibold text-[var(--text-primary)]">Account Manager</span>
                    <span className="block text-[10px] uppercase tracking-[0.08em] text-[var(--text-muted)]">{accountRole}</span>
                  </span>
                </span>
                <span className="text-xs text-[var(--text-muted)]">{accountMenuOpen ? "▲" : "▼"}</span>
              </button>
            </div>
          </div>
        </aside>

        <section className="flex h-full min-h-0 flex-col overflow-hidden border-x border-[color:var(--shell-border)] bg-[radial-gradient(circle_at_top_right,rgba(0,227,253,0.08),transparent_55%),var(--bg-canvas)]">
          <header className="sticky top-0 z-10 border-b border-[color:var(--shell-border)] bg-white/92 px-4 py-3 backdrop-blur-lg dark:bg-[#001f3d]/92 sm:px-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-start gap-2">
                <button
                  type="button"
                  onClick={() => setIsMobileSidebarOpen(true)}
                  className="inline-flex min-h-[36px] min-w-[36px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-sm font-semibold text-[var(--text-secondary)] lg:hidden"
                  aria-label="Mở sidebar"
                >
                  <span className="material-symbols-outlined text-base">menu</span>
                </button>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                    Clinical Lens AI
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Không gian làm việc trí tuệ lâm sàng</h2>
                  <div className="mt-1 hidden items-center gap-4 md:flex">
                    <span className="text-xs font-semibold text-cyan-700 dark:text-cyan-300">Dashboard</span>
                    <span className="text-xs font-semibold text-[var(--text-muted)]">Patient Records</span>
                    <span className="text-xs font-semibold text-[var(--text-muted)]">Analytics</span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={createNewConversation}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                >
                  New chat
                </button>
                <button
                  type="button"
                  disabled={!activeConversationId}
                  onClick={() => void onUpdateActiveConversationMeta({ isFavorite: !activeConversationMeta?.is_favorite })}
                  className={[
                    "inline-flex min-h-[36px] items-center rounded-lg border px-3 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60",
                    activeConversationMeta?.is_favorite
                      ? "border-amber-300/70 bg-amber-500/10 text-amber-700"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
                  ].join(" ")}
                >
                  {activeConversationMeta?.is_favorite ? "★ Favorited" : "☆ Favorite"}
                </button>
                <button
                  type="button"
                  onClick={() => void onExportActiveConversation("docx")}
                  disabled={!activeConversationId}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-emerald-300/75 bg-emerald-500/15 px-3 text-xs font-semibold text-emerald-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-700/70 dark:text-emerald-300"
                >
                  Xuất Word (.docx)
                </button>
                <button
                  type="button"
                  onClick={() => void onExportActiveConversation("markdown")}
                  disabled={!activeConversationId}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Export .md
                </button>
                <button
                  type="button"
                  onClick={() => void onShareActiveConversation()}
                  disabled={!activeConversationId || workspaceApiUnavailable}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-cyan-700/70 dark:text-cyan-300"
                >
                  Share public
                </button>

                <details className="group relative">
                  <summary className="inline-flex min-h-[36px] cursor-pointer list-none items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]">
                    More actions
                  </summary>
                  <div className="absolute right-0 z-20 mt-2 w-[19rem] space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-xl">
                    <div className="space-y-1.5">
                      <input
                        type="text"
                        value={conversationTitleDraft}
                        onChange={(event) => setConversationTitleDraft(event.target.value)}
                        disabled={!activeConversationId}
                        placeholder="Đặt tiêu đề conversation"
                        className="min-h-[34px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                      />
                      <button
                        type="button"
                        disabled={!activeConversationId || !conversationTitleDraft.trim()}
                        onClick={() => void onRenameActiveConversation()}
                        className="inline-flex min-h-[34px] w-full items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Rename
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => void onCreateInlineNote(true)}
                      disabled={!latestAnswer.trim()}
                      className="inline-flex min-h-[34px] w-full items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Save latest answer
                    </button>
                    <button
                      type="button"
                      onClick={() => void onRevokeShareActiveConversation()}
                      disabled={!activeConversationId || !shareInfo || workspaceApiUnavailable}
                      className="inline-flex min-h-[34px] w-full items-center justify-center rounded-lg border border-rose-300/70 bg-rose-500/10 px-3 text-xs font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-700/70 dark:text-rose-300"
                    >
                      Revoke share
                    </button>
                    <Link
                      href="/chat/shares"
                      className="inline-flex min-h-[34px] w-full items-center justify-center rounded-lg border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 dark:border-cyan-700/70 dark:text-cyan-300"
                    >
                      Manage shares
                    </Link>
                    <button
                      type="button"
                      onClick={() => void onDeleteActiveConversation()}
                      disabled={!activeConversationId}
                      className="inline-flex min-h-[34px] w-full items-center justify-center rounded-lg border border-rose-300/70 bg-rose-500/10 px-3 text-xs font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-700/70 dark:text-rose-300"
                    >
                      Delete chat
                    </button>
                  </div>
                </details>
              </div>
            </div>
            {workspaceApiUnavailable ? (
              <div className="mt-2 rounded-lg border border-amber-300/60 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:border-amber-700/60 dark:text-amber-200">
                Workspace API đang chạy chế độ tương thích. Lịch sử chat vẫn được giữ qua local cache; một số thao tác nâng cao (share/folder) tạm giới hạn.
              </div>
            ) : null}
            {shareInfo ? (
              <div className="mt-2 rounded-lg border border-cyan-300/50 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-800 dark:border-cyan-700/60 dark:text-cyan-200">
                <p className="font-semibold">Public link đang hoạt động</p>
                <p className="mt-1 break-all">{shareInfo.public_url}</p>
              </div>
            ) : null}
          </header>

          <div ref={conversationScrollRef} className="clara-scrollbar flex-1 min-h-0 overflow-y-auto py-4">
            <div className="mx-auto w-full max-w-[72rem] space-y-4 px-4 sm:px-6 lg:px-8">
              {isLoadingTurns && !conversationTurns.length ? (
                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  Đang tải nội dung conversation...
                </article>
              ) : null}

              {!conversationTurns.length && !isLoadingTurns ? (
                <article className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-5 text-sm leading-7 text-[var(--text-secondary)]">
                  Chưa có lượt chat nào. Bắt đầu bằng câu hỏi ở phần input phía dưới.
                </article>
              ) : (
                conversationTurns.map((turn) => <ChatTurn key={turn.id} turn={turn} />)
              )}
            </div>
          </div>

          <ChatComposer
            query={query}
            isSubmitting={isSubmitting}
            onChangeQuery={setQuery}
            onSubmit={onSubmit}
            quickPrompts={QUICK_PROMPTS}
            selectedResearchMode={selectedResearchMode}
            selectedRetrievalStackMode={selectedRetrievalStackMode}
            isFastResearchMode={isFastResearchMode}
            onChangeResearchMode={(mode) => {
              setSelectedResearchMode(mode);
              if (mode === "fast") {
                setSelectedRetrievalStackMode("auto");
              }
            }}
            onChangeRetrievalStackMode={setSelectedRetrievalStackMode}
            liveJobId={liveJobId}
            liveStatusNote={liveStatusNote}
            error={error}
            notice={notice}
          />
        </section>

        <aside className="clara-scrollbar hidden h-full flex-col overflow-y-auto border-l border-[color:var(--shell-border)] bg-[linear-gradient(180deg,rgba(255,255,255,0.7),rgba(241,244,247,0.7))] dark:bg-[linear-gradient(180deg,rgba(0,28,57,0.72),rgba(11,19,38,0.72))] 2xl:flex">
          <div className="border-b border-[color:var(--shell-border)] bg-white px-5 py-5 dark:bg-[#001f3d]/90">
            <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[var(--text-muted)]">
              System Telemetry
            </h3>

            <div className="mt-4 flex items-center gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
              <div className="relative h-11 w-11 shrink-0">
                <svg className="h-full w-full" viewBox="0 0 36 36">
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="currentColor"
                    className="text-[var(--surface-muted)]"
                    strokeWidth="3"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="currentColor"
                    className="text-cyan-500"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={`${confidenceRingPercent}, 100`}
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-black text-[var(--text-primary)]">
                  {confidenceDisplay}
                </span>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                  Confidence
                </p>
                <p className="text-sm font-extrabold text-[var(--text-primary)]">
                  {confidenceLabel}
                </p>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
                <span>Neural Load</span>
                <span>{neuralLoadPercent}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
                <div className="h-full rounded-full bg-cyan-500" style={{ width: `${neuralLoadPercent}%` }} />
              </div>
            </div>

            <div className="mt-4 space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
                Logic Flow
              </p>
              <div className="space-y-2.5 border-l border-[color:var(--shell-border)] pl-4">
                {logicFlowNodes.map((node, index) => {
                  const meta = logicFlowStatusMeta(node.status);
                  return (
                    <div key={`telemetry-flow-${node.id}-${index}`} className="relative">
                      <span className={["absolute -left-[19px] top-1 h-2.5 w-2.5 rounded-full", meta.dotClass].join(" ")} />
                      <p className={["text-xs font-bold", meta.labelClass].join(" ")}>{node.label}</p>
                      <p className={["text-[10px]", meta.detailClass].join(" ")}>
                        {node.detail || node.status.replaceAll("_", " ")}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-base font-extrabold text-[var(--text-primary)]">
                <span className="material-symbols-outlined text-cyan-500">source</span>
                Source Intel
              </h3>
              <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-black uppercase text-cyan-700 dark:text-cyan-300">
                {sourceIntel.activeCount} Active
              </span>
            </div>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-[var(--text-muted)]">
                search
              </span>
              <input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Tìm kiếm nguồn..."
                className="min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] pl-8 pr-3 text-sm text-[var(--text-primary)] outline-none focus:border-[color:var(--shell-border-strong)]"
              />
            </div>
          </div>

          <div className="clara-scrollbar flex-1 space-y-3 overflow-y-auto px-4 py-4">
            <p className="px-1 text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Global Medical Databases
            </p>
            {sourceIntelGlobal.length ? (
              sourceIntelGlobal.map((item, index) => (
                <div
                  key={`source-intel-global-${item.name}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="line-clamp-1 text-sm font-bold text-[var(--text-primary)]">{item.name}</p>
                    <span
                      className={[
                        "h-2 w-2 rounded-full",
                        item.status === "active"
                          ? "bg-emerald-500"
                          : item.status === "connecting"
                            ? "animate-pulse bg-amber-400"
                            : "bg-rose-500",
                      ].join(" ")}
                    />
                  </div>
                  <p className="mt-1 line-clamp-1 text-[10px] text-[var(--text-muted)]">
                    {item.query ? `Query: ${item.query}` : "Telemetry source from latest retrieval."}
                  </p>
                  <p className="mt-1 text-[9px] font-mono text-[var(--text-muted)]">
                    Status: {item.status.toUpperCase()} · attempts: {item.attempts}
                  </p>
                </div>
              ))
            ) : (
              <p className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3 text-xs text-[var(--text-muted)]">
                Chưa có telemetry source từ phiên chat hiện tại.
              </p>
            )}

            <p className="px-1 pt-2 text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
              MOH Vietnam Sources
            </p>
            {sourceIntelVietnam.length ? (
              sourceIntelVietnam.map((item, index) => (
                <div
                  key={`source-intel-vn-${item.name}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="line-clamp-1 text-sm font-bold text-[var(--text-primary)]">{item.name}</p>
                    <span
                      className={[
                        "h-2 w-2 rounded-full",
                        item.status === "active"
                          ? "bg-emerald-500"
                          : item.status === "connecting"
                            ? "animate-pulse bg-amber-400"
                            : "bg-rose-500",
                      ].join(" ")}
                    />
                  </div>
                  <p className="mt-1 text-[9px] font-mono text-[var(--text-muted)]">
                    Status: {item.status.toUpperCase()} · attempts: {item.attempts}
                  </p>
                </div>
              ))
            ) : (
              <p className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3 text-xs text-[var(--text-muted)]">
                Chưa ghi nhận source nội địa trong telemetry hiện tại.
              </p>
            )}
          </div>

          <div className="border-t border-[color:var(--shell-border)] bg-white/80 p-4 dark:bg-[#001f3d]/80">
            <div className="flex items-center gap-3 rounded-lg bg-[var(--surface-brand-soft)] px-3 py-2">
              <span className="material-symbols-outlined text-cyan-500">shield_lock</span>
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-primary)]">
                Verified Protocol Engine v4.2
              </p>
            </div>
          </div>
        </aside>
      </div>
        {isScopeManagerOpen ? (
          <div className="fixed inset-0 z-[68] flex items-start justify-center bg-slate-950/40 px-4 pt-[8vh] backdrop-blur-sm">
            <button
              type="button"
              aria-label="Đóng scope manager"
              onClick={() => setIsScopeManagerOpen(false)}
              className="absolute inset-0"
            />
            <div className="relative w-full max-w-3xl rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-2xl">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  Scope Manager
                </p>
                <button
                  type="button"
                  onClick={() => setIsScopeManagerOpen(false)}
                  className="inline-flex min-h-[30px] min-w-[30px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-semibold text-[var(--text-secondary)]"
                >
                  ✕
                </button>
              </div>

              <div className="mb-3 grid gap-2 sm:grid-cols-3">
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Folders</p>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{folders.length}</p>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Filter</p>
                  <p className="line-clamp-1 text-sm font-semibold text-[var(--text-primary)]">
                    {selectedFolderFilterId
                      ? folders.find((folder) => folder.id === selectedFolderFilterId)?.name || "Custom"
                      : "All folders"}
                  </p>
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Selected chats</p>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{selectedConversationIds.length}</p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <input
                    value={scopeFolderDraft}
                    onChange={(event) => setScopeFolderDraft(event.target.value)}
                    placeholder="Tên folder mới..."
                    className="min-h-[38px] flex-1 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)]"
                  />
                  <button
                    type="button"
                    onClick={() => void onCreateFolder()}
                    className="inline-flex min-h-[38px] items-center rounded-lg border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 dark:text-cyan-300"
                  >
                    + Create folder
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedFolderFilterId(null)}
                    className="inline-flex min-h-[38px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
                  >
                    Clear filter
                  </button>
                </div>

                <input
                  value={folderManagerSearch}
                  onChange={(event) => setFolderManagerSearch(event.target.value)}
                  placeholder="Tìm folder..."
                  className="min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)]"
                />

                <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
                  <div className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-2">
                    <button
                      type="button"
                      onClick={() => setSelectedFolderFilterId(null)}
                      className="line-clamp-1 text-left text-sm font-semibold text-[var(--text-primary)] hover:text-cyan-700"
                    >
                      All folders
                    </button>
                    <span className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-muted)]">
                      Filter reset
                    </span>
                  </div>

                  {folderManagerItems.map((folder) => (
                    <div
                      key={`scope-folder-${folder.id}`}
                      className={[
                        "flex items-center justify-between rounded-lg border bg-[var(--surface-muted)] px-2.5 py-2",
                        selectedFolderFilterId === folder.id
                          ? "border-cyan-300/70"
                          : "border-[color:var(--shell-border)]",
                      ].join(" ")}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedFolderFilterId(folder.id)}
                        className="line-clamp-1 text-left text-sm text-[var(--text-primary)] hover:text-cyan-700"
                      >
                        {folder.name}
                      </button>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => setSelectedFolderFilterId(folder.id)}
                          className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                        >
                          Filter
                        </button>
                        <button
                          type="button"
                          disabled={!activeConversationId || workspaceApiUnavailable}
                          onClick={() => void onUpdateActiveConversationMeta({ folderId: folder.id })}
                          className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[11px] text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Assign active
                        </button>
                        <button
                          type="button"
                          disabled={!selectedConversationIds.length || workspaceApiUnavailable}
                          onClick={() => void applyBulkMetaUpdate({ folderId: folder.id })}
                          className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[11px] text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Assign selected
                        </button>
                        <button
                          type="button"
                          onClick={() => void onRenameFolder(folder)}
                          className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDeleteFolder(folder)}
                          className="rounded border border-rose-300/70 px-2 py-1 text-[11px] text-rose-600"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                  {!folderManagerItems.length ? (
                    <p className="rounded-lg border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3 text-xs text-[var(--text-muted)]">
                      Không tìm thấy folder phù hợp.
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        ) : null}
        {isCommandPaletteOpen ? (
          <div className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-950/45 px-4 pt-[10vh] backdrop-blur-sm">
            <button
              type="button"
              aria-label="Đóng command palette"
              onClick={() => {
                setIsCommandPaletteOpen(false);
                setCommandPaletteQuery("");
              }}
              className="absolute inset-0"
            />
            <div className="relative w-full max-w-2xl rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-2xl">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  Command Palette
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setIsCommandPaletteOpen(false);
                    setCommandPaletteQuery("");
                  }}
                  className="inline-flex min-h-[30px] min-w-[30px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-semibold text-[var(--text-secondary)]"
                >
                  ✕
                </button>
              </div>
              <input
                id="chat-command-palette-input"
                value={commandPaletteQuery}
                onChange={(event) => setCommandPaletteQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    event.preventDefault();
                    setIsCommandPaletteOpen(false);
                    setCommandPaletteQuery("");
                    return;
                  }
                  if (event.key !== "Enter") return;
                  event.preventDefault();
                  const first = filteredCommandActions.find((item) => !item.disabled);
                  if (first) {
                    executeCommandAction(first);
                  }
                }}
                placeholder="Tìm hành động... (new chat, export docx, share...)"
                className="min-h-[42px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)] outline-none focus:border-[color:var(--shell-border-strong)]"
              />
              <div className="mt-2 max-h-[58vh] space-y-1 overflow-y-auto pr-1">
                {filteredCommandActions.length ? (
                  filteredCommandActions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      disabled={action.disabled}
                      onClick={() => executeCommandAction(action)}
                      className="flex min-h-[42px] w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-left text-sm text-[var(--text-primary)] transition hover:border-cyan-300/70 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <span>{action.label}</span>
                      {action.hint ? (
                        <span className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                          {action.hint}
                        </span>
                      ) : null}
                    </button>
                  ))
                ) : (
                  <p className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-4 text-sm text-[var(--text-muted)]">
                    Không có action phù hợp.
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
