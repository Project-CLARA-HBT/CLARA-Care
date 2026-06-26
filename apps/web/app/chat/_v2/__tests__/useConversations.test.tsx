import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import type { WorkspaceConversationItem } from "@/lib/workspace";

/**
 * Feature: clara-chat-redesign; Requirement 6.1, 6.5, 8.3.
 *
 * `useConversations` owns the server list + the local-fallback list and exposes
 * a merged, deduplicated, newest-first view. When the workspace API is
 * unavailable (a 404-like signal), it transparently falls back to the research
 * conversations client (Requirement 6.5). It reuses the existing clients
 * unchanged (Requirement 8.3); both are mocked here so the hook runs in
 * isolation.
 */

const listWorkspaceConversations = vi.fn();
const updateWorkspaceConversation = vi.fn();
const deleteWorkspaceConversation = vi.fn();
const updateWorkspaceConversationMeta = vi.fn();
const listResearchConversations = vi.fn();

vi.mock("@/lib/workspace", () => ({
  listWorkspaceConversations,
  updateWorkspaceConversation,
  deleteWorkspaceConversation,
  updateWorkspaceConversationMeta,
}));

vi.mock("@/lib/research", () => ({
  listResearchConversations,
}));

async function loadHook() {
  const mod = await import("@/app/chat/_v2/hooks/useConversations");
  return mod.useConversations;
}

function makeConversation(
  id: number,
  overrides: Partial<WorkspaceConversationItem> = {},
): WorkspaceConversationItem {
  return {
    conversation_id: id,
    title: `c-${id}`,
    preview: `p-${id}`,
    query_id: null,
    message_count: 1,
    created_at: "2026-01-01T00:00:00.000Z",
    last_message_at: "2026-01-01T00:00:00.000Z",
    folder_id: null,
    channel_id: null,
    is_favorite: false,
    ...overrides,
  };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe("useConversations", () => {
  it("loads server conversations and exposes them in the merged view", async () => {
    listWorkspaceConversations.mockResolvedValue([
      makeConversation(1, { last_message_at: "2026-03-01T00:00:00.000Z" }),
      makeConversation(2, { last_message_at: "2026-05-01T00:00:00.000Z" }),
    ]);
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });

    expect(result.current.merged.map((c) => c.conversation_id)).toEqual([2, 1]);
    expect(result.current.apiUnavailable).toBe(false);
  });

  it("merges a local-fallback turn with server data, deduped and newest-first", async () => {
    listWorkspaceConversations.mockResolvedValue([
      makeConversation(1, { title: "server-1", last_message_at: "2026-03-01T00:00:00.000Z" }),
    ]);
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    act(() => {
      result.current.upsertLocal(
        makeConversation(9, { last_message_at: "2026-06-01T00:00:00.000Z" }),
      );
    });

    const ids = result.current.merged.map((c) => c.conversation_id);
    expect(ids).toEqual([9, 1]);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("falls back to the research client on a 404-like workspace error", async () => {
    listWorkspaceConversations.mockRejectedValue(new Error("not found"));
    listResearchConversations.mockResolvedValue([
      { id: 5, query: "research q", queryId: 50, createdAt: Date.now() },
    ]);
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });

    await waitFor(() => expect(result.current.apiUnavailable).toBe(true));
    expect(result.current.merged.map((c) => c.conversation_id)).toEqual([5]);
  });

  it("patch updates a conversation in place without adding rows", async () => {
    listWorkspaceConversations.mockResolvedValue([makeConversation(1)]);
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    act(() => {
      result.current.patch(1, { is_favorite: true });
    });

    expect(result.current.merged).toHaveLength(1);
    expect(result.current.merged[0].is_favorite).toBe(true);
  });

  it("create adds a local-only conversation and makes it active", async () => {
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    let created: WorkspaceConversationItem | undefined;
    act(() => {
      created = result.current.create("Draft topic");
    });

    expect(created?.title).toBe("Draft topic");
    expect(result.current.activeId).toBe(created?.conversation_id);
    expect(result.current.localIds.has(created!.conversation_id)).toBe(true);
    expect(result.current.merged.map((c) => c.conversation_id)).toContain(
      created?.conversation_id,
    );
  });

  it("rename calls the workspace client for a server conversation and patches in place", async () => {
    listWorkspaceConversations.mockResolvedValue([makeConversation(1, { title: "old" })]);
    updateWorkspaceConversation.mockResolvedValue(makeConversation(1, { title: "new title" }));
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.rename(1, "new title");
    });

    expect(updateWorkspaceConversation).toHaveBeenCalledWith(1, { title: "new title" });
    expect(result.current.merged[0].title).toBe("new title");
  });

  it("rename of a local-only conversation stays local (no API call)", async () => {
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    let created: WorkspaceConversationItem | undefined;
    act(() => {
      created = result.current.create("draft");
    });
    await act(async () => {
      await result.current.rename(created!.conversation_id, "renamed locally");
    });

    expect(updateWorkspaceConversation).not.toHaveBeenCalled();
    expect(result.current.merged[0].title).toBe("renamed locally");
  });

  it("remove deletes a server conversation, drops it, and clears active selection", async () => {
    listWorkspaceConversations.mockResolvedValue([makeConversation(1)]);
    deleteWorkspaceConversation.mockResolvedValue({ deleted: true });
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    act(() => {
      result.current.select(1);
    });
    await act(async () => {
      await result.current.remove(1);
    });

    expect(deleteWorkspaceConversation).toHaveBeenCalledWith(1);
    expect(result.current.merged).toHaveLength(0);
    expect(result.current.activeId).toBeNull();
  });

  it("setFavorite uses the meta client and reflects the server result", async () => {
    listWorkspaceConversations.mockResolvedValue([makeConversation(1, { is_favorite: false })]);
    updateWorkspaceConversationMeta.mockResolvedValue({
      conversation_id: 1,
      is_favorite: true,
      updated_at: "2026-01-01T00:00:00.000Z",
    });
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.setFavorite(1, true);
    });

    expect(updateWorkspaceConversationMeta).toHaveBeenCalledWith(1, { isFavorite: true });
    expect(result.current.merged[0].is_favorite).toBe(true);
  });

  it("setFolder uses the meta client and patches folder_id", async () => {
    listWorkspaceConversations.mockResolvedValue([makeConversation(1, { folder_id: null })]);
    updateWorkspaceConversationMeta.mockResolvedValue({
      conversation_id: 1,
      folder_id: 7,
      is_favorite: false,
      updated_at: "2026-01-01T00:00:00.000Z",
    });
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.setFolder(1, 7);
    });

    expect(updateWorkspaceConversationMeta).toHaveBeenCalledWith(1, { folderId: 7 });
    expect(result.current.merged[0].folder_id).toBe(7);
  });

  it("favorite/folder mutations stay local when the workspace API is unavailable", async () => {
    listWorkspaceConversations.mockRejectedValue(new Error("404 not found"));
    listResearchConversations.mockResolvedValue([
      { id: 5, query: "research q", queryId: 50, createdAt: Date.now() },
    ]);
    const useConversations = await loadHook();
    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.load();
    });
    await waitFor(() => expect(result.current.apiUnavailable).toBe(true));

    await act(async () => {
      await result.current.setFavorite(5, true);
      await result.current.remove(5);
    });

    expect(updateWorkspaceConversationMeta).not.toHaveBeenCalled();
    expect(deleteWorkspaceConversation).not.toHaveBeenCalled();
    expect(result.current.merged).toHaveLength(0);
  });
});
