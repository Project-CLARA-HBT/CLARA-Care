import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import type {
  WorkspaceConversationShareListItem,
  WorkspaceNote,
} from "@/lib/workspace";

/**
 * Feature: clara-chat-redesign; Requirement 6.2, 6.4, 6.5, 8.3.
 *
 * `useWorkspace` owns the chat's progressive-disclosure side surfaces — notes,
 * shares, export, and search. Every load is best-effort so a workspace API
 * failure never blocks the chat flow (Requirement 2.4). Search degrades to an
 * in-memory note scan when the workspace API is unavailable (Requirement 6.5).
 * It reuses the existing workspace client unchanged (Requirement 8.3); the
 * client is mocked here so the hook runs in isolation.
 */

const listWorkspaceNotes = vi.fn();
const createWorkspaceNote = vi.fn();
const deleteWorkspaceNote = vi.fn();
const listWorkspaceShares = vi.fn();
const createWorkspaceConversationShare = vi.fn();
const revokeWorkspaceConversationShare = vi.fn();
const exportWorkspaceConversation = vi.fn();
const exportWorkspaceDocxFromMarkdown = vi.fn();
const searchWorkspace = vi.fn();

vi.mock("@/lib/workspace", () => ({
  listWorkspaceNotes,
  createWorkspaceNote,
  deleteWorkspaceNote,
  listWorkspaceShares,
  createWorkspaceConversationShare,
  revokeWorkspaceConversationShare,
  exportWorkspaceConversation,
  exportWorkspaceDocxFromMarkdown,
  searchWorkspace,
}));

async function loadHook() {
  const mod = await import("@/app/chat/_v2/hooks/useWorkspace");
  return mod.useWorkspace;
}

function makeNote(
  id: number,
  overrides: Partial<WorkspaceNote> = {},
): WorkspaceNote {
  return {
    id,
    title: `note-${id}`,
    content_markdown: `body-${id}`,
    summary: `summary-${id}`,
    tags: [],
    is_pinned: false,
    conversation_id: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

function makeShare(
  conversationId: number,
): WorkspaceConversationShareListItem {
  return {
    conversation_id: conversationId,
    conversation_title: `c-${conversationId}`,
    message_count: 1,
    last_message_at: "2026-01-01T00:00:00.000Z",
    share_token: `tok-${conversationId}`,
    public_url: `https://share/${conversationId}`,
    is_active: true,
    expires_at: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
  };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe("useWorkspace notes", () => {
  it("loads notes from the workspace client", async () => {
    listWorkspaceNotes.mockResolvedValue([makeNote(1), makeNote(2)]);
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.loadNotes();
    });

    expect(result.current.notes.map((n) => n.id)).toEqual([1, 2]);
  });

  it("a notes load failure never throws and leaves the list empty", async () => {
    listWorkspaceNotes.mockRejectedValue(new Error("boom"));
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.loadNotes();
    });

    expect(result.current.notes).toEqual([]);
  });

  it("saveNote prepends the created note", async () => {
    createWorkspaceNote.mockResolvedValue(makeNote(9, { title: "fresh" }));
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.saveNote({ title: "fresh" });
    });

    expect(result.current.notes[0].id).toBe(9);
  });

  it("removeNote drops the note from the list", async () => {
    listWorkspaceNotes.mockResolvedValue([makeNote(1), makeNote(2)]);
    deleteWorkspaceNote.mockResolvedValue({ deleted: true });
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.loadNotes();
    });
    await act(async () => {
      await result.current.removeNote(1);
    });

    expect(result.current.notes.map((n) => n.id)).toEqual([2]);
  });
});

describe("useWorkspace shares", () => {
  it("loadShares populates from the client; share refreshes the list", async () => {
    listWorkspaceShares.mockResolvedValue([makeShare(1)]);
    createWorkspaceConversationShare.mockResolvedValue(undefined);
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.loadShares();
    });
    expect(result.current.shares.map((s) => s.conversation_id)).toEqual([1]);

    listWorkspaceShares.mockResolvedValue([makeShare(1), makeShare(2)]);
    await act(async () => {
      await result.current.share(2);
    });

    expect(createWorkspaceConversationShare).toHaveBeenCalledWith(2, {
      expiresInHours: 168,
      rotate: false,
    });
    expect(result.current.shares.map((s) => s.conversation_id)).toEqual([1, 2]);
  });

  it("share/revoke are no-ops when the workspace API is unavailable", async () => {
    const useWorkspace = await loadHook();
    const { result } = renderHook(() =>
      useWorkspace({ apiUnavailable: true }),
    );

    let shareResult: unknown;
    await act(async () => {
      shareResult = await result.current.share(2);
      await result.current.revokeShare(2);
    });

    expect(shareResult).toBeNull();
    expect(createWorkspaceConversationShare).not.toHaveBeenCalled();
    expect(revokeWorkspaceConversationShare).not.toHaveBeenCalled();
  });
});

describe("useWorkspace search", () => {
  it("calls the workspace search client and stores the response", async () => {
    const response = {
      query: "metformin",
      conversations: [],
      notes: [makeNote(1)],
      folders: [],
      channels: [],
      suggestions: [],
    };
    searchWorkspace.mockResolvedValue(response);
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.search("metformin");
    });

    expect(searchWorkspace).toHaveBeenCalledWith("metformin");
    expect(result.current.searchResults?.notes.map((n) => n.id)).toEqual([1]);
  });

  it("a blank query clears results without calling the client", async () => {
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.search("   ");
    });

    expect(searchWorkspace).not.toHaveBeenCalled();
    expect(result.current.searchResults).toBeNull();
  });

  it("falls back to an in-memory note scan when the API is unavailable", async () => {
    const useWorkspace = await loadHook();
    const { result } = renderHook(() =>
      useWorkspace({ apiUnavailable: true }),
    );

    // Seed loaded notes via saveNote so the local scan has something to match.
    createWorkspaceNote.mockResolvedValue(
      makeNote(3, { title: "Blood pressure log", tags: ["bp"] }),
    );
    await act(async () => {
      await result.current.saveNote({ title: "Blood pressure log" });
    });

    let scan!: { notes: WorkspaceNote[] };
    await act(async () => {
      scan = (await result.current.search("blood")) as {
        notes: WorkspaceNote[];
      };
    });

    expect(searchWorkspace).not.toHaveBeenCalled();
    expect(scan.notes.map((n) => n.id)).toEqual([3]);
    expect(result.current.searchResults?.notes.map((n) => n.id)).toEqual([3]);
  });

  it("clearSearch resets stored results", async () => {
    searchWorkspace.mockResolvedValue({
      query: "x",
      conversations: [],
      notes: [makeNote(1)],
      folders: [],
      channels: [],
      suggestions: [],
    });
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.search("x");
    });
    expect(result.current.searchResults).not.toBeNull();

    act(() => result.current.clearSearch());
    expect(result.current.searchResults).toBeNull();
  });
});

describe("useWorkspace export", () => {
  it("uses the workspace export client when the API is available", async () => {
    // jsdom does not implement object-URL APIs; stub them so the browser-only
    // download path in triggerBlobDownload is exercisable.
    const createObjectURL = vi.fn(() => "blob:stub");
    const revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });

    exportWorkspaceConversation.mockResolvedValue(
      new Blob(["data"], { type: "text/markdown" }),
    );
    const useWorkspace = await loadHook();
    const { result } = renderHook(() => useWorkspace());

    await act(async () => {
      await result.current.exportConversation(7, "markdown", [], "Title");
    });

    expect(exportWorkspaceConversation).toHaveBeenCalledWith(7, "markdown");
    expect(createObjectURL).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    click.mockRestore();
    vi.unstubAllGlobals();
  });
});
