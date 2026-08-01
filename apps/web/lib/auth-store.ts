export type UserRole = "normal" | "researcher" | "doctor" | "admin";

const ROLE_KEY = "clara_role";
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
  trySetStorageItem(window.localStorage, ROLE_KEY, role);
}

export function getCsrfToken(): string | null {
  if (!isBrowser()) return null;
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const chunk of cookies) {
    const [rawKey, ...rest] = chunk.trim().split("=");
    if (rawKey !== CSRF_COOKIE_NAME) continue;
    const value = rest.join("=");
    return value ? decodeURIComponent(value) : null;
  }
  return null;
}
