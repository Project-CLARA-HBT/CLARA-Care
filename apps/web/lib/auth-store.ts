export type UserRole = "normal" | "researcher" | "doctor" | "admin";
export type AdminPreviewMode = "clinical" | "research" | "personal";

export const ROLE_KEY = "clara_role";
export const ADMIN_PREVIEW_STORAGE_KEY = "clara_admin_preview_mode";
export const ADMIN_PREVIEW_COOKIE_NAME = "clara_admin_preview_mode";
export const ADMIN_PREVIEW_CHANGE_EVENT = "clara:admin-preview-change";
export const ROLE_CHANGE_EVENT = "clara:role-change";
export const SESSION_CHANGE_EVENT = "clara:session-change";
const ACCESS_TOKEN_SESSION_KEY = "clara_access_token_session";
const REFRESH_TOKEN_SESSION_KEY = "clara_refresh_token_session";
const CLIENT_SESSION_COOKIE =
  process.env.NEXT_PUBLIC_AUTH_CLIENT_SESSION_COOKIE?.trim() || "clara_client_session";
const CSRF_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_CSRF_COOKIE?.trim() || "clara_csrf_token";
const ACTIVE_PROFILE_STORAGE_KEY = "clara_active_profile_id";
const PROFILE_CACHE_PREFIX = "clara_profile_cache:";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function normalizeAdminPreviewMode(value: unknown): AdminPreviewMode | null {
  if (value === "clinical" || value === "research" || value === "personal") {
    return value;
  }
  return null;
}

function tryGetStorageItem(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function trySetStorageItem(storage: Storage, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // Ignore storage write failures (private mode / restricted webview).
  }
}

function tryRemoveStorageItem(storage: Storage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    // Ignore storage write failures (private mode / restricted webview).
  }
}

function setClientSessionCookie(enabled: boolean): void {
  if (!isBrowser()) return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  if (enabled) {
    document.cookie = `${CLIENT_SESSION_COOKIE}=1; Path=/; Max-Age=${60 * 60 * 24 * 30}; SameSite=Lax${secure}`;
    return;
  }
  document.cookie = `${CLIENT_SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

export function setAdminPreviewCookie(mode: AdminPreviewMode | null): void {
  if (!isBrowser()) return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  const validMode = normalizeAdminPreviewMode(mode);
  if (validMode) {
    document.cookie = `${ADMIN_PREVIEW_COOKIE_NAME}=${encodeURIComponent(validMode)}; Path=/; Max-Age=${60 * 60 * 24 * 7}; SameSite=Lax${secure}`;
    return;
  }
  document.cookie = `${ADMIN_PREVIEW_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

function getAdminPreviewCookie(): AdminPreviewMode | null {
  if (!isBrowser()) return null;
  try {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const chunk of cookies) {
      const [rawKey, ...rest] = chunk.trim().split("=");
      if (rawKey !== ADMIN_PREVIEW_COOKIE_NAME) continue;
      const value = rest.join("=");
      if (!value) continue;
      return normalizeAdminPreviewMode(decodeURIComponent(value));
    }
  } catch {
    return null;
  }
  return null;
}

export function getStoredAdminPreviewMode(): AdminPreviewMode | null {
  if (!isBrowser()) return null;
  const fromStorage = tryGetStorageItem(window.localStorage, ADMIN_PREVIEW_STORAGE_KEY);
  const normalized = normalizeAdminPreviewMode(fromStorage);
  if (normalized) return normalized;
  return getAdminPreviewCookie();
}

export function setStoredAdminPreviewMode(mode: AdminPreviewMode | null): void {
  if (!isBrowser()) return;
  const normalized = normalizeAdminPreviewMode(mode);
  if (normalized) {
    trySetStorageItem(window.localStorage, ADMIN_PREVIEW_STORAGE_KEY, normalized);
  } else {
    tryRemoveStorageItem(window.localStorage, ADMIN_PREVIEW_STORAGE_KEY);
  }
  setAdminPreviewCookie(normalized);
}

function purgeLegacySessionTokens(): void {
  if (!isBrowser()) return;
  // Earlier builds wrote bearer credentials to sessionStorage. Remove them on
  // every auth-store entry point so an upgraded browser cannot retain a
  // refresh token that an injected script could read.
  tryRemoveStorageItem(window.sessionStorage, ACCESS_TOKEN_SESSION_KEY);
  tryRemoveStorageItem(window.sessionStorage, REFRESH_TOKEN_SESSION_KEY);
}

/** Mark the browser UI as signed in; credentials themselves stay HttpOnly. */
export function markAuthenticatedBrowserSession(): void {
  purgeLegacySessionTokens();
  setClientSessionCookie(true);
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  purgeLegacySessionTokens();
  tryRemoveStorageItem(window.localStorage, ROLE_KEY);
  tryRemoveStorageItem(window.localStorage, ADMIN_PREVIEW_STORAGE_KEY);
  setAdminPreviewCookie(null);
  tryRemoveStorageItem(window.localStorage, ACTIVE_PROFILE_STORAGE_KEY);
  for (const storage of [window.sessionStorage, window.localStorage]) {
    try {
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
      for (const key of keys) {
        if (key?.startsWith(PROFILE_CACHE_PREFIX)) tryRemoveStorageItem(storage, key);
      }
    } catch {
      // Ignore storage failures; logout must still clear the auth credentials.
    }
  }
  setClientSessionCookie(false);
}

export function getRole(): UserRole {
  if (!isBrowser()) return "normal";
  const value = tryGetStorageItem(window.localStorage, ROLE_KEY);
  if (value === "researcher" || value === "doctor" || value === "admin" || value === "normal") {
    return value;
  }
  return "normal";
}

export function setRole(role: UserRole): void {
  if (!isBrowser()) return;
  if (role === "researcher" || role === "doctor" || role === "admin" || role === "normal") {
    trySetStorageItem(window.localStorage, ROLE_KEY, role);
  }
}

export function getCsrfToken(): string | null {
  if (!isBrowser()) return null;
  const cookies = document.cookie ? document.cookie.split(";") : [];
  // A browser can retain an older host-only cookie after a deployment changes
  // the configured cookie domain.  Requests send duplicate-name cookies in
  // order and Starlette's parser retains the final value.  Mirror that
  // last-value behaviour here so the header and the cookie observed by the
  // CSRF middleware stay paired; returning the first value caused a spurious
  // 403 on profile saves for affected existing sessions.
  let token: string | null = null;
  for (const chunk of cookies) {
    const [rawKey, ...rest] = chunk.trim().split("=");
    if (rawKey !== CSRF_COOKIE_NAME) continue;
    const value = rest.join("=");
    if (!value) continue;
    try {
      token = decodeURIComponent(value);
    } catch {
      // A malformed legacy cookie must not prevent a later valid token from
      // being selected; the normal CSRF recovery path will refresh if needed.
    }
  }
  return token;
}
