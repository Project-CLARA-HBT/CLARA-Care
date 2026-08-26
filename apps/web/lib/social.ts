import api from "@/lib/http-client";

// CLARA Health Social platform web client (spec: .kiro/specs/clara-health-social).
//
// All routes 404 when the server-side `social_platform_enabled` flag is off, so
// callers treat a 404 as "feature unavailable" and hide the surface
// (fail-closed), exactly like the mobile client.

export type SocialConsentStatus = {
  consent_type: string;
  granted: boolean;
};

export type SocialCommunity = {
  id: number;
  slug: string;
  name: string;
  description: string;
  member_count: number;
  joined: boolean;
};

export type SocialPost = {
  id: number;
  community_id: number;
  author_handle: string;
  title: string;
  body: string;
  created_at: string;
  comment_count: number;
  reaction_count: number;
};

export type SocialComment = {
  id: number;
  post_id: number;
  author_handle: string;
  body: string;
  created_at: string;
};

export type SocialProfile = {
  handle: string;
  display_name: string;
  bio: string;
  role_badge: string;
};

export type ReactionKind = "helpful" | "relate" | "thanks";

export class SocialUnavailableError extends Error {
  constructor() {
    super("social_unavailable");
    this.name = "SocialUnavailableError";
  }
}

function isNotFound(error: unknown): boolean {
  const status = (error as { response?: { status?: number } })?.response?.status;
  return status === 404;
}

/** True when a write was rejected by the pre-publish moderation gate (422). */
export function isSocialModerationBlock(error: unknown): boolean {
  const status = (error as { response?: { status?: number } })?.response?.status;
  return status === 422;
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

export async function listCommunities(): Promise<SocialCommunity[]> {
  return guarded(async () => {
    const res = await api.get<SocialCommunity[]>("/social/communities");
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function joinCommunity(communityId: number): Promise<void> {
  await guarded(async () => {
    await api.post(`/social/communities/${communityId}/join`, {});
  });
}

export async function leaveCommunity(communityId: number): Promise<void> {
  await guarded(async () => {
    await api.post(`/social/communities/${communityId}/leave`, {});
  });
}

export async function getFeed(limit = 20, offset = 0): Promise<SocialPost[]> {
  return guarded(async () => {
    const res = await api.get<SocialPost[]>("/social/feed", { params: { limit, offset } });
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function createPost(input: {
  communityId: number;
  title: string;
  body: string;
}): Promise<SocialPost> {
  return guarded(async () => {
    const res = await api.post<SocialPost>("/social/posts", {
      community_id: input.communityId,
      title: input.title,
      body: input.body
    });
    return res.data;
  });
}

export async function getComments(postId: number): Promise<SocialComment[]> {
  return guarded(async () => {
    const res = await api.get<SocialComment[]>(`/social/posts/${postId}/comments`);
    return Array.isArray(res.data) ? res.data : [];
  });
}

export async function addComment(postId: number, body: string): Promise<SocialComment> {
  return guarded(async () => {
    const res = await api.post<SocialComment>(`/social/posts/${postId}/comments`, { body });
    return res.data;
  });
}

export async function addReaction(postId: number, kind: ReactionKind): Promise<void> {
  await guarded(async () => {
    await api.post(`/social/posts/${postId}/reactions`, { kind });
  });
}

export async function reportContent(input: {
  targetType: "post" | "comment";
  targetId: number;
  reason?: string;
}): Promise<void> {
  await guarded(async () => {
    await api.post("/social/reports", {
      target_type: input.targetType,
      target_id: input.targetId,
      reason: input.reason ?? ""
    });
  });
}

export type SocialReport = {
  id: number;
  target_type: "post" | "comment";
  target_id: number;
  reason: string;
  status: string;
  created_at: string;
};

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
