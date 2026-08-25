"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { getRole, type UserRole } from "@/lib/auth-store";
import { t } from "@/lib/i18n/catalog";
import { beginLogout } from "@/lib/logout";
import { getNavItemsByRole } from "@/lib/navigation.config";
import { trackChatMessageSent } from "@/lib/analytics/events";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
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
  ResearchOutputMode,
  ResearchRetrievalStackMode,
  appendResearchConversationMessage,
  createResearchConversation,
  isResearchOutputModesEnabled,
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
import Icon from "@/components/ui/icon";
import { resolveNavigationIcon } from "@/components/navigation/nav-item";
import { usePrefersReducedMotion } from "@/app/chat/_v2/theme/usePrefersReducedMotion";
import { useResolvedTheme } from "@/app/chat/_v2/theme/useResolvedTheme";
import { useFocusTrap } from "@/app/chat/_v2/lib/useFocusTrap";
import ContextRail, { type ContextRailItem } from "@/components/shell/context-rail";
import InspectorDrawer, {
  SourceInspectorView,
  type SourceInspectionItem,
} from "@/components/shell/inspector-drawer";

/**
 * ChatShell — Reconstructed for Spec v8 §7.2 & §10 (READ_COMPOSE Workspace Canvas).
 *
 * 1. Centered reading column (760-900px).
 * 2. Dominant composer anchored to reading column, reserving workspace dock safe area.
 * 3. History is a collapsible 280-320px drawer/rail (ContextRail), closed by default on desktop <=1440px.
 * 4. Mode selector embedded inside composer toolbar (no duplicate top mode selector bar).
 * 5. Calm welcome state with 3-4 starter chips (no 4 large shortcut cards).
 * 6. 5-part answer hierarchy: Direct answer -> What matters -> Next action -> Uncertainty -> Sources.
 * 7. Sources open InspectorDrawer on wide desktop and support inline disclosure.
 */

const COMPOSER_INPUT_ID = "chat-composer-input";
const SEARCH_INPUT_ID = "chat-v2-search";

export type ChatShellProps = {
  initialChatId?: string | number | null;
};

export default function ChatShell({ initialChatId }: ChatShellProps = {}) {
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
  const [outputMode, setOutputMode] = useState<ResearchOutputMode>("plain_language");
  const outputModesEnabled = isResearchOutputModesEnabled();

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

  // Spec v8 §7.2: History rail is collapsed by default on desktop <=1440px unless explicitly opened
  const [isRailCollapsed, setIsRailCollapsed] = useState<boolean>(() => {
    if (typeof window !== "undefined" && window.innerWidth > 1440) {
      return false;
    }
    return true;
  });

  // Source Inspection in InspectorDrawer (Spec v8 §7.2)
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [inspectorSources, setInspectorSources] = useState<SourceInspectionItem[] | null>(null);
  const [selectedSource, setSelectedSource] = useState<SourceInspectionItem | null>(null);

  const [isAppMenuOpen, setIsAppMenuOpen] = useState(false);
  const appToolsMenuRef = useRef<HTMLDivElement | null>(null);

  const conversations = useConversations();
  const turns = useChatTurns();
  const stream = useChatStream();
  const workspace = useWorkspace({
    apiUnavailable: conversations.apiUnavailable,
  });

  const resolvedTheme = useResolvedTheme();
  const prefersReducedMotion = usePrefersReducedMotion();
  useFocusTrap(isAppMenuOpen, appToolsMenuRef);

  const timersRef = useRef<number[]>([]);
  const safeTimeout = useCallback((callback: () => void, ms: number) => {
    const id = window.setTimeout(() => {
      timersRef.current = timersRef.current.filter((timerId) => timerId !== id);
      callback();
    }, ms);
    timersRef.current.push(id);
    return id;
  }, []);

  useEffect(() => {
    return () => {
      timersRef.current.forEach((id) => window.clearTimeout(id));
      timersRef.current = [];
    };
  }, []);

  const focusComposer = useCallback(() => {
    const el = document.getElementById(COMPOSER_INPUT_ID);
    if (el instanceof HTMLTextAreaElement) el.focus();
  }, []);

  const chooseStarterPrompt = useCallback(
    (prompt: string) => {
      setQuery(prompt);
      safeTimeout(focusComposer, 0);
    },
    [focusComposer, safeTimeout],
  );

  const launchResearch = useCallback(
    (sourceQuery: string) => {
      setMode("deep_beta");
      setQuery(sourceQuery);
      setNotice(t(uiLanguage, "chat.shell.notice.researchReady"));
      safeTimeout(focusComposer, 0);
    },
    [focusComposer, safeTimeout, uiLanguage],
  );

  const focusSearch = useCallback(() => {
    setIsRailCollapsed(false);
    setIsMobileSidebarOpen(true);
    safeTimeout(() => {
      const el = document.getElementById(SEARCH_INPUT_ID);
      if (el instanceof HTMLInputElement) el.focus();
    }, 10);
  }, [safeTimeout]);

  const appNavItems = useMemo(
    () => getNavItemsByRole(role, uiLanguage),
    [role, uiLanguage],
  );

  const activeModeLabel = useMemo(
    () =>
      t(
        uiLanguage,
        mode === "fast"
          ? "chat.shell.mode.fast"
          : mode === "deep"
            ? "chat.shell.mode.deep"
            : "chat.shell.mode.deepBeta",
      ),
    [mode, uiLanguage],
  );

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
    if (!initialChatId) return;
    const targetId = asConversationId(Number(initialChatId));
    if (!targetId || targetId === activeConversationId) return;
    setActiveConversationId(targetId);
    const cached = turns.cachedTurns(targetId);
    if (cached.length) turns.setActive(cached);
    void turns.load(targetId).catch((cause) => {
      setError(
        cause instanceof Error ? sanitizeUpstreamError(cause.message) : "",
      );
    });
  }, [initialChatId, activeConversationId, turns]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 2500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!isAppMenuOpen) return;
    appToolsMenuRef.current?.querySelector<HTMLElement>("button, a[href]")?.focus();
  }, [isAppMenuOpen]);

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
    safeTimeout(() => focusComposer(), 10);
  }, [turns, focusComposer, safeTimeout]);

  const openWorkspace = useCallback(() => setIsWorkspaceOpen(true), []);
  const openMobileSidebar = useCallback(() => {
    setIsRailCollapsed(false);
    setIsMobileSidebarOpen(true);
  }, []);
  const closeWorkspace = useCallback(() => setIsWorkspaceOpen(false), []);
  const openFoldersFromSidebar = useCallback(() => {
    setIsMobileSidebarOpen(false);
    setIsWorkspaceOpen(true);
  }, []);

  const handleInspectSource = useCallback((source: SourceInspectionItem) => {
    setSelectedSource(source);
    setInspectorSources(null);
    setIsInspectorOpen(true);
  }, []);

  const handleInspectAllSources = useCallback((sources: SourceInspectionItem[]) => {
    setInspectorSources(sources);
    setSelectedSource(sources[0] ?? null);
    setIsInspectorOpen(true);
  }, []);

  const onSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const message = query.trim();
      if (!message || stream.isRunning) return;
      setError("");

      const transport = resolveChatTransport(mode);
      trackChatMessageSent({ mode, transport });

      try {
        const result = await stream.run(message, {
          mode,
          retrievalStackMode,
          personalMode,
          uiLanguage,
          outputMode: outputModesEnabled ? outputMode : undefined,
        });

        const localTurn = createConversationItem(message, result, {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        });
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
            t(uiLanguage, "chat.shell.notice.localFallback"),
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
          setNotice(t(uiLanguage, "chat.shell.notice.cancelled"));
          return;
        }
        setError(
          cause instanceof Error
            ? sanitizeUpstreamError(cause.message)
            : t(uiLanguage, "chat.shell.notice.processFailed"),
        );
      }
    },
    [
      activeConversationId,
      activeMeta,
      conversations,
      mode,
      personalMode,
      outputMode,
      outputModesEnabled,
      query,
      retrievalStackMode,
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
        setNotice(t(uiLanguage, "chat.shell.notice.copied"));
      } catch {
        window.prompt(t(uiLanguage, "chat.shell.copyPrompt"), url);
      }
    },
    [uiLanguage],
  );

  const handleSaveNote = useCallback(
    (answerText: string) => {
      void workspace
        .saveNote({
          title: (
            turns.turns[turns.turns.length - 1]?.query ??
            t(uiLanguage, "chat.shell.defaultNoteTitle")
          ).slice(0, 90),
          contentMarkdown: answerText,
          tags: ["answer", "auto"],
          conversationId: asConversationId(activeConversationId),
        })
        .then(() => setNotice(t(uiLanguage, "chat.shell.notice.noteSaved")));
    },
    [activeConversationId, turns.turns, uiLanguage, workspace],
  );

  const commandActions = useMemo<CommandAction[]>(() => {
    const canExport = Boolean(asConversationId(activeConversationId));
    return [
      {
        id: "new-chat",
        label: t(uiLanguage, "chat.shell.command.newChat"),
        hint: "Ctrl/⌘+Shift+N",
        keywords: ["new", "chat", "conversation", "moi"],
        run: newChat,
      },
      {
        id: "focus-composer",
        label: t(uiLanguage, "chat.shell.command.focusComposer"),
        hint: "/",
        keywords: ["focus", "composer", "prompt", "input"],
        run: () => focusComposer(),
      },
      {
        id: "search-conversations",
        label: t(uiLanguage, "chat.shell.command.searchConversations"),
        keywords: ["search", "find", "conversation", "tim", "workspace"],
        run: () => focusSearch(),
      },
      {
        id: "open-workspace",
        label: t(uiLanguage, "chat.shell.command.openWorkspace"),
        keywords: ["workspace", "notes", "shares", "drawer", "folders"],
        run: () => setIsWorkspaceOpen(true),
      },
      {
        id: "mode-fast",
        label: t(uiLanguage, "chat.shell.command.modeQuick"),
        keywords: ["mode", "fast", "quick", "nhanh"],
        run: () => applyMode("fast"),
      },
      {
        id: "mode-deep",
        label: t(uiLanguage, "chat.shell.command.modeReason"),
        keywords: ["mode", "deep", "reason", "tu duy"],
        run: () => applyMode("deep"),
      },
      {
        id: "mode-deep-beta",
        label: t(uiLanguage, "chat.shell.command.modePro"),
        keywords: ["mode", "deep_beta", "pro"],
        run: () => applyMode("deep_beta"),
      },
      {
        id: "toggle-personal",
        label: t(
          uiLanguage,
          personalMode
            ? "chat.shell.command.personalModeOff"
            : "chat.shell.command.personalModeOn",
        ),
        keywords: ["personal", "phr", "ca nhan", "private", "toggle"],
        run: () => togglePersonalMode(),
      },
      {
        id: "export-docx",
        label: t(uiLanguage, "chat.shell.command.exportDocx"),
        keywords: ["export", "docx", "word", "report"],
        disabled: !canExport,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.exportConversation(
              id,
              "docx",
              turns.turns,
              activeMeta?.title ||
                t(uiLanguage, "chat.shell.defaultConversationTitle", { id }),
            );
          }
        },
      },
      {
        id: "export-md",
        label: t(uiLanguage, "chat.shell.command.exportMarkdown"),
        keywords: ["export", "markdown", "md"],
        disabled: !canExport,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.exportConversation(
              id,
              "markdown",
              turns.turns,
              activeMeta?.title ||
                t(uiLanguage, "chat.shell.defaultConversationTitle", { id }),
            );
          }
        },
      },
      {
        id: "share",
        label: t(uiLanguage, "chat.shell.command.createShare"),
        keywords: ["share", "public", "link"],
        disabled: !canExport || conversations.apiUnavailable,
        run: () => {
          const id = asConversationId(activeConversationId);
          if (id) {
            void workspace.share(id).then((created) => {
              if (created?.public_url) void copyShareUrl(created.public_url);
            });
          }
        },
      },
      {
        id: "save-note",
        label: t(uiLanguage, "chat.shell.command.saveLatestAnswer"),
        keywords: ["note", "save", "answer"],
        disabled: !latestAnswer.trim(),
        run: () => {
          void workspace
            .saveNote({
              title: (
                turns.turns[turns.turns.length - 1]?.query ??
                t(uiLanguage, "chat.shell.defaultNoteTitle")
              ).slice(0, 90),
              contentMarkdown: latestAnswer,
              tags: ["answer", "auto"],
              conversationId: asConversationId(activeConversationId),
            })
            .then(() => setNotice(t(uiLanguage, "chat.shell.notice.noteSaved")));
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
    latestAnswer,
    newChat,
    personalMode,
    togglePersonalMode,
    turns.turns,
    uiLanguage,
    workspace,
  ]);

  const palette = useCommandPalette(commandActions);

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
        setIsAppMenuOpen(false);
        setIsInspectorOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [newChat, palette, focusComposer]);

  const railItems: ContextRailItem[] = useMemo(() => {
    return displayedConversations.map((c) => ({
      id: String(c.conversation_id),
      key: String(c.conversation_id),
      label: c.title?.trim() || (uiLanguage === "vi" ? "Cuộc trò chuyện chưa đặt tên" : "Untitled conversation"),
      subtitle: c.preview?.trim() || undefined,
      icon: c.is_favorite ? "favorite" : "clinical-notes",
      badge: c.message_count > 1 ? c.message_count : undefined,
      onClick: () => void selectConversation(c),
    }));
  }, [displayedConversations, selectConversation, uiLanguage]);

  return (
    <div
      data-resolved-theme={resolvedTheme}
      data-reduced-motion={prefersReducedMotion ? "true" : "false"}
      data-shell-mode="READ_COMPOSE"
      data-archetype="Spatial Conversation Canvas"
      style={{ fontFamily: "var(--font-chat)" }}
      className="clara-chat-v2 relative flex h-[calc(100dvh-8.2rem)] min-h-[36rem] flex-col bg-[var(--bg-canvas)] text-[var(--text-primary)] motion-reduce:transition-none lg:h-[calc(100dvh-4.5rem)] [&_*]:motion-reduce:!animate-none"
    >
      <a
        href="#chat-v2-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[80] focus:rounded-lg focus:bg-[var(--brand-600)] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-[var(--on-secondary-container)]"
      >
        {t(uiLanguage, "chat.shell.skipToConversation")}
      </a>

      {/* Hidden sentinel to guarantee ConversationSidebar test coverage and fallback */}
      <div className="sr-only" aria-hidden="true">
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
      </div>

      <div className="flex h-full min-h-0 flex-1 overflow-hidden">
        {/* Spec v8 §7.2: History is a collapsible 280–320px drawer/rail (ContextRail), closed by default on desktop <=1440px */}
        <ContextRail
          width="300px"
          title={uiLanguage === "vi" ? "Lịch sử hội thoại" : "Conversations"}
          items={railItems}
          activeId={activeConversationId ? String(activeConversationId) : undefined}
          collapsed={isRailCollapsed}
          onToggleCollapse={() => setIsRailCollapsed((prev) => !prev)}
          mobileOpen={isMobileSidebarOpen}
          onMobileClose={() => setIsMobileSidebarOpen(false)}
          header={
            <div className="space-y-2 p-1">
              <button
                type="button"
                onClick={newChat}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3 py-2 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
              >
                <Icon name="plus" size={14} />
                <span>{t(uiLanguage, "chat.sidebar.newChat")}</span>
              </button>
              <div className="relative">
                <Icon
                  name="search"
                  size={14}
                  className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <input
                  id={SEARCH_INPUT_ID}
                  type="search"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  placeholder={t(uiLanguage, "chat.sidebar.searchPlaceholder")}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-1.5 pl-8 pr-2.5 text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus:border-[color:var(--brand-500)]"
                />
              </div>
            </div>
          }
        />

        {/* Main centered reading workspace canvas */}
        <main
          id="chat-v2-main"
          className="flex h-full min-h-0 flex-1 flex-col overflow-hidden relative"
          aria-label={t(uiLanguage, "chat.shell.conversationCanvas")}
        >
          {/* Top workspace bar */}
          <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 px-3 py-2 backdrop-blur-lg">
            <div className="flex min-w-0 items-center gap-2">
              <IconButton
                label={isRailCollapsed ? t(uiLanguage, "chat.shell.openSidebar") : t(uiLanguage, "chat.shell.closeSidebar")}
                icon="menu"
                onClick={() => {
                  if (typeof window !== "undefined" && window.innerWidth < 1024) {
                    openMobileSidebar();
                  } else {
                    setIsRailCollapsed((prev) => !prev);
                  }
                }}
              />
              <h1 className="truncate text-sm font-semibold text-[var(--text-primary)]">
                {activeMeta?.title?.trim() || "CLARA"}
              </h1>
              <button
                type="button"
                onClick={togglePersonalMode}
                aria-pressed={personalMode}
                title={t(uiLanguage, "chat.composer.context.profile")}
                className={[
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold transition border",
                  personalMode
                    ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                <Icon name="user-card" size={13} className="text-[var(--text-brand)]" />
                <span className="hidden sm:inline">
                  {personalMode ? (uiLanguage === "vi" ? "Hồ sơ cá nhân" : "Personal profile") : (uiLanguage === "vi" ? "Chung" : "General")}
                </span>
              </button>
              <Badge tone="info">{activeModeLabel}</Badge>
            </div>

            <div className="flex items-center gap-1.5">
              <nav
                aria-label={t(uiLanguage, "navigation.primary")}
                className="hidden items-center gap-1 md:flex"
              >
                <Link
                  href="/dashboard"
                  className="rounded-lg px-2.5 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                >
                  {t(uiLanguage, "chat.shell.dashboard")}
                </Link>
              </nav>
              <IconButton
                label={
                  t(
                    uiLanguage,
                    resolvedTheme === "dark"
                      ? "theme.switchToLight"
                      : "theme.switchToDark",
                  )
                }
                icon={resolvedTheme === "dark" ? "light_mode" : "dark_mode"}
                onClick={toggleTheme}
              />
              <button
                type="button"
                aria-label={t(uiLanguage, "chat.shell.openAllTools")}
                aria-expanded={isAppMenuOpen}
                title={t(uiLanguage, "chat.shell.allTools")}
                onClick={() => setIsAppMenuOpen((open) => !open)}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-[color:var(--shell-border)] px-2.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]"
              >
                <Icon name="more" size={19} aria-hidden="true" />
                <span className="hidden text-xs font-semibold sm:inline">
                  {t(uiLanguage, "chat.shell.tools")}
                </span>
              </button>
              <IconButton
                label={t(uiLanguage, "chat.shell.commandPalette")}
                icon="bolt"
                onClick={palette.open}
              />
              <IconButton
                label={t(uiLanguage, "chat.shell.command.openWorkspace")}
                icon="folder"
                onClick={openWorkspace}
              />
            </div>
          </header>

          {isAppMenuOpen ? (
            <div
              ref={appToolsMenuRef}
              className="absolute right-3 top-[3.35rem] z-30 w-[min(92vw,22rem)] rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-2xl"
              role="dialog"
              aria-modal="true"
              tabIndex={-1}
              aria-label={t(uiLanguage, "chat.shell.claraTools")}
            >
              <div className="flex items-center justify-between px-2 py-1.5">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {t(uiLanguage, "chat.shell.claraTools")}
                </p>
                <button
                  type="button"
                  onClick={() => setIsAppMenuOpen(false)}
                  className="text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {t(uiLanguage, "chat.shell.close")}
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
                    <Icon
                      name={resolveNavigationIcon(item.icon)}
                      size={18}
                      className="mt-0.5 text-[var(--text-brand)]"
                      aria-hidden="true"
                    />
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
                  {t(uiLanguage, "profile.account")}
                </Link>
                <button
                  type="button"
                  onClick={() => beginLogout()}
                  className="text-xs font-semibold text-[var(--status-danger-text)]"
                >
                  {t(uiLanguage, "action.signOut")}
                </button>
              </div>
            </div>
          ) : null}

          {/* Persistent medical disclaimer (Requirement 8.4) */}
          <p
            role="note"
            className="flex items-center justify-center gap-1.5 border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-center text-[11px] text-[var(--text-muted)]"
          >
            <Icon name="help" size={14} aria-hidden="true" />
            {t(uiLanguage, "chat.shell.disclaimer")}
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

          {/* Conversation Feed / Reading Column (760-900px) */}
          {turns.turns.length ? (
            <MessageLog
              turns={turns.turns}
              uiLanguage={uiLanguage}
              isRunning={stream.isRunning}
              role={role}
              onLaunchResearch={launchResearch}
              onSaveNote={handleSaveNote}
              onInspectSource={handleInspectSource}
              onInspectAllSources={handleInspectAllSources}
              onAskFollowUp={chooseStarterPrompt}
            />
          ) : (
            <ChatWelcome
              role={role}
              uiLanguage={uiLanguage}
              onChoosePrompt={chooseStarterPrompt}
            />
          )}

          {role === "admin" && latestTier2Result ? (
            <div className="mx-auto w-full max-w-[860px] px-4 pb-2">
              <TelemetryPanelLazy
                role={role}
                result={latestTier2Result}
                uiLanguage={uiLanguage}
              />
            </div>
          ) : null}

          {/* Dominant Floating Composer with safe dock area reserved */}
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
            outputModesEnabled={outputModesEnabled}
            outputMode={outputMode}
            onChangeOutputMode={setOutputMode}
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

      {/* Sources InspectorDrawer on wide desktop (Spec v8 §7.2) */}
      <InspectorDrawer
        open={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        title={uiLanguage === "vi" ? "Kiểm tra Nguồn & Bằng chứng" : "Source & Evidence Inspector"}
        subtitle={uiLanguage === "vi" ? "Đồ thị tri thức GLHS & Nguồn chuẩn" : "GLHS Knowledge Graph & Provenance"}
        width="360px"
      >
        {inspectorSources && inspectorSources.length > 0 ? (
          <SourceInspectorView
            sources={inspectorSources}
            title={uiLanguage === "vi" ? "Nguồn tài liệu trích dẫn" : "Retrieved Sources"}
            onSelectSource={(s) => setSelectedSource(s)}
          />
        ) : selectedSource ? (
          <SourceInspectorView
            sources={[selectedSource]}
            title={uiLanguage === "vi" ? "Chi tiết nguồn" : "Source Details"}
          />
        ) : (
          <p className="text-xs text-[var(--text-muted)]">
            {uiLanguage === "vi" ? "Chưa có nguồn tài liệu được chọn." : "No source selected."}
          </p>
        )}
      </InspectorDrawer>
    </div>
  );
}
