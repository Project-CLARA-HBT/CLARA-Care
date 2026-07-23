"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { getRole, type UserRole } from "@/lib/auth-store";
import { beginLogout } from "@/lib/logout";
import { getNavItemsByRole } from "@/lib/navigation.config";
import { trackChatMessageSent } from "@/lib/analytics/events";
import { sanitizeUpstreamError, toModeLabel } from "@/lib/user-facing-text";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import {
  applyThemePreference,
  saveThemePreference,
  type ThemePreference,
} from "@/lib/theme";
import {
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
  appendResearchConversationMessage,
  createResearchConversation,
  resolveChatTransport,
} from "@/lib/research";
import {
  WorkspaceConversationItem,
  searchWorkspace,
  updateWorkspaceConversationMeta,
} from "@/lib/workspace";
import { createConversationItem } from "@/components/research/lib/research-page-helpers";

import { useChatStream } from "@/app/chat/_v2/hooks/useChatStream";
import { useChatTurns } from "@/app/chat/_v2/hooks/useChatTurns";
import { useConversations } from "@/app/chat/_v2/hooks/useConversations";
import { useWorkspace } from "@/app/chat/_v2/hooks/useWorkspace";
import {
  useCommandPalette,
  type CommandAction,
} from "@/app/chat/_v2/hooks/useCommandPalette";
import {
  asConversationId,
  isEditableElement,
  latestAnswerFromTurn,
} from "@/app/chat/_v2/lib/chat-format";

import ConversationSidebar from "@/app/chat/_v2/components/ConversationSidebar";
import MessageLog from "@/app/chat/_v2/components/MessageLog";
import Composer from "@/app/chat/_v2/components/Composer";
import ChatWelcome from "@/app/chat/_v2/components/ChatWelcome";
import CommandPaletteLazy from "@/app/chat/_v2/components/CommandPaletteLazy";
import WorkspaceDrawerLazy from "@/app/chat/_v2/components/WorkspaceDrawerLazy";
import TelemetryPanelLazy from "@/app/chat/_v2/components/TelemetryPanelLazy";
import { Badge, IconButton } from "@/app/chat/_v2/components/primitives";
import { usePrefersReducedMotion } from "@/app/chat/_v2/theme/usePrefersReducedMotion";
import { useResolvedTheme } from "@/app/chat/_v2/theme/useResolvedTheme";

/**
 * ChatShell — the rebuilt CLARA Chat (CHAT_V2) layout + orchestration.
 *
 * Owns responsive layout (sidebar / canvas / drawer), ARIA landmarks, a
 * skip-link, global keyboard shortcuts, and focus management (Requirement 2.1,
 * 5.1, 5.2). It composes the colocated hooks and presentational components; it
 * reuses the EXISTING API/SSE contracts unchanged (Requirement 8.3) and
 * preserves the persistent medical disclaimer (Requirement 8.4) and admin-only
 * telemetry detail (Requirement 6.6).
 */

/** Stable id of the composer textarea (see `Composer.tsx`), used for focus. */
const COMPOSER_INPUT_ID = "chat-composer-input";

/** Stable id of the sidebar search field (see `ConversationSidebar.tsx`). */
const SEARCH_INPUT_ID = "chat-v2-search";

export default function ChatShell() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRole] = useState<UserRole>("normal");
  const [query, setQuery] = useState("");
  const [searchText, setSearchText] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [mode, setMode] = useState<ResearchExecutionMode>("fast");
  const [retrievalStackMode, setRetrievalStackMode] =
    useState<ResearchRetrievalStackMode>("auto");
  const [personalMode, setPersonalMode] = useState(false);

  const [activeConversationId, setActiveConversationId] = useState<
    number | null
  >(null);
  const [activeMeta, setActiveMeta] =
    useState<WorkspaceConversationItem | null>(null);
  const [searchResults, setSearchResults] = useState<
    WorkspaceConversationItem[] | null
  >(null);
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isAppMenuOpen, setIsAppMenuOpen] = useState(false);

  const conversations = useConversations();
  const turns = useChatTurns();
  const stream = useChatStream();
  const workspace = useWorkspace({
    apiUnavailable: conversations.apiUnavailable,
  });

  // Theme integration (Requirement 4.2, 4.5). Light/dark is driven entirely by
  // the app's shared token layer (`lib/theme.ts` + `globals.css`); the shell
  // observes the resolved theme so it can expose it to assistive tech and child
  // surfaces, and reflects the `prefers-reduced-motion` preference on the root
  // so decorative motion can be neutralized consistently.
  const resolvedTheme = useResolvedTheme();
  const prefersReducedMotion = usePrefersReducedMotion();

  // Focus management for the composer (Requirement 5.1, 5.4). The composer is a
  // self-contained presentational component, so the shell focuses it by its
  // stable input id rather than threading a ref through the component tree.
  const focusComposer = useCallback(() => {
    const el = document.getElementById(COMPOSER_INPUT_ID);
    if (el instanceof HTMLTextAreaElement) el.focus();
  }, []);

  const chooseStarterPrompt = useCallback(
    (prompt: string) => {
      setQuery(prompt);
      window.setTimeout(focusComposer, 0);
    },
    [focusComposer],
  );

  const launchResearch = useCallback(
    (sourceQuery: string) => {
      setMode("deep_beta");
      setQuery(sourceQuery);
      setNotice(
        uiLanguage === "en"
          ? "Research mode is ready. Refine the question or run it now."
          : "Đã sẵn sàng chế độ Nghiên cứu. Bạn có thể chỉnh câu hỏi hoặc chạy ngay.",
      );
      window.setTimeout(focusComposer, 0);
    },
    [focusComposer, uiLanguage],
  );

  // Focus the sidebar conversation-search field (command-palette parity action
  // + Ctrl/⌘+K). On mobile the sidebar is an overlay, so open it first so the
  // field is visible before focus lands (Requirement 5.1, 6.4).
  const focusSearch = useCallback(() => {
    setIsMobileSidebarOpen(true);
    window.setTimeout(() => {
      const el = document.getElementById(SEARCH_INPUT_ID);
      if (el instanceof HTMLInputElement) el.focus();
    }, 10);
  }, []);

  const isEn = uiLanguage === "en";
  const appNavItems = useMemo(() => getNavItemsByRole(role), [role]);
  // User-facing mode label (Req 4.4): never expose the internal mode string,
  // always present the Vietnamese End_User label via the shared mapping.
  const activeModeLabel = useMemo(() => toModeLabel(mode), [mode]);
  const latestAnswer = useMemo(
    () => latestAnswerFromTurn(turns.turns[turns.turns.length - 1] ?? null),
    [turns.turns],
  );
  const latestTier2Result = useMemo(() => {
    const found = [...turns.turns]
      .reverse()
      .find((item) => item.result.tier === "tier2");
    return found && found.result.tier === "tier2" ? found.result : null;
  }, [turns.turns]);

  // --- Bootstrap: language, role, initial lists -----------------------------
  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    setRole(getRole());
    return onUILanguageChange((language) => setUiLanguage(language));
  }, []);

  const toggleTheme = useCallback(() => {
    const nextTheme: ThemePreference =
      resolvedTheme === "dark" ? "light" : "dark";
    saveThemePreference(nextTheme);
    applyThemePreference(nextTheme);
  }, [resolvedTheme]);

  useEffect(() => {
    void conversations.load();
    void workspace.loadNotes();
    void workspace.loadShares();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 2500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // --- Debounced workspace search -------------------------------------------
  useEffect(() => {
    const keyword = searchText.trim();
    if (!keyword) {
      setSearchResults(null);
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchWorkspace(keyword, 16);
        if (active) setSearchResults(result.conversations);
      } catch {
        if (active) setSearchResults(null);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [searchText]);

  const displayedConversations = searchResults ?? conversations.merged;

  // --- Mode / personal invariants -------------------------------------------
  const applyMode = useCallback((next: ResearchExecutionMode) => {
    setMode(next);
    if (next === "fast") {
      setPersonalMode(false);
      setRetrievalStackMode("auto");
    }
  }, []);

  const togglePersonalMode = useCallback(() => {
    setPersonalMode((prev) => {
      const next = !prev;
      if (next) setMode((m) => (m === "fast" ? "deep" : m));
      return next;
    });
  }, []);

  // --- Conversation selection -----------------------------------------------
  const selectConversation = useCallback(
    async (item: WorkspaceConversationItem) => {
      const conversationId = asConversationId(item.conversation_id);
      if (!conversationId) return;
      setActiveConversationId(conversationId);
      setActiveMeta(item);
      setIsMobileSidebarOpen(false);
      setError("");
      const cached = turns.cachedTurns(conversationId);
      if (cached.length) turns.setActive(cached);
      try {
        await turns.load(conversationId);
      } catch (cause) {
        setError(
          cause instanceof Error ? sanitizeUpstreamError(cause.message) : "",
        );
      }
      if (!conversations.apiUnavailable) {
        try {
          await updateWorkspaceConversationMeta(conversationId, {
            touched: true,
          });
        } catch {
          // best-effort
        }
      }
    },
    [conversations.apiUnavailable, turns],
  );

  const newChat = useCallback(() => {
    setActiveConversationId(null);
    setActiveMeta(null);
    turns.clear();
    setQuery("");
    setError("");
    setIsMobileSidebarOpen(false);
    window.setTimeout(() => focusComposer(), 10);
  }, [turns, focusComposer]);

  // Stable handlers for opening advanced surfaces, so memoized children
  // (ConversationSidebar) don't re-render on every shell state change and the
  // lazy surfaces only mount on demand (Requirement 7.2, 7.3, Property P9).
  const openWorkspace = useCallback(() => setIsWorkspaceOpen(true), []);
  const openMobileSidebar = useCallback(() => setIsMobileSidebarOpen(true), []);
  const closeWorkspace = useCallback(() => setIsWorkspaceOpen(false), []);
  const openFoldersFromSidebar = useCallback(() => {
    setIsMobileSidebarOpen(false);
    setIsWorkspaceOpen(true);
  }, []);

  // --- Submit ---------------------------------------------------------------
  const onSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const message = query.trim();
      if (!message || stream.isRunning) return;
      setError("");

      const transport = resolveChatTransport(mode);
      // Coarse, non-PII analytics only (Requirement 8.5).
      trackChatMessageSent({ mode, transport });

      try {
        const result = await stream.run(message, {
          mode,
          retrievalStackMode,
          personalMode,
          uiLanguage,
        });

        const localTurn = createConversationItem(message, result, {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        });
        // Append to the visible log + local cache exactly once (Property P4).
        turns.appendTurn(activeConversationId, localTurn);

        let targetId = activeConversationId;
        try {
          if (targetId) {
            const persisted = await appendResearchConversationMessage(
              targetId,
              message,
              result as unknown as Record<string, unknown>,
            );
            targetId = asConversationId(Number(persisted.id));
          } else {
            const persisted = await createResearchConversation(
              message,
              result as unknown as Record<string, unknown>,
            );
            targetId = asConversationId(Number(persisted.id));
          }
        } catch (persistError) {
          // Local-fallback: keep the turn cached against a synthetic id so it is
          // never lost when persistence fails (Requirement 3.3, 6.5).
          const fallbackId = targetId ?? Date.now();
          targetId = fallbackId;
          const nowIso = new Date().toISOString();
          conversations.upsertLocal({
            conversation_id: fallbackId,
            title: message.slice(0, 255),
            preview: message.slice(0, 260),
            query_id: null,
            message_count: Math.max(1, (activeMeta?.message_count ?? 0) + 1),
            created_at: activeMeta?.created_at ?? nowIso,
            last_message_at: nowIso,
            folder_id: activeMeta?.folder_id ?? null,
            channel_id: null,
            is_favorite: activeMeta?.is_favorite ?? false,
          });
          turns.appendTurn(fallbackId, localTurn);
          setNotice(
            isEn
              ? "Answer saved locally; backend sync will recover later."
              : "Đã lưu local; backend sync sẽ khôi phục sau.",
          );
        }

        if (targetId) {
          setActiveConversationId(targetId);
          if (!conversations.apiUnavailable) {
            try {
              await turns.load(targetId);
            } catch {
              // keep local turns
            }
          }
        }

        setQuery("");
        await Promise.all([conversations.load(), workspace.loadShares()]);
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          setNotice(isEn ? "Run cancelled." : "Đã hủy phiên.");
          return;
        }
        setError(
          cause instanceof Error
            ? sanitizeUpstreamError(cause.message)
            : isEn
              ? "Could not process the question."
              : "Không thể xử lý câu hỏi.",
        );
      }
    },
    [
      activeConversationId,
      activeMeta,
      conversations,
      isEn,
      mode,
      personalMode,
      query,
      retrievalStackMode,
      role,
      stream,
      turns,
      uiLanguage,
      workspace,
    ],
  );

  const copyShareUrl = useCallback(
    async (url: string) => {
      try {
        await navigator.clipboard.writeText(url);
        setNotice(isEn ? "Copied." : "Đã sao chép.");
      } catch {
        window.prompt("Copy", url);
      }
    },
    [isEn],
  );

  // --- Command palette -------------------------------------------------------
  const commandActions = useMemo<CommandAction[]>(() => {
    const canExport = Boolean(asConversationId(activeConversationId));
    return [
      {
        id: "new-chat",
        label: isEn ? "New chat" : "Chat mới",
        hint: "Ctrl/⌘+Shift+N",
        keywords: ["new", "chat", "conversation", "moi"],
        run: newChat,
      },
      {
        id: "focus-composer",
        label: isEn ? "Focus composer" : "Nhập câu hỏi",
        hint: "/",
        keywords: ["focus", "composer", "prompt", "input"],
        run: () => focusComposer(),
      },
      {
        id: "search-conversations",
        label: isEn ? "Search conversations" : "Tìm hội thoại",
        keywords: ["search", "find", "conversation", "tim", "workspace"],
        run: () => focusSearch(),
      },
      {
        id: "open-workspace",
        label: isEn ? "Open workspace" : "Mở workspace",
        keywords: ["workspace", "notes", "shares", "drawer", "folders"],
        run: () => setIsWorkspaceOpen(true),
      },
      {
        id: "mode-fast",
        label: isEn ? "Mode: Quick" : "Chế độ: Nhanh",
        keywords: ["mode", "fast", "quick", "nhanh"],
        run: () => applyMode("fast"),
      },
      {
        id: "mode-deep",
        label: isEn ? "Mode: Reason" : "Chế độ: Tư duy",
        keywords: ["mode", "deep", "reason", "tu duy"],
        run: () => applyMode("deep"),
      },
      {
        id: "mode-deep-beta",
        label: isEn ? "Mode: Pro" : "Chế độ: Pro",
        keywords: ["mode", "deep_beta", "pro"],
        run: () => applyMode("deep_beta"),
      },
      {
        id: "toggle-personal",
        label: personalMode
          ? isEn
            ? "Personal mode: turn off"
            : "Chế độ cá nhân: tắt"
          : isEn
            ? "Personal mode: turn on"
            : "Chế độ cá nhân: bật",
        keywords: ["personal", "phr", "ca nhan", "private", "toggle"],
        run: () => togglePersonalMode(),
      },
      {
        id: "export-docx",
        label: isEn ? "Export report (DOCX)" : "Xuất báo cáo (DOCX)",
        keywords: ["export", "docx", "word", "report"],
        disabled: !canExport,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.exportConversation(
              id,
              "docx",
              turns.turns,
              activeMeta?.title || `Conversation ${id}`,
            );
          }
        },
      },
      {
        id: "export-md",
        label: isEn ? "Export Markdown" : "Xuất Markdown",
        keywords: ["export", "markdown", "md"],
        disabled: !canExport,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.exportConversation(
              id,
              "markdown",
              turns.turns,
              activeMeta?.title || `Conversation ${id}`,
            );
          }
        },
      },
      {
        id: "share",
        label: isEn ? "Create share link" : "Tạo liên kết chia sẻ",
        keywords: ["share", "public", "link"],
        disabled: !canExport || conversations.apiUnavailable,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.share(id).then((rows) => {
              const created = rows?.find((row) => row.conversation_id === id);
              if (created) void copyShareUrl(created.public_url);
            });
          }
        },
      },
      {
        id: "save-note",
        label: isEn
          ? "Save latest answer as note"
          : "Lưu câu trả lời thành ghi chú",
        keywords: ["note", "save", "answer"],
        disabled: !latestAnswer.trim(),
        run: () => {
          void workspace
            .saveNote({
              title: (
                turns.turns[turns.turns.length - 1]?.query ?? "Note"
              ).slice(0, 90),
              contentMarkdown: latestAnswer,
              tags: ["answer", "auto"],
              conversationId: asConversationId(activeConversationId),
            })
            .then(() => setNotice(isEn ? "Note saved." : "Đã lưu ghi chú."));
        },
      },
    ];
  }, [
    activeConversationId,
    activeMeta,
    applyMode,
    conversations.apiUnavailable,
    copyShareUrl,
    focusComposer,
    focusSearch,
    isEn,
    latestAnswer,
    newChat,
    personalMode,
    togglePersonalMode,
    turns.turns,
    workspace,
  ]);

  const palette = useCommandPalette(commandActions);

  // --- Global keyboard shortcuts --------------------------------------------
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const withCommand = event.metaKey || event.ctrlKey;
      if (palette.isOpen) return;
      if (
        (withCommand && event.shiftKey && key === "p") ||
        (withCommand && key === "k")
      ) {
        event.preventDefault();
        palette.open();
        return;
      }
      if (withCommand && event.shiftKey && key === "n") {
        event.preventDefault();
        newChat();
        return;
      }
      if (
        !withCommand &&
        !event.altKey &&
        key === "/" &&
        !isEditableElement(event.target)
      ) {
        event.preventDefault();
        focusComposer();
        return;
      }
      if (key === "escape") {
        setIsWorkspaceOpen(false);
        setIsMobileSidebarOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [newChat, palette, focusComposer]);

  return (
    <div
      data-resolved-theme={resolvedTheme}
      data-reduced-motion={prefersReducedMotion ? "true" : "false"}
      style={{ fontFamily: "var(--font-chat)" }}
      className="clara-chat-v2 relative flex h-[calc(100dvh-8.2rem)] min-h-[36rem] flex-col bg-[var(--bg-canvas)] text-[var(--text-primary)] motion-reduce:transition-none lg:h-[calc(100dvh-4.5rem)] [&_*]:motion-reduce:!animate-none"
    >
      <a
        href="#chat-v2-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[80] focus:rounded-lg focus:bg-[var(--brand-600)] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        {isEn ? "Skip to conversation" : "Tới khung trò chuyện"}
      </a>

      <div className="grid h-full min-h-0 grid-cols-1 xl:grid-cols-[18rem_minmax(0,1fr)]">
        {/* Sidebar (overlay on mobile, fixed column on desktop). */}
        {isMobileSidebarOpen ? (
          <button
            type="button"
            aria-label={isEn ? "Close sidebar" : "Đóng sidebar"}
            onClick={() => setIsMobileSidebarOpen(false)}
            className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[2px] xl:hidden"
          />
        ) : null}
        <aside
          className={[
            "fixed inset-y-0 left-0 z-50 w-[min(86vw,18rem)] border-r border-[color:var(--shell-border)] bg-[var(--surface-panel)] transition-transform duration-200 motion-reduce:transition-none xl:relative xl:z-0 xl:w-auto xl:translate-x-0",
            isMobileSidebarOpen
              ? "translate-x-0"
              : "-translate-x-[110%] xl:translate-x-0",
          ].join(" ")}
        >
          <ConversationSidebar
            conversations={displayedConversations}
            activeId={activeConversationId}
            isLoading={conversations.isLoading}
            searchText={searchText}
            onSearchChange={setSearchText}
            onSelect={selectConversation}
            onNewChat={newChat}
            onOpenFolders={openFoldersFromSidebar}
            uiLanguage={uiLanguage}
          />
        </aside>

        {/* Main canvas. */}
        <main
          id="chat-v2-main"
          className="flex h-full min-h-0 flex-col overflow-hidden"
          aria-label={isEn ? "Conversation canvas" : "Khung trò chuyện"}
        >
          <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 px-3 py-2 backdrop-blur-lg">
            <div className="flex min-w-0 items-center gap-2">
              <IconButton
                label={isEn ? "Open sidebar" : "Mở sidebar"}
                icon="menu"
                className="xl:hidden"
                onClick={openMobileSidebar}
              />
              <h1 className="truncate text-sm font-semibold text-[var(--text-primary)]">
                {activeMeta?.title?.trim() || "CLARA"}
              </h1>
              <Badge tone="info">{activeModeLabel}</Badge>
            </div>
            <div className="flex items-center gap-1.5">
              <nav
                aria-label={isEn ? "Primary navigation" : "Điều hướng chính"}
                className="hidden items-center gap-1 md:flex"
              >
                <Link
                  href="/dashboard"
                  className="rounded-lg px-2.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                >
                  {isEn ? "Dashboard" : "Tổng quan"}
                </Link>
                <Link
                  href="/research"
                  className="rounded-lg px-2.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                >
                  {isEn ? "Research" : "Nghiên cứu"}
                </Link>
              </nav>
              <IconButton
                label={
                  resolvedTheme === "dark"
                    ? isEn
                      ? "Switch to light mode"
                      : "Chuyển sang giao diện sáng"
                    : isEn
                      ? "Switch to dark mode"
                      : "Chuyển sang giao diện tối"
                }
                icon={resolvedTheme === "dark" ? "light_mode" : "dark_mode"}
                onClick={toggleTheme}
              />
              <button
                type="button"
                aria-label={isEn ? "Open all tools" : "Mở các công cụ"}
                aria-expanded={isAppMenuOpen}
                title={isEn ? "All tools" : "Các công cụ"}
                onClick={() => setIsAppMenuOpen((open) => !open)}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-[color:var(--shell-border)] px-2.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]"
              >
                <span
                  className="material-symbols-outlined text-[19px]"
                  aria-hidden="true"
                >
                  apps
                </span>
                <span className="hidden text-xs font-semibold sm:inline">
                  {isEn ? "Tools" : "Công cụ"}
                </span>
              </button>
              <IconButton
                label={isEn ? "Command palette" : "Bảng lệnh"}
                icon="bolt"
                onClick={palette.open}
              />
              <IconButton
                label={isEn ? "Open workspace" : "Mở workspace"}
                icon="dock_to_left"
                onClick={openWorkspace}
              />
            </div>
          </header>

          {isAppMenuOpen ? (
            <div
              className="absolute right-3 top-[3.35rem] z-30 w-[min(92vw,22rem)] rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-xl shadow-slate-950/10"
              role="dialog"
              aria-label={isEn ? "CLARA tools" : "Công cụ CLARA"}
            >
              <div className="flex items-center justify-between px-2 py-1.5">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {isEn ? "CLARA tools" : "Công cụ CLARA"}
                </p>
                <button
                  type="button"
                  onClick={() => setIsAppMenuOpen(false)}
                  className="text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {isEn ? "Close" : "Đóng"}
                </button>
              </div>
              <div className="grid gap-1 sm:grid-cols-2">
                {appNavItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsAppMenuOpen(false)}
                    className="flex items-start gap-2 rounded-xl px-2.5 py-2 text-left hover:bg-[var(--surface-muted)]"
                  >
                    <span
                      className="material-symbols-outlined mt-0.5 text-[18px] text-[var(--text-brand)]"
                      aria-hidden="true"
                    >
                      {item.icon}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-[var(--text-primary)]">
                        {item.label}
                      </span>
                      <span className="block truncate text-[11px] text-[var(--text-muted)]">
                        {item.desc}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
              <div className="mt-2 flex items-center justify-between border-t border-[color:var(--shell-border)] px-2 pt-2">
                <Link
                  href="/account/data"
                  onClick={() => setIsAppMenuOpen(false)}
                  className="text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                >
                  {isEn ? "Account" : "Tài khoản"}
                </Link>
                <button
                  type="button"
                  onClick={() => beginLogout()}
                  className="text-xs font-semibold text-[var(--status-danger-text)]"
                >
                  {isEn ? "Sign out" : "Đăng xuất"}
                </button>
              </div>
            </div>
          ) : null}

          {/* Persistent medical disclaimer (Requirement 8.4). */}
          <p
            role="note"
            className="flex items-center justify-center gap-1.5 border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-center text-[11px] text-[var(--text-muted)]"
          >
            <span
              className="material-symbols-outlined text-[14px]"
              aria-hidden="true"
            >
              info
            </span>
            {isEn
              ? "CLARA is an AI health information assistant, not a replacement for a clinician."
              : "CLARA là AI hỗ trợ thông tin y tế, không thay thế bác sĩ hoặc nhân viên y tế."}
          </p>

          {error ? (
            <p
              role="alert"
              className="border-b border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-[12px] font-medium text-[var(--status-danger-text)]"
            >
              {error}
            </p>
          ) : null}
          {notice ? (
            <p
              aria-live="polite"
              className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[12px] text-[var(--text-secondary)]"
            >
              {notice}
            </p>
          ) : null}

          {turns.turns.length ? (
            <MessageLog
              turns={turns.turns}
              uiLanguage={uiLanguage}
              isRunning={stream.isRunning}
              role={role}
              onLaunchResearch={launchResearch}
            />
          ) : (
            <ChatWelcome
              role={role}
              uiLanguage={uiLanguage}
              onChoosePrompt={chooseStarterPrompt}
            />
          )}

          {role === "admin" && latestTier2Result ? (
            <div className="mx-auto w-full max-w-3xl px-3 pb-2">
              <TelemetryPanelLazy
                role={role}
                result={latestTier2Result}
                uiLanguage={uiLanguage}
              />
            </div>
          ) : null}

          <Composer
            query={query}
            onChangeQuery={setQuery}
            onSubmit={onSubmit}
            isRunning={stream.isRunning}
            onCancel={stream.cancel}
            mode={mode}
            onChangeMode={applyMode}
            retrievalStackMode={retrievalStackMode}
            onChangeRetrievalStackMode={setRetrievalStackMode}
            personalMode={personalMode}
            onTogglePersonalMode={togglePersonalMode}
            liveStatusNote={stream.statusNote}
            uiLanguage={uiLanguage}
            userRole={role}
          />
        </main>
      </div>

      <CommandPaletteLazy palette={palette} uiLanguage={uiLanguage} />
      <WorkspaceDrawerLazy
        open={isWorkspaceOpen}
        onClose={closeWorkspace}
        workspace={workspace}
        uiLanguage={uiLanguage}
        onCopyShareUrl={copyShareUrl}
        activeConversationId={activeConversationId}
        activeTitle={activeMeta?.title || ""}
        activeTurns={turns.turns}
        apiUnavailable={conversations.apiUnavailable}
        onNotice={setNotice}
      />
    </div>
  );
}
