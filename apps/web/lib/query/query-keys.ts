/**
 * TanStack Query key factory for CLARA API v2.
 *
 * Enforces profile scoping across all consumer and clinical server-state caches.
 * When switching profiles, invalidating ['profile', previousProfileId] or ['profile']
 * safely purges all stale profile-specific data without polluting global caches.
 */

import { getActiveProfileId } from "@/lib/profile-context";

export type QueryKeyParamValue = string | number | boolean | null | undefined | Record<string, unknown> | unknown[];

export type QueryKeyRecord = Record<string, QueryKeyParamValue>;

export const queryKeys = {
  /** Global application keys that are NOT profile-dependent. */
  global: {
    all: ["global"] as const,
    session: () => ["global", "session"] as const,
    auth: () => ["global", "auth"] as const,
    config: () => ["global", "config"] as const,
    systemHealth: () => ["global", "system-health"] as const,
  },

  /** Profiles management and selection keys. */
  profiles: {
    all: ["profiles"] as const,
    list: () => ["profiles", "list"] as const,
    detail: (profileId: string) => ["profiles", "detail", profileId] as const,
    grants: (profileId?: string) => ["profiles", "grants", profileId ?? "all"] as const,
  },

  /** Home vertical slice query keys (direct factory or profile-scoped). */
  home: {
    all: (profileId?: string | null) =>
      ["profile", profileId?.trim() || "anonymous", "home"] as const,
    overview: (profileId?: string | null) =>
      ["profile", profileId?.trim() || "anonymous", "home", "overview"] as const,
    summary: (profileId?: string | null, params?: QueryKeyRecord) =>
      ["profile", profileId?.trim() || "anonymous", "home", "summary", params ?? {}] as const,
    schedule: (profileId?: string | null, date?: string) =>
      ["profile", profileId?.trim() || "anonymous", "home", "schedule", { date }] as const,
    recentChanges: (profileId?: string | null, limit?: number) =>
      ["profile", profileId?.trim() || "anonymous", "home", "recent-changes", { limit }] as const,
    alerts: (profileId?: string | null) =>
      ["profile", profileId?.trim() || "anonymous", "home", "alerts"] as const,
  },

  /** Profile-scoped key factory. All returned keys start with ['profile', scope]. */
  profile: (profileId: string | null | undefined) => {
    const scope = profileId?.trim() || "anonymous";

    return {
      /** Root scope for the profile. Useful for bulk invalidation on profile change. */
      all: ["profile", scope] as const,

      /** Home vertical slice read models. */
      home: {
        all: ["profile", scope, "home"] as const,
        overview: () => ["profile", scope, "home", "overview"] as const,
        summary: (params?: QueryKeyRecord) =>
          ["profile", scope, "home", "summary", params ?? {}] as const,
        schedule: (date?: string) =>
          ["profile", scope, "home", "schedule", { date }] as const,
        recentChanges: (limit?: number) =>
          ["profile", scope, "home", "recent-changes", { limit }] as const,
        alerts: () => ["profile", scope, "home", "alerts"] as const,
      },

      /** Health vertical slice (summary, timeline, demographics, allergies, etc.). */
      health: {
        all: ["profile", scope, "health"] as const,
        summary: (contextVersion?: string) =>
          ["profile", scope, "health", "summary", { contextVersion }] as const,
        timeline: (params?: {
          cursor?: string;
          from?: string;
          to?: string;
          period?: string;
          types?: string[];
          search?: string;
        }) => ["profile", scope, "health", "timeline", params ?? {}] as const,
        demographics: () => ["profile", scope, "health", "demographics"] as const,
        allergies: {
          all: ["profile", scope, "health", "allergies"] as const,
          list: (params?: QueryKeyRecord) =>
            ["profile", scope, "health", "allergies", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "health", "allergies", "detail", id] as const,
        },
        conditions: {
          all: ["profile", scope, "health", "conditions"] as const,
          list: (params?: QueryKeyRecord) =>
            ["profile", scope, "health", "conditions", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "health", "conditions", "detail", id] as const,
        },
        medications: {
          all: ["profile", scope, "health", "medications"] as const,
          list: (params?: QueryKeyRecord) =>
            ["profile", scope, "health", "medications", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "health", "medications", "detail", id] as const,
          changes: (id: string) =>
            ["profile", scope, "health", "medications", id, "changes"] as const,
        },
        measurements: {
          all: ["profile", scope, "health", "measurements"] as const,
          list: (params?: { type?: string; from?: string; to?: string; limit?: number }) =>
            ["profile", scope, "health", "measurements", "list", params ?? {}] as const,
          latest: () => ["profile", scope, "health", "measurements", "latest"] as const,
        },
        documents: {
          all: ["profile", scope, "health", "documents"] as const,
          list: (params?: { cursor?: string; limit?: number; kind?: string }) =>
            ["profile", scope, "health", "documents", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "health", "documents", "detail", id] as const,
        },
      },

      /** Care vertical slice (tasks, schedule, visits, family circle). */
      care: {
        all: ["profile", scope, "care"] as const,
        summary: (contextVersion?: string) =>
          ["profile", scope, "care", "summary", { contextVersion }] as const,
        tasks: {
          all: ["profile", scope, "care", "tasks"] as const,
          list: (params?: { status?: string; limit?: number }) =>
            ["profile", scope, "care", "tasks", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "care", "tasks", "detail", id] as const,
        },
        schedule: (params?: { from?: string; to?: string }) =>
          ["profile", scope, "care", "schedule", params ?? {}] as const,
        visits: {
          all: ["profile", scope, "care", "visits"] as const,
          list: (params?: QueryKeyRecord) =>
            ["profile", scope, "care", "visits", "list", params ?? {}] as const,
          detail: (id: string) =>
            ["profile", scope, "care", "visits", "detail", id] as const,
        },
        family: {
          all: ["profile", scope, "care", "family"] as const,
          members: () => ["profile", scope, "care", "family", "members"] as const,
          grants: () => ["profile", scope, "care", "family", "grants"] as const,
        },
      },

      /** Ask / Consumer Intent AI conversations. */
      ask: {
        all: ["profile", scope, "ask"] as const,
        threads: (params?: QueryKeyRecord) =>
          ["profile", scope, "ask", "threads", params ?? {}] as const,
        thread: (id: string) => ["profile", scope, "ask", "threads", id] as const,
      },

      /** Connected Health / Wearables sync status. */
      connectors: {
        all: ["profile", scope, "connectors"] as const,
        status: () => ["profile", scope, "connectors", "status"] as const,
        sync: (id: string) => ["profile", scope, "connectors", id, "sync"] as const,
      },

      /** You / Profile / Sharing / Privacy / Integrations / Notifications keys. */
      you: {
        all: ["profile", scope, "you"] as const,
        overview: () => ["profile", scope, "you", "overview"] as const,
        profile: () => ["profile", scope, "you", "profile"] as const,
        emergencyCard: () => ["profile", scope, "you", "emergency-card"] as const,
        sharing: {
          all: ["profile", scope, "you", "sharing"] as const,
          overview: () => ["profile", scope, "you", "sharing", "overview"] as const,
          logs: () => ["profile", scope, "you", "sharing", "logs"] as const,
        },
        privacy: {
          all: ["profile", scope, "you", "privacy"] as const,
          aiTransparency: () => ["profile", scope, "you", "privacy", "ai-transparency"] as const,
        },
        integrations: () => ["profile", scope, "you", "integrations"] as const,
        notifications: () => ["profile", scope, "you", "notifications"] as const,
        settings: () => ["profile", scope, "you", "settings"] as const,
        security: () => ["profile", scope, "you", "security"] as const,
      },

      /** Arbitrary custom profile-scoped query key. */
      custom: (...parts: readonly unknown[]) =>
        ["profile", scope, ...parts] as const,
    };
  },
};

/**
 * Returns true if the query key belongs to the 'profile' root namespace.
 * If targetProfileId is supplied, also checks that the key matches that profile.
 */
export function isProfileScopedKey(
  queryKey: readonly unknown[],
  targetProfileId?: string | null,
): boolean {
  if (!Array.isArray(queryKey) || queryKey.length < 2) return false;
  if (queryKey[0] !== "profile") return false;
  if (targetProfileId !== undefined) {
    const expected = targetProfileId?.trim() || "anonymous";
    return queryKey[1] === expected;
  }
  return true;
}

/**
 * Extracts the profileId from a profile-scoped query key, or null if un-scoped.
 */
export function getProfileScopeFromKey(queryKey: readonly unknown[]): string | null {
  if (!isProfileScopedKey(queryKey)) return null;
  const scope = queryKey[1];
  return typeof scope === "string" ? scope : String(scope);
}

/**
 * Convenience helper to produce query keys bound to the active profile in browser storage.
 */
export function useActiveProfileQueryKeys(overrideProfileId?: string | null) {
  const profileId = overrideProfileId ?? getActiveProfileId();
  return queryKeys.profile(profileId);
}
