"use client";

import { useCallback, useState } from "react";

import {
  WorkspaceConversationShareListItem,
  WorkspaceNote,
  WorkspaceSearchResponse,
  createWorkspaceConversationShare,
  createWorkspaceNote,
  deleteWorkspaceNote,
  exportWorkspaceConversation,
  exportWorkspaceDocxFromMarkdown,
  listWorkspaceNotes,
  listWorkspaceShares,
  revokeWorkspaceConversationShare,
  searchWorkspace,
} from "@/lib/workspace";
import {
  buildConversationMarkdownExport,
  localWorkspaceSearch,
  parsePromptText,
  triggerBlobDownload,
} from "@/app/chat/_v2/lib/chat-format";
import type { ConversationItem } from "@/components/research/lib/research-page-types";

/**
 * Workspace side-surface state (notes / shares / export) for the rebuilt CLARA
 * Chat (CHAT_V2). Reuses the existing workspace client unchanged (Requirement
 * 6.2, 8.3). All loads are best-effort: a failure never throws into the chat
 * flow, it just leaves the relevant list empty so the workspace stays optional
 * progressive-disclosure (Requirement 2.4).
 */

export type UseWorkspace = {
  notes: WorkspaceNote[];
  shares: WorkspaceConversationShareListItem[];
  searchResults: WorkspaceSearchResponse | null;
  loadNotes: () => Promise<void>;
  loadShares: () => Promise<void>;
  saveNote: (payload: {
    title: string;
    contentMarkdown?: string;
    tags?: string[];
    conversationId?: number | null;
  }) => Promise<void>;
  removeNote: (noteId: number) => Promise<void>;
  share: (
    conversationId: number,
    options?: { expiresInHours?: number; rotate?: boolean },
  ) => Promise<WorkspaceConversationShareListItem[] | null>;
  revokeShare: (conversationId: number) => Promise<void>;
  exportConversation: (
    conversationId: number,
    format: "markdown" | "docx",
    fallbackTurns: ConversationItem[],
    title: string,
  ) => Promise<void>;
  search: (query: string) => Promise<WorkspaceSearchResponse | null>;
  clearSearch: () => void;
};

export function useWorkspace(options?: {
  apiUnavailable?: boolean;
}): UseWorkspace {
  const apiUnavailable = options?.apiUnavailable ?? false;
  const [notes, setNotes] = useState<WorkspaceNote[]>([]);
  const [shares, setShares] = useState<WorkspaceConversationShareListItem[]>(
    [],
  );
  const [searchResults, setSearchResults] =
    useState<WorkspaceSearchResponse | null>(null);

  const loadNotes = useCallback(async () => {
    try {
      setNotes(await listWorkspaceNotes({ limit: 100 }));
    } catch {
      // Notes are optional; never block the chat flow.
    }
  }, []);

  const loadShares = useCallback(async () => {
    if (apiUnavailable) {
      setShares([]);
      return;
    }
    try {
      setShares(await listWorkspaceShares({ limit: 80, activeOnly: false }));
    } catch {
      // Shares are optional.
    }
  }, [apiUnavailable]);

  const saveNote = useCallback(
    async (payload: {
      title: string;
      contentMarkdown?: string;
      tags?: string[];
      conversationId?: number | null;
    }) => {
      const created = await createWorkspaceNote(payload);
      setNotes((prev) => [created, ...prev]);
    },
    [],
  );

  const removeNote = useCallback(async (noteId: number) => {
    await deleteWorkspaceNote(noteId);
    setNotes((prev) => prev.filter((note) => note.id !== noteId));
  }, []);

  const share = useCallback(
    async (
      conversationId: number,
      options?: { expiresInHours?: number; rotate?: boolean },
    ) => {
      if (apiUnavailable) return null;
      await createWorkspaceConversationShare(conversationId, {
        expiresInHours: options?.expiresInHours ?? 168,
        rotate: options?.rotate ?? false,
      });
      const next = await listWorkspaceShares({ limit: 80, activeOnly: false });
      setShares(next);
      return next;
    },
    [apiUnavailable],
  );

  const revokeShare = useCallback(
    async (conversationId: number) => {
      if (apiUnavailable) return;
      await revokeWorkspaceConversationShare(conversationId);
      setShares(await listWorkspaceShares({ limit: 80, activeOnly: false }));
    },
    [apiUnavailable],
  );

  const exportConversation = useCallback(
    async (
      conversationId: number,
      format: "markdown" | "docx",
      fallbackTurns: ConversationItem[],
      title: string,
    ) => {
      const localMarkdown = buildConversationMarkdownExport(
        title,
        fallbackTurns,
      );
      try {
        if (!apiUnavailable) {
          const blob = await exportWorkspaceConversation(
            conversationId,
            format,
          );
          triggerBlobDownload(
            blob,
            `conversation-${conversationId}.${format === "markdown" ? "md" : "docx"}`,
          );
          return;
        }
        if (format === "markdown") {
          triggerBlobDownload(
            new Blob([localMarkdown], { type: "text/markdown;charset=utf-8" }),
            `conversation-${conversationId}.md`,
          );
          return;
        }
        const docx = await exportWorkspaceDocxFromMarkdown({
          markdown: localMarkdown,
          title: `conversation-${conversationId}`,
        });
        triggerBlobDownload(docx, `conversation-${conversationId}.docx`);
      } catch {
        // Last-resort fallback so the user never loses content.
        triggerBlobDownload(
          new Blob([localMarkdown], { type: "text/markdown;charset=utf-8" }),
          `conversation-${conversationId}.md`,
        );
      }
    },
    [apiUnavailable],
  );

  const search = useCallback(
    async (query: string): Promise<WorkspaceSearchResponse | null> => {
      const normalized = parsePromptText(query);
      if (!normalized) {
        setSearchResults(null);
        return null;
      }
      if (apiUnavailable) {
        const local = localWorkspaceSearch(notes, normalized);
        setSearchResults(local);
        return local;
      }
      try {
        const result = await searchWorkspace(normalized);
        setSearchResults(result);
        return result;
      } catch {
        // Search is best-effort: fall back to the in-memory notes the chat
        // already holds so the user is never left without results.
        const local = localWorkspaceSearch(notes, normalized);
        setSearchResults(local);
        return local;
      }
    },
    [apiUnavailable, notes],
  );

  const clearSearch = useCallback(() => setSearchResults(null), []);

  return {
    notes,
    shares,
    searchResults,
    loadNotes,
    loadShares,
    saveNote,
    removeNote,
    share,
    revokeShare,
    exportConversation,
    search,
    clearSearch,
  };
}
