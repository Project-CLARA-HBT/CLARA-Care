import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";

/**
 * Feature: clara-chat-redesign, Requirement 2.1 (answer-first canvas) and
 * Requirement 5 (accessibility): ARIA landmarks, skip-link, global keyboard
 * shortcuts, and composer focus management.
 *
 * The shell composes colocated hooks + heavy child components. Here the hooks
 * are stubbed so no API/SSE call runs, and the heavy children are replaced with
 * sentinels — but the REAL `Composer` renders so we can assert the shell focuses
 * its textarea (focus management, Req 5.1/5.4). The lib modules the shell imports
 * at top-level are mocked to keep the render deterministic and side-effect-free.
 */

const clearTurns = vi.fn();
const loadConversations = vi.fn().mockResolvedValue([]);
const loadNotes = vi.fn().mockResolvedValue(undefined);
const loadShares = vi.fn().mockResolvedValue(undefined);

vi.mock("@/app/chat/_v2/hooks/useConversations", () => ({
  useConversations: () => ({
    conversations: [],
    merged: [],
    localIds: new Set<number>(),
    activeId: null,
    isLoading: false,
    apiUnavailable: false,
    load: loadConversations,
    select: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    setFavorite: vi.fn(),
    setFolder: vi.fn(),
    upsertLocal: vi.fn(),
    removeLocal: vi.fn(),
    patch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatTurns", () => ({
  useChatTurns: () => ({
    turns: [],
    cachedTurns: () => [],
    setActive: vi.fn(),
    load: vi.fn().mockResolvedValue(undefined),
    clear: clearTurns,
    appendTurn: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatStream", () => ({
  useChatStream: () => ({
    isRunning: false,
    statusNote: "",
    run: vi.fn(),
    cancel: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useWorkspace", () => ({
  useWorkspace: () => ({
    notes: [],
    shares: [],
    searchResults: null,
    loadNotes,
    loadShares,
    saveNote: vi.fn(),
    removeNote: vi.fn(),
    share: vi.fn(),
    revokeShare: vi.fn(),
    exportConversation: vi.fn(),
    search: vi.fn(),
    clearSearch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useCommandPalette", () => ({
  useCommandPalette: () => ({
    isOpen: false,
    open: vi.fn(),
    close: vi.fn(),
    query: "",
    setQuery: vi.fn(),
    results: [],
    activeIndex: 0,
    setActiveIndex: vi.fn(),
    runActive: vi.fn(),
  }),
}));

// Heavy child components → light sentinels. The real Composer is kept (below).
vi.mock("@/app/chat/_v2/components/ConversationSidebar", () => ({
  default: () => <div data-testid="sidebar" />,
}));
vi.mock("@/app/chat/_v2/components/MessageLog", () => ({
  default: () => <div data-testid="message-log" />,
}));
vi.mock("@/app/chat/_v2/components/CommandPalette", () => ({
  default: () => <div data-testid="command-palette" />,
}));
vi.mock("@/app/chat/_v2/components/WorkspaceDrawer", () => ({
  default: () => <div data-testid="workspace-drawer" />,
}));
vi.mock("@/app/chat/_v2/components/TelemetryPanel", () => ({
  default: () => <div data-testid="telemetry-panel" />,
}));

// Lib modules imported at the top of ChatShell — stubbed to avoid side effects.
vi.mock("@/lib/auth-store", () => ({ getRole: () => "normal" }));
vi.mock("@/lib/analytics/events", () => ({ trackChatMessageSent: vi.fn() }));
vi.mock("@/lib/user-facing-text", () => ({
  sanitizeUpstreamError: (m: string) => m,
  toModeLabel: (m: string) => m,
}));
vi.mock("@/lib/ui-language", () => ({
  getStoredUILanguage: () => "en",
  onUILanguageChange: () => vi.fn(),
}));
vi.mock("@/lib/research", () => ({
  isResearchOutputModesEnabled: () => false,
  resolveChatTransport: () => "chat",
  appendResearchConversationMessage: vi.fn(),
  createResearchConversation: vi.fn(),
  listResearchConversationMessages: vi.fn(),
}));
vi.mock("@/lib/workspace", () => ({
  searchWorkspace: vi.fn().mockResolvedValue({ conversations: [] }),
  updateWorkspaceConversationMeta: vi.fn(),
}));
vi.mock("@/components/research/lib/research-page-helpers", () => ({
  createConversationItem: vi.fn(),
}));

async function renderShell() {
  const mod = await import("@/app/chat/_v2/ChatShell");
  const ChatShell = mod.default;
  const utils = render(<ChatShell />);
  // Flush the bootstrap effects (language/role/list loads).
  await waitFor(() => expect(loadConversations).toHaveBeenCalled());
  return utils;
}

beforeEach(() => {
  vi.clearAllMocks();
  loadConversations.mockResolvedValue([]);
});

afterEach(() => {
  vi.resetModules();
});

describe("ChatShell — accessibility scaffolding", () => {
  it("exposes a skip-link targeting the main canvas landmark", async () => {
    await renderShell();
    const skipLink = screen.getByRole("link", { name: /skip to conversation/i });
    expect(skipLink).toHaveAttribute("href", "#chat-v2-main");
    const main = screen.getByRole("main", { name: /conversation canvas/i });
    expect(main).toHaveAttribute("id", "chat-v2-main");
  });

  it("renders the persistent medical disclaimer (Requirement 8.4)", async () => {
    await renderShell();
    expect(
      screen.getByText(/not a replacement for a clinician/i),
    ).toBeInTheDocument();
  });

  it("keeps primary product navigation and theme control visible in chat", async () => {
    await renderShell();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: "Research" })).toHaveAttribute(
      "href",
      "/research",
    );
    expect(
      screen.getByRole("button", { name: /switch to dark theme/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open all tools/i })).toBeInTheDocument();
  });

  it("focuses the composer when the '/' shortcut is pressed (Req 5.1/5.4)", async () => {
    await renderShell();
    const composer = screen.getByLabelText(/your medical question/i);
    expect(document.activeElement).not.toBe(composer);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "/" }));
    });
    expect(document.activeElement).toBe(composer);
  });

  it("starts a new chat on Ctrl/Cmd+Shift+N (global shortcut)", async () => {
    await renderShell();
    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "n",
          ctrlKey: true,
          shiftKey: true,
        }),
      );
    });
    // `newChat` clears the active turn buffer.
    expect(clearTurns).toHaveBeenCalled();
  });
});
