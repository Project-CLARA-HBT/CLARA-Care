"use client";

import { useCallback, useState } from "react";

import {
  createConversationItemFromPersisted,
} from "@/components/research/lib/research-page-helpers";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import { listResearchConversationMessages } from "@/lib/research";

/**
 * Per-conversation turn state for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Loads persisted turns for a conversation and keeps a local cache keyed by
 * conversation id so a turn is never lost when persistence fails or the server
 * list is temporarily empty (design Property P4; Requirement 3.3). The
 * `appendTurn` helper persists into both the visible list and the local cache
 * exactly once.
 */

export type UseChatTurns = {
  turns: ConversationItem[];
  isLoading: boolean;
  localCache: Record<number, ConversationItem[]>;
  setActive: (turns: ConversationItem[]) => void;
  clear: () => void;
  appendTurn: (conversationId: number | null, turn: ConversationItem) => void;
  load: (conversationId: number) => Promise<ConversationItem[]>;
  cachedTurns: (conversationId: number) => ConversationItem[];
};

export function useChatTurns(): UseChatTurns {
  const [turns, setTurns] = useState<ConversationItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [localCache, setLocalCache] = useState<Record<number, ConversationItem[]>>({});

  const cachedTurns = useCallback(
    (conversationId: number): ConversationItem[] => {
      const cached = localCache[conversationId];
      return Array.isArray(cached) ? cached : [];
    },
    [localCache]
  );

  const setActive = useCallback((next: ConversationItem[]) => {
    setTurns(next);
  }, []);

  const clear = useCallback(() => {
    setTurns([]);
  }, []);

  const appendTurn = useCallback((conversationId: number | null, turn: ConversationItem) => {
    setTurns((prev) => [...prev, turn]);
    if (conversationId === null) return;
    setLocalCache((prev) => {
      const existing = Array.isArray(prev[conversationId]) ? prev[conversationId] : [];
      // Persist into the local cache exactly once (idempotent on turn id).
      if (existing.some((item) => item.id === turn.id)) return prev;
      return { ...prev, [conversationId]: [...existing, turn] };
    });
  }, []);

  const load = useCallback(
    async (conversationId: number): Promise<ConversationItem[]> => {
      setIsLoading(true);
      try {
        const rows = await listResearchConversationMessages(conversationId, 180);
        if (!rows.length) {
          const cached = localCache[conversationId];
          if (Array.isArray(cached) && cached.length) {
            setTurns(cached);
            return cached;
          }
          setTurns([]);
          return [];
        }
        const loaded = rows.map((row, index) => {
          const parsed = createConversationItemFromPersisted({
            id: String(conversationId),
            queryId: row.queryId,
            query: row.query,
            result: row.result,
            tier: row.tier,
            createdAt: row.createdAt,
          });
          return { ...parsed, id: `${conversationId}-${row.queryId ?? index}` };
        });
        setTurns(loaded);
        return loaded;
      } catch (cause) {
        const cached = localCache[conversationId];
        if (Array.isArray(cached) && cached.length) {
          setTurns(cached);
          return cached;
        }
        setTurns([]);
        throw cause;
      } finally {
        setIsLoading(false);
      }
    },
    [localCache]
  );

  return {
    turns,
    isLoading,
    localCache,
    setActive,
    clear,
    appendTurn,
    load,
    cachedTurns,
  };
}
