import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import fc from "fast-check";

import type { ConversationItem } from "@/components/research/lib/research-page-types";

/**
 * Feature: clara-chat-redesign, Property P4 (no turn loss); Requirement 3.3.
 *
 * `useChatTurns` must persist every appended turn into both the visible list and
 * the per-conversation local cache exactly once (idempotent on turn id), and must
 * recover cached turns when a server load returns empty or fails. These tests
 * mock the existing transport (`lib/research`) so the hook is exercised in
 * isolation without a backend (Requirement 8.3).
 */

const listResearchConversationMessages = vi.fn();

vi.mock("@/lib/research", () => ({
  listResearchConversationMessages,
}));

vi.mock("@/components/research/lib/research-page-helpers", () => ({
  createConversationItemFromPersisted: (persisted: {
    id: string;
    query: string;
    createdAt?: number;
  }): ConversationItem => ({
    id: persisted.id,
    query: persisted.query,
    createdAt: persisted.createdAt ?? 0,
    result: { tier: "tier1", answer: `answer:${persisted.query}`, debug: null },
  }),
}));

async function loadHook() {
  const mod = await import("@/app/chat/_v2/hooks/useChatTurns");
  return mod.useChatTurns;
}

function makeTurn(id: string): ConversationItem {
  return {
    id,
    query: `q-${id}`,
    createdAt: 0,
    result: { tier: "tier1", answer: `a-${id}`, debug: null },
  };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe("useChatTurns — no turn loss (Property P4)", () => {
  it("appends a turn into both the visible list and the local cache exactly once", async () => {
    const useChatTurns = await loadHook();
    const { result } = renderHook(() => useChatTurns());

    act(() => {
      result.current.appendTurn(42, makeTurn("t1"));
    });

    expect(result.current.turns.map((t) => t.id)).toEqual(["t1"]);
    expect(result.current.cachedTurns(42).map((t) => t.id)).toEqual(["t1"]);

    // Re-appending the same turn id is idempotent in the cache (no dup).
    act(() => {
      result.current.appendTurn(42, makeTurn("t1"));
    });
    expect(result.current.cachedTurns(42).map((t) => t.id)).toEqual(["t1"]);
  });

  it("recovers cached turns when a server load returns empty", async () => {
    listResearchConversationMessages.mockResolvedValue([]);
    const useChatTurns = await loadHook();
    const { result } = renderHook(() => useChatTurns());

    act(() => {
      result.current.appendTurn(7, makeTurn("cached-1"));
    });

    let loaded: ConversationItem[] = [];
    await act(async () => {
      loaded = await result.current.load(7);
    });

    expect(loaded.map((t) => t.id)).toEqual(["cached-1"]);
    expect(result.current.turns.map((t) => t.id)).toEqual(["cached-1"]);
  });

  it("recovers cached turns (no rethrow) when a server load throws but a cache exists", async () => {
    listResearchConversationMessages.mockRejectedValue(new Error("network"));
    const useChatTurns = await loadHook();
    const { result } = renderHook(() => useChatTurns());

    act(() => {
      result.current.appendTurn(9, makeTurn("cached-x"));
    });

    let loaded: ConversationItem[] = [];
    await act(async () => {
      loaded = await result.current.load(9);
    });

    // The cache shields the user from the transport error: no turn is lost.
    expect(loaded.map((t) => t.id)).toEqual(["cached-x"]);
    expect(result.current.turns.map((t) => t.id)).toEqual(["cached-x"]);
  });

  it("rethrows when a server load fails and no cache exists", async () => {
    listResearchConversationMessages.mockRejectedValue(new Error("network"));
    const useChatTurns = await loadHook();
    const { result } = renderHook(() => useChatTurns());

    await act(async () => {
      await expect(result.current.load(999)).rejects.toThrow("network");
    });
  });

  it("Property: appending N distinct turns never drops or duplicates a turn", async () => {
    const useChatTurns = await loadHook();
    await fc.assert(
      fc.asyncProperty(
        fc.uniqueArray(fc.string({ minLength: 1, maxLength: 8 }), {
          minLength: 1,
          maxLength: 12,
        }),
        async (ids) => {
          const { result, unmount } = renderHook(() => useChatTurns());
          for (const id of ids) {
            act(() => {
              result.current.appendTurn(1, makeTurn(id));
            });
          }
          const visible = result.current.turns.map((t) => t.id);
          const cached = result.current.cachedTurns(1).map((t) => t.id);
          unmount();
          return (
            visible.length === ids.length &&
            visible.join("|") === ids.join("|") &&
            cached.join("|") === ids.join("|")
          );
        },
      ),
      { numRuns: 60 },
    );
  });
});
