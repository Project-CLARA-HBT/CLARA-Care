"use client";

import { useCallback, useMemo, useState } from "react";

import {
  WorkspaceConversationItem,
  deleteWorkspaceConversation,
  listWorkspaceConversations,
  updateWorkspaceConversation,
  updateWorkspaceConversationMeta,
} from "@/lib/workspace";
import { listResearchConversations } from "@/lib/research";
import {
  LOCAL_WORKSPACE_MAX_ITEMS,
  asConversationId,
  isNotFoundLikeError,
  mergeConversations,
  parsePromptText,
} from "@/app/chat/_v2/lib/chat-format";

/**
 * Conversation list state for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Owns the server conversation list, the local-fallback list (used when the
 * workspace API is unavailable — Requirement 6.5), and exposes a merged,
 * deduplicated, newest-first view (Requirement 6.1). Beyond loading, it owns
 * the conversation CRUD surface — create / select / rename / delete / favorite /
 * folder organization (Requirement 6.1) — each of which transparently degrades
 * to a local-only mutation when the workspace API is unavailable or the target
 * conversation only exists locally (Requirement 6.5). Reuses the existing
 * workspace + research clients unchanged (Requirement 8.3).
 */

/** Maps a persisted research row into a workspace conversation shape. */
export function researchRowToConversation(row: {
  id: string | number;
  query?: string;
  queryId?: string | number | null;
  createdAt?: number;
}): WorkspaceConversationItem {
  const created = new Date(row.createdAt || Date.now()).toISOString();
  const preview = row.query || "Research conversation";
  const normalizedId = Math.trunc(Number(row.id));
  const normalizedQueryId = row.queryId ? Math.trunc(Number(row.queryId)) : null;
  return {
    conversation_id: Number.isFinite(normalizedId) ? normalizedId : Date.now(),
    title: preview.slice(0, 255),
    preview: preview.slice(0, 260),
    query_id: normalizedQueryId !== null && Number.isFinite(normalizedQueryId) ? normalizedQueryId : null,
    message_count: 1,
    created_at: created,
    last_message_at: created,
    folder_id: null,
    channel_id: null,
    is_favorite: false,
  };
}

/** Builds a fresh, local-only conversation placeholder with a unique id. */
export function makeLocalConversation(
  title: string,
  now: number = Date.now(),
): WorkspaceConversationItem {
  const created = new Date(now).toISOString();
  const trimmed = parsePromptText(title) ?? "New conversation";
  return {
    conversation_id: now,
    title: trimmed.slice(0, 255),
    preview: trimmed.slice(0, 260),
    query_id: null,
    message_count: 0,
    created_at: created,
    last_message_at: created,
    folder_id: null,
    channel_id: null,
    is_favorite: false,
  };
}

export type UseConversations = {
  conversations: WorkspaceConversationItem[];
  merged: WorkspaceConversationItem[];
  localIds: Set<number>;
  activeId: number | null;
  isLoading: boolean;
  apiUnavailable: boolean;
  load: (options?: { folderId?: number | null }) => Promise<WorkspaceConversationItem[]>;
  select: (conversationId: number | null) => void;
  create: (title?: string) => WorkspaceConversationItem;
  rename: (conversationId: number, title: string) => Promise<void>;
  remove: (conversationId: number) => Promise<void>;
  setFavorite: (conversationId: number, isFavorite: boolean) => Promise<void>;
  setFolder: (conversationId: number, folderId: number | null) => Promise<void>;
  upsertLocal: (item: WorkspaceConversationItem) => void;
  removeLocal: (conversationId: number) => void;
  patch: (conversationId: number, patch: Partial<WorkspaceConversationItem>) => void;
};

export function useConversations(): UseConversations {
  const [conversations, setConversations] = useState<WorkspaceConversationItem[]>([]);
  const [localFallback, setLocalFallback] = useState<WorkspaceConversationItem[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [apiUnavailable, setApiUnavailable] = useState(false);

  const merged = useMemo(
    () => mergeConversations(conversations, localFallback),
    [conversations, localFallback]
  );

  // Conversation ids that exist only in the local-fallback list (i.e. not yet
  // persisted server-side). Mutations targeting these must stay local.
  const localIds = useMemo(() => {
    const serverIds = new Set(conversations.map((row) => row.conversation_id));
    return new Set(
      localFallback
        .map((row) => row.conversation_id)
        .filter((id) => !serverIds.has(id))
    );
  }, [conversations, localFallback]);

  const load = useCallback(
    async (options?: { folderId?: number | null }): Promise<WorkspaceConversationItem[]> => {
      setIsLoading(true);
      try {
        if (apiUnavailable) {
          const rows = await listResearchConversations(80);
          const items = rows.map(researchRowToConversation);
          setConversations(items);
          return items;
        }
        const items = await listWorkspaceConversations({
          limit: 80,
          folderId: options?.folderId ?? undefined,
          favoritesOnly: false,
        });
        setApiUnavailable(false);
        setConversations(items);
        return items;
      } catch (cause) {
        if (isNotFoundLikeError(cause)) {
          setApiUnavailable(true);
          try {
            const rows = await listResearchConversations(80);
            const items = rows.map(researchRowToConversation);
            setConversations(items);
            return items;
          } catch {
            setConversations([]);
            return [];
          }
        }
        throw cause;
      } finally {
        setIsLoading(false);
      }
    },
    [apiUnavailable]
  );

  const upsertLocal = useCallback((item: WorkspaceConversationItem) => {
    setLocalFallback((prev) => {
      const filtered = prev.filter((row) => row.conversation_id !== item.conversation_id);
      return [item, ...filtered].slice(0, LOCAL_WORKSPACE_MAX_ITEMS);
    });
  }, []);

  const removeLocal = useCallback((conversationId: number) => {
    setLocalFallback((prev) => prev.filter((row) => row.conversation_id !== conversationId));
    setConversations((prev) => prev.filter((row) => row.conversation_id !== conversationId));
  }, []);

  const patch = useCallback(
    (conversationId: number, value: Partial<WorkspaceConversationItem>) => {
      const apply = (rows: WorkspaceConversationItem[]) =>
        rows.map((row) =>
          row.conversation_id === conversationId ? { ...row, ...value } : row
        );
      setConversations(apply);
      setLocalFallback(apply);
    },
    []
  );

  const select = useCallback((conversationId: number | null) => {
    setActiveId(asConversationId(conversationId));
  }, []);

  const create = useCallback(
    (title?: string): WorkspaceConversationItem => {
      const item = makeLocalConversation(title ?? "New conversation");
      upsertLocal(item);
      setActiveId(item.conversation_id);
      return item;
    },
    [upsertLocal]
  );

  // True when a mutation against this conversation must stay local-only:
  // either the workspace API is down, or the conversation is not yet persisted.
  const mustStayLocal = useCallback(
    (conversationId: number) => apiUnavailable || localIds.has(conversationId),
    [apiUnavailable, localIds]
  );

  const rename = useCallback(
    async (conversationId: number, title: string): Promise<void> => {
      const id = asConversationId(conversationId);
      const nextTitle = parsePromptText(title);
      if (id === null || nextTitle === null) return;
      if (mustStayLocal(id)) {
        patch(id, { title: nextTitle, preview: nextTitle });
        return;
      }
      const updated = await updateWorkspaceConversation(id, { title: nextTitle });
      patch(id, { title: updated.title ?? nextTitle });
    },
    [mustStayLocal, patch]
  );

  const remove = useCallback(
    async (conversationId: number): Promise<void> => {
      const id = asConversationId(conversationId);
      if (id === null) return;
      if (!mustStayLocal(id)) {
        await deleteWorkspaceConversation(id);
      }
      removeLocal(id);
      setActiveId((prev) => (prev === id ? null : prev));
    },
    [mustStayLocal, removeLocal]
  );

  const setFavorite = useCallback(
    async (conversationId: number, isFavorite: boolean): Promise<void> => {
      const id = asConversationId(conversationId);
      if (id === null) return;
      if (mustStayLocal(id)) {
        patch(id, { is_favorite: isFavorite });
        return;
      }
      const updated = await updateWorkspaceConversationMeta(id, { isFavorite });
      patch(id, { is_favorite: updated.is_favorite ?? isFavorite });
    },
    [mustStayLocal, patch]
  );

  const setFolder = useCallback(
    async (conversationId: number, folderId: number | null): Promise<void> => {
      const id = asConversationId(conversationId);
      if (id === null) return;
      const nextFolder = folderId === null ? null : asConversationId(folderId);
      if (mustStayLocal(id)) {
        patch(id, { folder_id: nextFolder });
        return;
      }
      const updated = await updateWorkspaceConversationMeta(id, { folderId: nextFolder });
      patch(id, { folder_id: updated.folder_id ?? nextFolder });
    },
    [mustStayLocal, patch]
  );

  return {
    conversations,
    merged,
    localIds,
    activeId,
    isLoading,
    apiUnavailable,
    load,
    select,
    create,
    rename,
    remove,
    setFavorite,
    setFolder,
    upsertLocal,
    removeLocal,
    patch,
  };
}
