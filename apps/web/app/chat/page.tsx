"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createConversationItem,
  createConversationItemFromPersisted,
} from "@/components/research/lib/research-page-helpers";
import { ConversationItem, ResearchResult } from "@/components/research/lib/research-page-types";
import ChatComposer from "@/components/chat-workspace/chat-composer";
import ChatTurn from "@/components/chat-workspace/chat-turn";
import PageShell from "@/components/ui/page-shell";
import {
  RESEARCH_TIER2_JOB_POLL_MS,
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
  appendResearchConversationMessage,
  createResearchConversation,
  createResearchTier2Job,
  getResearchTier2Job,
  listResearchConversationMessages,
  normalizeResearchTier2,
  normalizeResearchTier2JobProgress,
  streamResearchTier2Job,
} from "@/lib/research";
import {
  WorkspaceChannel,
  WorkspaceConversationShare,
  WorkspaceConversationItem,
  WorkspaceFolder,
  WorkspaceNote,
  WorkspaceSearchResponse,
  WorkspaceSuggestion,
  WorkspaceSummary,
  bulkUpdateWorkspaceConversationMeta,
  createWorkspaceConversationShare,
  createWorkspaceChannel,
  createWorkspaceFolder,
  createWorkspaceNote,
  deleteWorkspaceChannel,
  deleteWorkspaceConversation,
  deleteWorkspaceFolder,
  deleteWorkspaceNote,
  getWorkspaceConversationShare,
  getWorkspaceSummary,
  listWorkspaceChannels,
  listWorkspaceConversations,
  listWorkspaceFolders,
  listWorkspaceNotes,
  exportWorkspaceConversation,
  listWorkspaceSuggestions,
  revokeWorkspaceConversationShare,
  searchWorkspace,
  updateWorkspaceChannel,
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

const JOB_FETCH_RETRY_ATTEMPTS = 3;
const JOB_FETCH_RETRY_BACKOFF_MS = 600;
const JOB_COMPLETED_RESULT_REFETCH_ATTEMPTS = 5;
const JOB_COMPLETED_RESULT_REFETCH_MS = 900;

type WorkspaceLeftView = "all" | "chat" | "library" | "notes" | "discover";

const WORKSPACE_LEFT_VIEW_OPTIONS: Array<{
  id: WorkspaceLeftView;
  label: string;
  title: string;
}> = [
  { id: "all", label: "AL", title: "All" },
  { id: "chat", label: "CH", title: "Chat" },
  { id: "library", label: "LB", title: "Library" },
  { id: "notes", label: "NT", title: "Notes" },
  { id: "discover", label: "DS", title: "Discover" },
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

function latestAnswerFromTurn(turn: ConversationItem | null): string {
  if (!turn) return "";
  const result = turn.result;
  return result.answer || "";
}

function asConversationId(value: number | null): number | null {
  if (!Number.isFinite(value) || value === null || value <= 0) return null;
  return Math.trunc(value);
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

const fetchTier2JobWithRetry = async (jobId: string) => {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= JOB_FETCH_RETRY_ATTEMPTS; attempt += 1) {
    try {
      return await getResearchTier2Job(jobId);
    } catch (error) {
      lastError = error;
      if (attempt < JOB_FETCH_RETRY_ATTEMPTS) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, JOB_FETCH_RETRY_BACKOFF_MS * attempt);
        });
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Không thể tải trạng thái research job.");
};

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
  const [channels, setChannels] = useState<WorkspaceChannel[]>([]);
  const [conversations, setConversations] = useState<WorkspaceConversationItem[]>([]);
  const [notes, setNotes] = useState<WorkspaceNote[]>([]);
  const [suggestions, setSuggestions] = useState<WorkspaceSuggestion[]>([]);
  const [searchResult, setSearchResult] = useState<WorkspaceSearchResponse | null>(null);
  const [shareInfo, setShareInfo] = useState<WorkspaceConversationShare | null>(null);

  const [newFolderName, setNewFolderName] = useState("");
  const [newChannelName, setNewChannelName] = useState("");
  const [noteTitleDraft, setNoteTitleDraft] = useState("");
  const [noteMarkdownDraft, setNoteMarkdownDraft] = useState("");
  const [noteTagsDraft, setNoteTagsDraft] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [conversationTitleDraft, setConversationTitleDraft] = useState("");

  const [selectedFolderFilterId, setSelectedFolderFilterId] = useState<number | null>(null);
  const [selectedChannelFilterId, setSelectedChannelFilterId] = useState<number | null>(null);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [bulkFolderTarget, setBulkFolderTarget] = useState<string>("skip");
  const [bulkChannelTarget, setBulkChannelTarget] = useState<string>("skip");

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

  const isFastResearchMode = selectedResearchMode === "fast";
  const conversationScrollRef = useRef<HTMLDivElement | null>(null);

  const latestTurn = useMemo(
    () => (conversationTurns.length ? conversationTurns[conversationTurns.length - 1] : null),
    [conversationTurns]
  );
  const latestAnswer = useMemo(() => latestAnswerFromTurn(latestTurn), [latestTurn]);
  const selectedConversationSet = useMemo(
    () => new Set(selectedConversationIds),
    [selectedConversationIds]
  );

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
      const items = await listWorkspaceConversations({
        limit: 80,
        folderId: selectedFolderFilterId ?? undefined,
        channelId: selectedChannelFilterId ?? undefined,
        favoritesOnly,
      });
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
      setError(cause instanceof Error ? cause.message : "Không thể tải danh sách hội thoại workspace.");
      return [];
    } finally {
      setIsLoadingConversations(false);
    }
  }, [activeConversationId, favoritesOnly, selectedChannelFilterId, selectedFolderFilterId]);

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

  const loadStaticWorkspaceData = useCallback(async () => {
    setIsLoadingWorkspace(true);
    setError("");
    try {
      const [nextSummary, nextFolders, nextChannels] = await Promise.all([
        getWorkspaceSummary(),
        listWorkspaceFolders(false),
        listWorkspaceChannels(false),
      ]);
      setSummary(nextSummary);
      setFolders(nextFolders);
      setChannels(nextChannels);
      await Promise.all([loadNotes(), loadSuggestions(), loadConversations()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải workspace chat.");
    } finally {
      setIsLoadingWorkspace(false);
    }
  }, [loadConversations, loadNotes, loadSuggestions]);

  const loadConversationTurns = useCallback(async (conversationId: number, fallbackItem?: WorkspaceConversationItem) => {
    setIsLoadingTurns(true);
    try {
      const rows = await listResearchConversationMessages(conversationId, 180);
      if (!rows.length) {
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
      setConversationTurns([]);
      setError(cause instanceof Error ? cause.message : "Không thể tải tin nhắn của conversation.");
    } finally {
      setIsLoadingTurns(false);
    }
  }, []);

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
    return conversations;
  }, [conversations, searchResult]);

  useEffect(() => {
    if (!selectedConversationIds.length) return;
    const visible = new Set(displayedConversations.map((item) => item.conversation_id));
    setSelectedConversationIds((prev) => prev.filter((id) => visible.has(id)));
  }, [displayedConversations, selectedConversationIds.length]);

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

  const channelFilterList = useMemo(() => {
    if (searchResult?.channels?.length) return searchResult.channels;
    return channels;
  }, [channels, searchResult]);

  const setConversationMetaPatch = useCallback(
    (conversationId: number, patch: Partial<WorkspaceConversationItem>) => {
      setConversations((prev) =>
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

  const selectAllDisplayedConversations = useCallback(() => {
    setSelectedConversationIds(displayedConversations.map((item) => item.conversation_id));
  }, [displayedConversations]);

  const clearConversationSelection = useCallback(() => {
    setSelectedConversationIds([]);
  }, []);

  const applyBulkMetaUpdate = useCallback(
    async (payload: { folderId?: number | null; channelId?: number | null; isFavorite?: boolean }) => {
      if (!selectedConversationIds.length) {
        setNotice("Hãy chọn conversation trước khi chạy bulk action.");
        return;
      }
      try {
        const result = await bulkUpdateWorkspaceConversationMeta({
          conversationIds: selectedConversationIds,
          folderId: payload.folderId,
          channelId: payload.channelId,
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
                  channel_id:
                    payload.channelId !== undefined
                      ? (payload.channelId ?? null)
                      : item.channel_id,
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
                    channel_id:
                      payload.channelId !== undefined
                        ? (payload.channelId ?? null)
                        : item.channel_id,
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
              channel_id:
                payload.channelId !== undefined ? (payload.channelId ?? null) : prev.channel_id,
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
    [activeConversationId, refreshSummary, selectedConversationIds]
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
        await deleteWorkspaceConversation(conversationId);
        deletedCount += 1;
      } catch {
        // Continue deleting remaining items.
      }
    }
    setSelectedConversationIds([]);
    if (activeConversationId && selectedConversationIds.includes(activeConversationId)) {
      setActiveConversationId(null);
      setActiveConversationMeta(null);
      setConversationTurns([]);
    }
    await Promise.all([loadConversations(), refreshSummary()]);
    setNotice(`Đã xóa ${deletedCount}/${selectedConversationIds.length} conversation.`);
  }, [activeConversationId, loadConversations, refreshSummary, selectedConversationIds]);

  const bulkExportSelectedConversations = useCallback(
    async (format: "markdown" | "docx") => {
      if (!selectedConversationIds.length) {
        setNotice("Hãy chọn conversation trước khi export.");
        return;
      }
      let successCount = 0;
      for (const conversationId of selectedConversationIds) {
        try {
          const blob = await exportWorkspaceConversation(conversationId, format);
          triggerBlobDownload(blob, `conversation-${conversationId}.${format === "markdown" ? "md" : "docx"}`);
          successCount += 1;
        } catch {
          // Keep exporting remaining conversations.
        }
      }
      setNotice(`Đã export ${successCount}/${selectedConversationIds.length} conversation (${format}).`);
    },
    [selectedConversationIds]
  );

  const onSelectConversation = useCallback(
    async (item: WorkspaceConversationItem) => {
      const conversationId = asConversationId(item.conversation_id);
      if (!conversationId) return;
      setActiveConversationId(conversationId);
      setActiveConversationMeta(item);
      setError("");
      setLiveJobId(null);
      setLiveStatusNote("");
      await loadConversationTurns(conversationId, item);
      try {
        await updateWorkspaceConversationMeta(conversationId, { touched: true });
      } catch {
        // Ignore touched update failure.
      }
    },
    [loadConversationTurns]
  );

  const onDragConversationStart = (conversationId: number) => {
    setDraggingConversationId(conversationId);
  };

  const onDragConversationEnd = () => {
    setDraggingConversationId(null);
  };

  const onDropConversationToFolder = async (folderId: number | null) => {
    if (!draggingConversationId) return;
    try {
      const updated = await updateWorkspaceConversationMeta(draggingConversationId, {
        folderId,
        touched: false,
      });
      setConversationMetaPatch(draggingConversationId, {
        folder_id: updated.folder_id ?? null,
        channel_id: updated.channel_id ?? null,
        is_favorite: updated.is_favorite,
      });
      await refreshSummary();
      setNotice(`Đã chuyển conversation #${draggingConversationId} sang folder.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể drag & drop vào folder.");
    } finally {
      setDraggingConversationId(null);
    }
  };

  const onDropConversationToChannel = async (channelId: number | null) => {
    if (!draggingConversationId) return;
    try {
      const updated = await updateWorkspaceConversationMeta(draggingConversationId, {
        channelId,
        touched: false,
      });
      setConversationMetaPatch(draggingConversationId, {
        folder_id: updated.folder_id ?? null,
        channel_id: updated.channel_id ?? null,
        is_favorite: updated.is_favorite,
      });
      await refreshSummary();
      setNotice(`Đã chuyển conversation #${draggingConversationId} sang channel.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể drag & drop vào channel.");
    } finally {
      setDraggingConversationId(null);
    }
  };

  const createNewConversation = () => {
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
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isSubmitting) return;

    setIsSubmitting(true);
    setError("");

    try {
      const job = await createResearchTier2Job(message, {
        researchMode: selectedResearchMode,
        retrievalStackMode: selectedRetrievalStackMode,
      });
      setLiveJobId(job.job_id);

      let currentJob = job;
      let finalPayload: Record<string, unknown> | null = null;

      const applyLiveSnapshot = (snapshot: typeof currentJob) => {
        const progress = normalizeResearchTier2JobProgress(snapshot.progress);
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
        setLiveStatusNote(`${streamError} Đang fallback sang polling.`);
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
          await new Promise((resolve) => {
            window.setTimeout(resolve, JOB_COMPLETED_RESULT_REFETCH_MS);
          });
          currentJob = await fetchTier2JobWithRetry(job.job_id);
          applyLiveSnapshot(currentJob);
          if (hasFinalResultObject(currentJob.result)) {
            finalPayload = currentJob.result;
            break;
          }
        }
      }

      if (!finalPayload) {
        throw new Error("Không nhận được kết quả cuối từ research job.");
      }

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
        const fallbackConversationId = targetConversationId ?? null;
        targetConversationId = fallbackConversationId;
        setError(
          persistError instanceof Error
            ? `Đã trả lời nhưng lưu hội thoại thất bại: ${persistError.message}`
            : "Đã trả lời nhưng lưu hội thoại thất bại."
        );
      }

      if (targetConversationId) {
        setActiveConversationId(targetConversationId);
        if (didPersistConversation) {
          await loadConversationTurns(targetConversationId);
        }
      }

      setQuery("");
      setLiveJobId(null);
      setLiveStatusNote("");
      const [refreshedItems] = await Promise.all([
        loadConversations(targetConversationId),
        refreshSummary(),
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
    channelId?: number | null;
    isFavorite?: boolean;
  }) => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;

    try {
      const updated = await updateWorkspaceConversationMeta(conversationId, payload);
      setConversationMetaPatch(conversationId, {
        folder_id: updated.folder_id ?? null,
        channel_id: updated.channel_id ?? null,
        is_favorite: updated.is_favorite,
      });
      await refreshSummary();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật metadata conversation.");
    }
  };

  const onCreateFolder = async () => {
    const name = parsePromptText(newFolderName);
    if (!name) return;
    try {
      const created = await createWorkspaceFolder({ name });
      setFolders((prev) => [created, ...prev]);
      setNewFolderName("");
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

  const onCreateChannel = async () => {
    const name = parsePromptText(newChannelName);
    if (!name) return;
    try {
      const created = await createWorkspaceChannel({ name });
      setChannels((prev) => [created, ...prev]);
      setNewChannelName("");
      await refreshSummary();
      setNotice(`Đã tạo channel \"${created.name}\".`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo channel.");
    }
  };

  const onRenameChannel = async (channel: WorkspaceChannel) => {
    const name = parsePromptText(window.prompt("Đổi tên channel", channel.name));
    if (!name) return;
    try {
      const updated = await updateWorkspaceChannel(channel.id, { name });
      setChannels((prev) => prev.map((item) => (item.id === channel.id ? updated : item)));
      setNotice(`Đã cập nhật channel \"${updated.name}\".`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đổi tên channel.");
    }
  };

  const onDeleteChannel = async (channel: WorkspaceChannel) => {
    const confirmed = window.confirm(`Xóa channel "${channel.name}"?`);
    if (!confirmed) return;
    try {
      await deleteWorkspaceChannel(channel.id);
      setChannels((prev) => prev.filter((item) => item.id !== channel.id));
      if (selectedChannelFilterId === channel.id) setSelectedChannelFilterId(null);
      await refreshSummary();
      setNotice("Đã xóa channel.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xóa channel.");
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

    try {
      const share = await createWorkspaceConversationShare(conversationId, {
        expiresInHours: 168,
        rotate: false,
      });
      setShareInfo(share);
      if (navigator?.clipboard) {
        await navigator.clipboard.writeText(share.public_url);
        setNotice("Đã copy link share public.");
      } else {
        window.prompt("Copy link share public", share.public_url);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể chia sẻ conversation.");
    }
  };

  const onRevokeShareActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    try {
      await revokeWorkspaceConversationShare(conversationId);
      setShareInfo(null);
      setNotice("Đã thu hồi liên kết public.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể thu hồi liên kết.");
    }
  };

  const onExportActiveConversation = async (format: "markdown" | "docx") => {
    const conversationId = asConversationId(activeConversationId);
    if (!conversationId) return;
    try {
      const blob = await exportWorkspaceConversation(conversationId, format);
      triggerBlobDownload(blob, `conversation-${conversationId}.${format === "markdown" ? "md" : "docx"}`);
      setNotice(`Đã export conversation #${conversationId} (${format}).`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể export conversation.");
    }
  };

  const onRenameActiveConversation = async () => {
    const conversationId = asConversationId(activeConversationId);
    const title = parsePromptText(conversationTitleDraft);
    if (!conversationId || !title) return;
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
    try {
      await deleteWorkspaceConversation(conversationId);
      setConversations((prev) => prev.filter((item) => item.conversation_id !== conversationId));
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

  const activeFolderValue = String(activeConversationMeta?.folder_id ?? "none");
  const activeChannelValue = String(activeConversationMeta?.channel_id ?? "none");

  return (
    <PageShell
      variant="plain"
      title="Chat Workspace"
      description="OpenWebUI-style workspace: rail điều hướng, conversation canvas, notes/search/suggestions và composer luôn hiển thị."
    >
      <div className="grid min-h-[78dvh] gap-4 lg:grid-cols-[3.4rem_22rem_minmax(0,1fr)]">
        <aside className="chrome-panel hidden max-h-[82dvh] flex-col items-center justify-between rounded-[1.35rem] px-2 py-3 lg:flex">
          <div className="flex w-full flex-col gap-2">
            {WORKSPACE_LEFT_VIEW_OPTIONS.map((option) => {
              const active = workspaceLeftView === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  title={option.title}
                  onClick={() => setWorkspaceLeftView(option.id)}
                  className={[
                    "inline-flex min-h-[40px] w-full items-center justify-center rounded-xl border text-[11px] font-semibold tracking-[0.08em] transition",
                    active
                      ? "border-cyan-300/70 bg-cyan-500/15 text-cyan-700 dark:text-cyan-300"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-cyan-300/55",
                  ].join(" ")}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-2 text-center text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
            OpenUI
          </div>
        </aside>

        <aside className="chrome-panel flex max-h-[82dvh] flex-col overflow-hidden rounded-[1.35rem] p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Workspace</h2>
            <button
              type="button"
              onClick={createNewConversation}
              className="inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
            >
              + New
            </button>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5 lg:hidden">
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
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Conv</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.conversations ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Msg</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.messages ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Notes</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.notes ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Pinned</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.pinned_notes ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Folders</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.folders ?? "-"}</p>
            </div>
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Channels</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{summary?.channels ?? "-"}</p>
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
                placeholder="Tìm conversation, note..."
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

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setFavoritesOnly((prev) => !prev)}
              className={[
                "inline-flex min-h-[34px] items-center rounded-full border px-3 text-xs font-semibold",
                favoritesOnly
                  ? "border-amber-300/70 bg-amber-500/10 text-amber-700"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
              ].join(" ")}
            >
              Favorites only
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedFolderFilterId(null);
                setSelectedChannelFilterId(null);
                setFavoritesOnly(false);
              }}
              className="inline-flex min-h-[34px] items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
            >
              Reset filters
            </button>
          </div>

          <div className="mt-3 flex-1 space-y-3 overflow-y-auto pr-1">
            {(workspaceLeftView === "all" || workspaceLeftView === "library") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Folders</p>
                <span className="text-[11px] text-[var(--text-muted)]">{folders.length}</span>
              </div>
              <div className="mb-2 flex gap-1.5">
                <input
                  value={newFolderName}
                  onChange={(event) => setNewFolderName(event.target.value)}
                  placeholder="Tên folder..."
                  className="min-h-[34px] flex-1 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-[11px] text-[var(--text-primary)]"
                />
                <button
                  type="button"
                  onClick={() => void onCreateFolder()}
                  className="inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-[11px] font-semibold text-[var(--text-secondary)]"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setSelectedFolderFilterId(null)}
                  onDragOver={(event) => {
                    event.preventDefault();
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    void onDropConversationToFolder(null);
                  }}
                  className={[
                    "rounded-full border px-2.5 py-1 text-[11px]",
                    selectedFolderFilterId === null
                      ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-800"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                  ].join(" ")}
                >
                  All
                </button>
                {folderFilterList.map((folder) => (
                  <button
                    key={folder.id}
                    type="button"
                    onClick={() => setSelectedFolderFilterId(folder.id)}
                    onDragOver={(event) => {
                      event.preventDefault();
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      void onDropConversationToFolder(folder.id);
                    }}
                    className={[
                      "rounded-full border px-2.5 py-1 text-[11px]",
                      selectedFolderFilterId === folder.id
                        ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-800"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                      draggingConversationId ? "ring-1 ring-cyan-300/60" : "",
                    ].join(" ")}
                  >
                    {folder.name}
                  </button>
                ))}
              </div>
              {folders.length ? (
                <ul className="mt-2 space-y-1.5">
                  {folders.slice(0, 8).map((folder) => (
                    <li
                      key={`manage-folder-${folder.id}`}
                      className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1.5"
                    >
                      <span className="line-clamp-1 text-[11px] text-[var(--text-secondary)]">{folder.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void onRenameFolder(folder)}
                          className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDeleteFolder(folder)}
                          className="rounded border border-rose-300/70 px-1.5 py-0.5 text-[10px] text-rose-600"
                        >
                          Del
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "library") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Channels</p>
                <span className="text-[11px] text-[var(--text-muted)]">{channels.length}</span>
              </div>
              <div className="mb-2 flex gap-1.5">
                <input
                  value={newChannelName}
                  onChange={(event) => setNewChannelName(event.target.value)}
                  placeholder="Tên channel..."
                  className="min-h-[34px] flex-1 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-[11px] text-[var(--text-primary)]"
                />
                <button
                  type="button"
                  onClick={() => void onCreateChannel()}
                  className="inline-flex min-h-[34px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-[11px] font-semibold text-[var(--text-secondary)]"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setSelectedChannelFilterId(null)}
                  onDragOver={(event) => {
                    event.preventDefault();
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    void onDropConversationToChannel(null);
                  }}
                  className={[
                    "rounded-full border px-2.5 py-1 text-[11px]",
                    selectedChannelFilterId === null
                      ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-800"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                  ].join(" ")}
                >
                  All
                </button>
                {channelFilterList.map((channel) => (
                  <button
                    key={channel.id}
                    type="button"
                    onClick={() => setSelectedChannelFilterId(channel.id)}
                    onDragOver={(event) => {
                      event.preventDefault();
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      void onDropConversationToChannel(channel.id);
                    }}
                    className={[
                      "rounded-full border px-2.5 py-1 text-[11px]",
                      selectedChannelFilterId === channel.id
                        ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-800"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                      draggingConversationId ? "ring-1 ring-cyan-300/60" : "",
                    ].join(" ")}
                  >
                    #{channel.name}
                  </button>
                ))}
              </div>
              {channels.length ? (
                <ul className="mt-2 space-y-1.5">
                  {channels.slice(0, 8).map((channel) => (
                    <li
                      key={`manage-channel-${channel.id}`}
                      className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1.5"
                    >
                      <span className="line-clamp-1 text-[11px] text-[var(--text-secondary)]">#{channel.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void onRenameChannel(channel)}
                          className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDeleteChannel(channel)}
                          className="rounded border border-rose-300/70 px-1.5 py-0.5 text-[10px] text-rose-600"
                        >
                          Del
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
            ) : null}

            {(workspaceLeftView === "all" || workspaceLeftView === "chat") ? (
            <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">Conversations</p>
                <span className="text-[11px] text-[var(--text-muted)]">{displayedConversations.length}</span>
              </div>
              <div className="mb-2 flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={selectAllDisplayedConversations}
                  className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={clearConversationSelection}
                  className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                >
                  Clear
                </button>
                <span className="inline-flex items-center rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-[10px] text-[var(--text-muted)]">
                  Selected: {selectedConversationIds.length}
                </span>
              </div>
              {selectedConversationIds.length ? (
                <div className="mb-2 space-y-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                    Bulk actions
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <select
                      value={bulkFolderTarget}
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
                      onClick={() => {
                        if (bulkFolderTarget === "skip") return;
                        const folderId =
                          bulkFolderTarget === "none" ? null : Number(bulkFolderTarget);
                        void applyBulkMetaUpdate({ folderId });
                      }}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Apply folder
                    </button>
                    <select
                      value={bulkChannelTarget}
                      onChange={(event) => setBulkChannelTarget(event.target.value)}
                      className="min-h-[28px] rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 text-[10px] text-[var(--text-secondary)]"
                    >
                      <option value="skip">Channel: Skip</option>
                      <option value="none">Channel: None</option>
                      {channels.map((channel) => (
                        <option key={`bulk-channel-${channel.id}`} value={String(channel.id)}>
                          Channel: #{channel.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => {
                        if (bulkChannelTarget === "skip") return;
                        const channelId =
                          bulkChannelTarget === "none" ? null : Number(bulkChannelTarget);
                        void applyBulkMetaUpdate({ channelId });
                      }}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Apply channel
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyBulkMetaUpdate({ isFavorite: true })}
                      className="rounded border border-amber-300/70 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-700"
                    >
                      Favorite
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyBulkMetaUpdate({ isFavorite: false })}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Unfavorite
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyBulkMetaUpdate({ folderId: null })}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Clear folder
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyBulkMetaUpdate({ channelId: null })}
                      className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-[10px] text-[var(--text-secondary)]"
                    >
                      Clear channel
                    </button>
                    <button
                      type="button"
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
                <ul className="space-y-1.5">
                  {displayedConversations.slice(0, 30).map((item) => {
                    const isActive = item.conversation_id === activeConversationId;
                    const isChecked = selectedConversationSet.has(item.conversation_id);
                    return (
                      <li key={item.conversation_id}>
                        <div
                          draggable
                          onDragStart={() => onDragConversationStart(item.conversation_id)}
                          onDragEnd={onDragConversationEnd}
                          className={[
                            "w-full rounded-lg border px-2.5 py-2 text-left",
                            isActive
                              ? "border-cyan-300/70 bg-cyan-500/10"
                              : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
                            draggingConversationId === item.conversation_id
                              ? "opacity-70"
                              : "",
                          ].join(" ")}
                        >
                          <div className="flex items-start gap-2">
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
                            <button
                              type="button"
                              onClick={() => void onSelectConversation(item)}
                              className="flex-1 text-left"
                            >
                              <p className="line-clamp-2 text-xs font-semibold text-[var(--text-primary)]">
                                {buildConversationPreview(item)}
                              </p>
                              <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                                #{item.conversation_id} ·{" "}
                                {item.is_favorite ? "fav" : "normal"} ·{" "}
                                {new Date(item.created_at).toLocaleDateString("vi-VN")}
                              </p>
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
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
          </div>
        </aside>

        <section className="chrome-panel flex min-h-[82dvh] flex-col overflow-hidden rounded-[1.35rem] p-4 sm:p-5">
          <header className="border-b border-[color:var(--shell-border)] pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Active Conversation</p>
                <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
                  {activeConversationMeta
                    ? `#${activeConversationMeta.conversation_id} · ${buildConversationPreview(activeConversationMeta)}`
                    : "New conversation"}
                </h2>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={conversationTitleDraft}
                  onChange={(event) => setConversationTitleDraft(event.target.value)}
                  disabled={!activeConversationId}
                  placeholder="Đặt tiêu đề conversation"
                  className="min-h-[36px] min-w-[220px] rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                />
                <button
                  type="button"
                  disabled={!activeConversationId || !conversationTitleDraft.trim()}
                  onClick={() => void onRenameActiveConversation()}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Rename
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
                  {activeConversationMeta?.is_favorite ? "★ Favorite" : "☆ Favorite"}
                </button>

                <button
                  type="button"
                  onClick={() => void onCreateInlineNote(true)}
                  disabled={!latestAnswer.trim()}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Save latest answer
                </button>

                <button
                  type="button"
                  onClick={() => void onShareActiveConversation()}
                  disabled={!activeConversationId}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-cyan-700/70 dark:text-cyan-300"
                >
                  Share public
                </button>
                <button
                  type="button"
                  onClick={() => void onRevokeShareActiveConversation()}
                  disabled={!activeConversationId || !shareInfo}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-rose-300/70 bg-rose-500/10 px-3 text-xs font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-700/70 dark:text-rose-300"
                >
                  Revoke share
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
                  onClick={() => void onExportActiveConversation("docx")}
                  disabled={!activeConversationId}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Export .docx
                </button>
                <Link
                  href="/chat/shares"
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-cyan-300/70 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-700 dark:border-cyan-700/70 dark:text-cyan-300"
                >
                  Manage shares
                </Link>
                <button
                  type="button"
                  onClick={() => void onDeleteActiveConversation()}
                  disabled={!activeConversationId}
                  className="inline-flex min-h-[36px] items-center rounded-lg border border-rose-300/70 bg-rose-500/10 px-3 text-xs font-semibold text-rose-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-700/70 dark:text-rose-300"
                >
                  Delete chat
                </button>
              </div>
            </div>
            {shareInfo ? (
              <div className="mt-2 rounded-lg border border-cyan-300/50 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-800 dark:border-cyan-700/60 dark:text-cyan-200">
                <p className="font-semibold">Public link đang hoạt động</p>
                <p className="mt-1 break-all">{shareInfo.public_url}</p>
              </div>
            ) : null}

            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <label htmlFor="active-folder" className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                  Folder
                </label>
                <select
                  id="active-folder"
                  value={activeFolderValue}
                  disabled={!activeConversationId}
                  onChange={(event) => {
                    const raw = event.target.value;
                    const folderId = raw === "none" ? null : Number(raw);
                    void onUpdateActiveConversationMeta({ folderId });
                  }}
                  className="mt-1 min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="none">No folder</option>
                  {folders.map((folder) => (
                    <option key={folder.id} value={String(folder.id)}>
                      {folder.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="active-channel" className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                  Channel
                </label>
                <select
                  id="active-channel"
                  value={activeChannelValue}
                  disabled={!activeConversationId}
                  onChange={(event) => {
                    const raw = event.target.value;
                    const channelId = raw === "none" ? null : Number(raw);
                    void onUpdateActiveConversationMeta({ channelId });
                  }}
                  className="mt-1 min-h-[36px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-sm text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="none">No channel</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={String(channel.id)}>
                      #{channel.name}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => void onCreateFolder()}
                className="mt-[1.1rem] inline-flex min-h-[36px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
              >
                + Folder
              </button>

              <button
                type="button"
                onClick={() => void onCreateChannel()}
                className="mt-[1.1rem] inline-flex min-h-[36px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
              >
                + Channel
              </button>
            </div>
          </header>

          <div ref={conversationScrollRef} className="flex-1 space-y-4 overflow-y-auto py-4 pr-1">
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
      </div>
    </PageShell>
  );
}
