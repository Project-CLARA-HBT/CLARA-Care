import api from "@/lib/http-client";

// CLARA Health Social platform web client (spec: .kiro/specs/clara-health-social).
//
// All routes 404 when the server-side `social_platform_enabled` flag is off, so
// callers treat a 404 as "feature unavailable" and hide the surface
// (fail-closed), exactly like the mobile client.

export interface SocialConsentStatus {
  consent_type: string;
  granted: boolean;
}

export interface SocialCommunity {
  id: number;
  slug: string;
  name: string;
  description: string;
  member_count: number;
  joined: boolean;
  is_curated?: boolean;
  created_at?: string;
}

export interface SocialPost {
  id: number;
  community_id: number;
  community_name?: string;
  author_handle: string;
  author_display_name?: string;
  is_verified_clinician?: boolean;
  title: string;
  body: string;
  moderation_status?: string;
  comment_count: number;
  reaction_count: number;
  user_reaction?: string | null;
  is_bookmarked?: boolean;
  reactions_breakdown?: Record<string, number>;
  created_at: string;
  updated_at?: string;
  tags?: string[];
}

export interface SocialComment {
  id: number;
  post_id: number;
  parent_id?: number | null;
  author_handle: string;
  author_display_name?: string;
  is_verified_clinician?: boolean;
  body: string;
  moderation_status?: string;
  created_at: string;
  updated_at?: string;
}

export interface SocialProfile {
  handle: string;
  display_name: string;
  bio: string;
  role_badge?: string;
  is_verified_clinician?: boolean;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export type ReactionKind = "helpful" | "relate" | "thanks";

export interface SocialReaction {
  id?: number;
  post_id: number;
  user_id?: number;
  kind: ReactionKind | string;
  created_at?: string;
}

export interface SocialBookmark {
  id?: number;
  user_id?: number;
  post_id: number;
  created_at?: string;
}

export interface SocialReport {
  id: number;
  reporter_id?: number;
  target_type: "post" | "comment" | string;
  target_id: number;
  reason: string;
  detail?: string;
  status: string;
  created_at: string;
  resolved_at?: string;
}

export interface PostFilters {
  community_id?: number;
  q?: string;
  author_role?: "all" | "verified" | "peer" | string;
  limit?: number;
  offset?: number;
}

export class SocialUnavailableError extends Error {
  constructor() {
    super("social_unavailable");
    this.name = "SocialUnavailableError";
  }
}

function isNotFound(error: unknown): boolean {
  const status =
    (error as { response?: { status?: number }; status?: number })?.response?.status ??
    (error as { status?: number })?.status;
  return status === 404;
}

/** True when a write was rejected by the pre-publish moderation gate (422). */
export function isSocialModerationBlock(error: unknown): boolean {
  const status =
    (error as { response?: { status?: number }; status?: number })?.response?.status ??
    (error as { status?: number })?.status;
  return status === 422;
}

/** Extract detailed server validation or moderation message if available. */
export function getSocialErrorMessage(error: unknown, fallbackMessage: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return fallbackMessage;
}

/** Checks if an author handle represents CLARA official or verified clinician. */
export function isClaraOfficial(handle: string): boolean {
  if (!handle) return false;
  const lower = handle.toLowerCase();
  return (
    lower.startsWith("clara") ||
    lower.startsWith("dr_") ||
    lower.startsWith("bs_") ||
    lower.startsWith("bacsi_") ||
    lower.startsWith("duocsi_") ||
    lower.startsWith("expert_") ||
    lower.startsWith("mod_") ||
    lower.includes("official")
  );
}

async function guarded<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (isNotFound(error)) throw new SocialUnavailableError();
    throw error;
  }
}

export async function getSocialConsent(): Promise<SocialConsentStatus> {
  return guarded(async () => {
    const res = await api.get<SocialConsentStatus>("/social/consent");
    return res.data;
  });
}

export async function grantSocialConsent(): Promise<SocialConsentStatus> {
  return guarded(async () => {
    const res = await api.post<SocialConsentStatus>("/social/consent", {});
    return res.data;
  });
}

export async function revokeSocialConsent(): Promise<SocialConsentStatus> {
  return guarded(async () => {
    const res = await api.delete<SocialConsentStatus>("/social/consent");
    return res.data;
  });
}

export async function getMyProfile(): Promise<SocialProfile> {
  return guarded(async () => {
    const res = await api.get<SocialProfile>("/social/me/profile");
    return res.data;
  });
}

export async function updateMyProfile(payload: {
  display_name?: string;
  bio?: string;
}): Promise<SocialProfile> {
  return guarded(async () => {
    const res = await api.patch<SocialProfile>("/social/me/profile", payload);
    return res.data;
  });
}

export async function listCommunities(): Promise<SocialCommunity[]> {
  return guarded(async () => {
    const res = await api.get<SocialCommunity[]>("/social/communities");
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function joinCommunity(id: number): Promise<SocialCommunity | void> {
  return guarded(async () => {
    const res = await api.post<SocialCommunity>(`/social/communities/${id}/join`, {});
    return res.data;
  });
}

export async function leaveCommunity(id: number): Promise<SocialCommunity | void> {
  return guarded(async () => {
    const res = await api.post<SocialCommunity>(`/social/communities/${id}/leave`, {});
    return res.data;
  });
}

export async function getFeed(
  params?: PostFilters | number,
  legacyOffset = 0
): Promise<SocialPost[]> {
  return guarded(async () => {
    const queryParams =
      typeof params === "number"
        ? { limit: params, offset: legacyOffset }
        : params;
    const res = await api.get<SocialPost[]>("/social/feed", { params: queryParams });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function getCommunityPosts(
  communityId: number,
  limit = 20,
  offset = 0
): Promise<SocialPost[]> {
  return guarded(async () => {
    const res = await api.get<SocialPost[]>(`/social/communities/${communityId}/posts`, {
      params: { limit, offset },
    });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function searchPosts(
  query: string,
  params?: PostFilters
): Promise<SocialPost[]> {
  return guarded(async () => {
    const res = await api.get<SocialPost[]>("/social/posts/search", {
      params: { q: query, ...params },
    });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function getPost(id: number): Promise<SocialPost> {
  return guarded(async () => {
    const res = await api.get<SocialPost>(`/social/posts/${id}`);
    return res.data;
  });
}

export async function createPost(payload: {
  community_id?: number;
  communityId?: number;
  title: string;
  body: string;
  tags?: string[];
}): Promise<SocialPost> {
  const community_id = payload.community_id ?? payload.communityId ?? 0;
  return guarded(async () => {
    const res = await api.post<SocialPost>("/social/posts", {
      community_id,
      title: payload.title,
      body: payload.body,
      ...(payload.tags ? { tags: payload.tags } : {}),
    });
    return res.data;
  });
}

export async function deletePost(id: number): Promise<{ deleted: boolean }> {
  return guarded(async () => {
    const res = await api.delete<{ deleted: boolean }>(`/social/posts/${id}`);
    return res.data;
  });
}

export async function getComments(
  postId: number,
  limitOrParams?: number | { limit?: number; offset?: number },
  offset = 0
): Promise<SocialComment[]> {
  return guarded(async () => {
    let params: { limit?: number; offset?: number } = { limit: 50, offset: 0 };
    if (typeof limitOrParams === "number") {
      params = { limit: limitOrParams, offset };
    } else if (limitOrParams && typeof limitOrParams === "object") {
      params = limitOrParams;
    }
    const res = await api.get<SocialComment[]>(`/social/posts/${postId}/comments`, {
      params,
    });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function addComment(
  postId: number,
  payload:
    | { body: string; parent_id?: number | null }
    | string,
  legacyParentId?: number | null
): Promise<SocialComment> {
  let bodyData: { body: string; parent_id?: number | null };
  if (typeof payload === "string") {
    bodyData = { body: payload };
    if (legacyParentId !== undefined && legacyParentId !== null) {
      bodyData.parent_id = legacyParentId;
    }
  } else {
    bodyData = payload;
  }
  return guarded(async () => {
    const res = await api.post<SocialComment>(`/social/posts/${postId}/comments`, bodyData);
    return res.data;
  });
}

export async function deleteComment(commentId: number): Promise<{ deleted: boolean }> {
  return guarded(async () => {
    const res = await api.delete<{ deleted: boolean }>(`/social/comments/${commentId}`);
    return res.data;
  });
}

export async function toggleReaction(
  postId: number,
  kind: "helpful" | "relate" | "thanks" | ReactionKind
): Promise<{ ok: boolean } | void> {
  return guarded(async () => {
    const res = await api.post<{ ok: boolean }>(`/social/posts/${postId}/reactions`, { kind });
    return res.data;
  });
}

export const addReaction = toggleReaction;

export async function toggleBookmark(postId: number): Promise<{ bookmarked: boolean }> {
  return guarded(async () => {
    const res = await api.post<{ bookmarked: boolean }>(`/social/posts/${postId}/bookmark`, {});
    return res.data;
  });
}

export async function getBookmarks(
  params?: { limit?: number; offset?: number } | PostFilters
): Promise<SocialPost[]> {
  return guarded(async () => {
    const res = await api.get<SocialPost[]>("/social/me/bookmarks", { params });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export const getMyBookmarks = getBookmarks;

export async function reportContent(payload: {
  target_type?: "post" | "comment" | string;
  targetType?: "post" | "comment" | string;
  target_id?: number;
  targetId?: number;
  reason: string;
  detail?: string;
}): Promise<{ reported: boolean } | void> {
  const target_type = payload.target_type ?? payload.targetType ?? "post";
  const target_id = payload.target_id ?? payload.targetId ?? 0;
  return guarded(async () => {
    const res = await api.post<{ reported: boolean }>("/social/reports", {
      target_type,
      target_id,
      reason: payload.reason ?? "",
      detail: payload.detail ?? payload.reason ?? "",
    });
    return res.data;
  });
}

// Admin-only: the open moderation queue.
export async function listReports(): Promise<SocialReport[]> {
  return guarded(async () => {
    const res = await api.get<SocialReport[]>("/social/moderation/reports");
    return Array.isArray(res.data) ? res.data : [];
  });
}

// Admin-only: resolve a report — "dismiss" keeps content, "remove" soft-deletes it.
export async function actOnReport(reportId: number, action: "dismiss" | "remove"): Promise<void> {
  await guarded(async () => {
    await api.post(`/social/moderation/reports/${reportId}/action`, { action });
  });
}
