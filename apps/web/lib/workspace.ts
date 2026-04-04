import api from "@/lib/http-client";

export type WorkspaceSummary = {
  conversations: number;
  messages: number;
  folders: number;
  channels: number;
  notes: number;
  pinned_notes: number;
};

export type WorkspaceFolder = {
  id: number;
  name: string;
  slug: string;
  description: string;
  color: string;
  icon: string;
  sort_order: number;
  is_archived: boolean;
  conversation_count: number;
  created_at: string;
  updated_at: string;
};

export type WorkspaceChannel = {
  id: number;
  name: string;
  slug: string;
  description: string;
  visibility: "private" | "team" | "public";
  color: string;
  icon: string;
  sort_order: number;
  is_archived: boolean;
  conversation_count: number;
  created_at: string;
  updated_at: string;
};

export type WorkspaceConversationItem = {
  conversation_id: number;
  title: string;
  preview: string;
  query_id?: number | null;
  message_count: number;
  created_at: string;
  last_message_at?: string | null;
  folder_id?: number | null;
  channel_id?: number | null;
  is_favorite: boolean;
};

export type WorkspaceNote = {
  id: number;
  title: string;
  content_markdown: string;
  summary: string;
  tags: string[];
  is_pinned: boolean;
  conversation_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type WorkspaceSuggestion = {
  id: string;
  text: string;
  category: string;
  score: number;
};

export type WorkspaceSearchResponse = {
  query: string;
  conversations: WorkspaceConversationItem[];
  notes: WorkspaceNote[];
  folders: WorkspaceFolder[];
  channels: WorkspaceChannel[];
  suggestions: WorkspaceSuggestion[];
};

export type WorkspaceConversationShare = {
  conversation_id: number;
  share_token: string;
  public_url: string;
  is_active: boolean;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkspacePublicConversationMessage = {
  query_id: number;
  role: string;
  query: string;
  answer: string;
  created_at: string;
};

export type WorkspacePublicConversation = {
  conversation_id: number;
  title: string;
  owner_label: string;
  expires_at?: string | null;
  messages: WorkspacePublicConversationMessage[];
};

export async function getWorkspaceSummary(): Promise<WorkspaceSummary> {
  const { data } = await api.get<WorkspaceSummary>("/api/v1/workspace/summary");
  return data;
}

export async function listWorkspaceFolders(includeArchived = false): Promise<WorkspaceFolder[]> {
  const { data } = await api.get<WorkspaceFolder[]>("/api/v1/workspace/folders", {
    params: { include_archived: includeArchived },
  });
  return data;
}

export async function createWorkspaceFolder(payload: {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
}): Promise<WorkspaceFolder> {
  const { data } = await api.post<WorkspaceFolder>("/api/v1/workspace/folders", payload);
  return data;
}

export async function updateWorkspaceFolder(
  folderId: number,
  payload: {
    name?: string;
    description?: string;
    color?: string;
    icon?: string;
    sortOrder?: number;
    isArchived?: boolean;
  }
): Promise<WorkspaceFolder> {
  const { data } = await api.patch<WorkspaceFolder>(`/api/v1/workspace/folders/${folderId}`, {
    name: payload.name,
    description: payload.description,
    color: payload.color,
    icon: payload.icon,
    sort_order: payload.sortOrder,
    is_archived: payload.isArchived,
  });
  return data;
}

export async function deleteWorkspaceFolder(folderId: number): Promise<{ deleted: boolean }> {
  const { data } = await api.delete<{ deleted: boolean }>(`/api/v1/workspace/folders/${folderId}`);
  return data;
}

export async function listWorkspaceChannels(includeArchived = false): Promise<WorkspaceChannel[]> {
  const { data } = await api.get<WorkspaceChannel[]>("/api/v1/workspace/channels", {
    params: { include_archived: includeArchived },
  });
  return data;
}

export async function createWorkspaceChannel(payload: {
  name: string;
  description?: string;
  visibility?: "private" | "team" | "public";
  color?: string;
  icon?: string;
}): Promise<WorkspaceChannel> {
  const { data } = await api.post<WorkspaceChannel>("/api/v1/workspace/channels", payload);
  return data;
}

export async function updateWorkspaceChannel(
  channelId: number,
  payload: {
    name?: string;
    description?: string;
    visibility?: "private" | "team" | "public";
    color?: string;
    icon?: string;
    sortOrder?: number;
    isArchived?: boolean;
  }
): Promise<WorkspaceChannel> {
  const { data } = await api.patch<WorkspaceChannel>(`/api/v1/workspace/channels/${channelId}`, {
    name: payload.name,
    description: payload.description,
    visibility: payload.visibility,
    color: payload.color,
    icon: payload.icon,
    sort_order: payload.sortOrder,
    is_archived: payload.isArchived,
  });
  return data;
}

export async function deleteWorkspaceChannel(channelId: number): Promise<{ deleted: boolean }> {
  const { data } = await api.delete<{ deleted: boolean }>(`/api/v1/workspace/channels/${channelId}`);
  return data;
}

export async function listWorkspaceConversations(params?: {
  limit?: number;
  query?: string;
  folderId?: number;
  channelId?: number;
  favoritesOnly?: boolean;
}): Promise<WorkspaceConversationItem[]> {
  const { data } = await api.get<{ items: WorkspaceConversationItem[] }>("/api/v1/workspace/conversations", {
    params: {
      limit: params?.limit ?? 60,
      query: params?.query,
      folder_id: params?.folderId,
      channel_id: params?.channelId,
      favorites_only: params?.favoritesOnly ?? false,
    },
  });
  return data.items ?? [];
}

export async function updateWorkspaceConversationMeta(
  conversationId: number,
  payload: {
    folderId?: number | null;
    channelId?: number | null;
    isFavorite?: boolean;
    touched?: boolean;
  }
): Promise<{
  conversation_id: number;
  folder_id?: number | null;
  channel_id?: number | null;
  is_favorite: boolean;
  last_opened_at?: string | null;
  updated_at: string;
}> {
  const body: Record<string, unknown> = {
    touched: payload.touched ?? true,
  };
  if ("folderId" in payload) body.folder_id = payload.folderId ?? null;
  if ("channelId" in payload) body.channel_id = payload.channelId ?? null;
  if ("isFavorite" in payload) body.is_favorite = payload.isFavorite;

  const { data } = await api.patch(`/api/v1/workspace/conversations/${conversationId}/meta`, body);
  return data;
}

export async function updateWorkspaceConversation(
  conversationId: number,
  payload: { title: string }
): Promise<WorkspaceConversationItem> {
  const { data } = await api.patch<WorkspaceConversationItem>(
    `/api/v1/workspace/conversations/${conversationId}`,
    { title: payload.title }
  );
  return data;
}

export async function deleteWorkspaceConversation(
  conversationId: number
): Promise<{ deleted: boolean }> {
  const { data } = await api.delete<{ deleted: boolean }>(
    `/api/v1/workspace/conversations/${conversationId}`
  );
  return data;
}

export async function createWorkspaceConversationShare(
  conversationId: number,
  payload?: { expiresInHours?: number; rotate?: boolean }
): Promise<WorkspaceConversationShare> {
  const { data } = await api.post<WorkspaceConversationShare>(
    `/api/v1/workspace/conversations/${conversationId}/share`,
    {
      expires_in_hours: payload?.expiresInHours,
      rotate: payload?.rotate ?? false,
    }
  );
  return data;
}

export async function getWorkspaceConversationShare(
  conversationId: number
): Promise<WorkspaceConversationShare> {
  const { data } = await api.get<WorkspaceConversationShare>(
    `/api/v1/workspace/conversations/${conversationId}/share`
  );
  return data;
}

export async function revokeWorkspaceConversationShare(
  conversationId: number
): Promise<{ revoked: boolean }> {
  const { data } = await api.delete<{ revoked: boolean }>(
    `/api/v1/workspace/conversations/${conversationId}/share`
  );
  return data;
}

export async function getWorkspacePublicConversation(
  shareToken: string
): Promise<WorkspacePublicConversation> {
  const { data } = await api.get<WorkspacePublicConversation>(
    `/api/v1/workspace/public/conversations/${shareToken}`
  );
  return data;
}

export async function listWorkspaceNotes(params?: {
  limit?: number;
  query?: string;
  conversationId?: number;
}): Promise<WorkspaceNote[]> {
  const { data } = await api.get<WorkspaceNote[]>("/api/v1/workspace/notes", {
    params: {
      limit: params?.limit ?? 80,
      query: params?.query,
      conversation_id: params?.conversationId,
    },
  });
  return data;
}

export async function createWorkspaceNote(payload: {
  title: string;
  contentMarkdown?: string;
  tags?: string[];
  isPinned?: boolean;
  conversationId?: number | null;
}): Promise<WorkspaceNote> {
  const { data } = await api.post<WorkspaceNote>("/api/v1/workspace/notes", {
    title: payload.title,
    content_markdown: payload.contentMarkdown ?? "",
    tags: payload.tags ?? [],
    is_pinned: payload.isPinned ?? false,
    conversation_id: payload.conversationId ?? null,
  });
  return data;
}

export async function updateWorkspaceNote(
  noteId: number,
  payload: {
    title?: string;
    contentMarkdown?: string;
    tags?: string[];
    isPinned?: boolean;
    conversationId?: number | null;
  }
): Promise<WorkspaceNote> {
  const { data } = await api.patch<WorkspaceNote>(`/api/v1/workspace/notes/${noteId}`, {
    title: payload.title,
    content_markdown: payload.contentMarkdown,
    tags: payload.tags,
    is_pinned: payload.isPinned,
    conversation_id: payload.conversationId,
  });
  return data;
}

export async function deleteWorkspaceNote(noteId: number): Promise<{ deleted: boolean }> {
  const { data } = await api.delete<{ deleted: boolean }>(`/api/v1/workspace/notes/${noteId}`);
  return data;
}

export async function listWorkspaceSuggestions(limit = 10): Promise<WorkspaceSuggestion[]> {
  const { data } = await api.get<{ items: WorkspaceSuggestion[] }>("/api/v1/workspace/suggestions", {
    params: { limit },
  });
  return data.items ?? [];
}

export async function searchWorkspace(query: string, limit = 12): Promise<WorkspaceSearchResponse> {
  const { data } = await api.get<WorkspaceSearchResponse>("/api/v1/workspace/search", {
    params: { q: query, limit },
  });
  return data;
}
