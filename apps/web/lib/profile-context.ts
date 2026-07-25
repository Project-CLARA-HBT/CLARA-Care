/**
 * Client-side profile-context boundary.
 *
 * The selected id is only a display/request hint; the API independently checks
 * ownership or a live Family grant for every protected operation.  We never
 * place health-record data in this store.
 */

export type ProfileContextProfile = {
  id: string;
  display_name: string;
  kind: "self" | "shared" | string;
  active: boolean;
  created_at: string;
};

export type ProfileContext = {
  profiles: ProfileContextProfile[];
  active_profile_id: string | null;
  active_kind: "self" | "shared" | string | null;
  cache_scope: string | null;
  reset_required: boolean;
};

export type ProfileActivation = {
  profile: ProfileContextProfile;
  active_profile_id: string;
  cache_scope: string;
  reset_required: boolean;
};

export const ACTIVE_PROFILE_STORAGE_KEY = "clara_active_profile_id";
export const PROFILE_CACHE_PREFIX = "clara_profile_cache:";
export const PROFILE_CONTEXT_CHANGE_EVENT = "clara:profile-context-changed";

function browserStorage(): Storage[] {
  if (typeof window === "undefined") return [];
  return [window.sessionStorage, window.localStorage];
}

export function getActiveProfileId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY)?.trim();
    return value || null;
  } catch {
    return null;
  }
}

/** Remove only explicitly profile-scoped caches; auth/session state survives. */
export function clearProfileScopedClientState(): void {
  for (const storage of browserStorage()) {
    try {
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
      for (const key of keys) {
        if (key?.startsWith(PROFILE_CACHE_PREFIX)) storage.removeItem(key);
      }
    } catch {
      // Storage can be unavailable in private browsing or embedded webviews.
    }
  }
}

export function setActiveProfileId(profileId: string | null): void {
  if (typeof window === "undefined") return;
  const next = profileId?.trim() || null;
  const previous = getActiveProfileId();
  if (previous === next) return;
  clearProfileScopedClientState();
  try {
    if (next) window.localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, next);
    else window.localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY);
  } catch {
    // The current page still receives the reset event if persistence is blocked.
  }
  window.dispatchEvent(
    new CustomEvent(PROFILE_CONTEXT_CHANGE_EVENT, { detail: { previous, next } }),
  );
}

export function clearActiveProfileContext(): void {
  clearProfileScopedClientState();
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY);
  } catch {
    // noop
  }
}
