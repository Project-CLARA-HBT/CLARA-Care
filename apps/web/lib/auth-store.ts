export type UserRole = "normal" | "researcher" | "doctor" | "admin";

const ROLE_KEY = "clara_role";
const ACCESS_TOKEN_SESSION_KEY = "clara_access_token_session";
const REFRESH_TOKEN_SESSION_KEY = "clara_refresh_token_session";
const ACCESS_TOKEN_LOCAL_KEY = "clara_access_token_local";
const REFRESH_TOKEN_LOCAL_KEY = "clara_refresh_token_local";
const CLIENT_SESSION_COOKIE = "clara_client_session";
const CSRF_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_CSRF_COOKIE?.trim() || "clara_csrf_token";

let accessTokenMemory: string | null = null;
let refreshTokenMemory: string | null = null;

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

export function getAccessToken(): string | null {
  if (!accessTokenMemory && isBrowser()) {
    const sessionCached = tryGetStorageItem(window.sessionStorage, ACCESS_TOKEN_SESSION_KEY);
    const localCached = tryGetStorageItem(window.localStorage, ACCESS_TOKEN_LOCAL_KEY);
    accessTokenMemory = sessionCached?.trim() || localCached?.trim() || null;
  }
  return accessTokenMemory;
}

export function setAccessToken(token: string): void {
  const next = token.trim() || null;
  accessTokenMemory = next;
  if (!isBrowser()) return;
  if (next) {
    trySetStorageItem(window.sessionStorage, ACCESS_TOKEN_SESSION_KEY, next);
    trySetStorageItem(window.localStorage, ACCESS_TOKEN_LOCAL_KEY, next);
    setClientSessionCookie(true);
  } else {
    tryRemoveStorageItem(window.sessionStorage, ACCESS_TOKEN_SESSION_KEY);
    tryRemoveStorageItem(window.localStorage, ACCESS_TOKEN_LOCAL_KEY);
  }
}

export function getRefreshToken(): string | null {
  if (!refreshTokenMemory && isBrowser()) {
    const sessionCached = tryGetStorageItem(window.sessionStorage, REFRESH_TOKEN_SESSION_KEY);
    const localCached = tryGetStorageItem(window.localStorage, REFRESH_TOKEN_LOCAL_KEY);
    refreshTokenMemory = sessionCached?.trim() || localCached?.trim() || null;
  }
  return refreshTokenMemory;
}

export function setRefreshToken(token: string): void {
  // SessionStorage fallback only to recover from environments where HttpOnly
  // cookie is temporarily unavailable (mobile/webview cross-origin quirks).
  const next = token.trim() || null;
  refreshTokenMemory = next;
  if (!isBrowser()) return;
  if (next) {
    trySetStorageItem(window.sessionStorage, REFRESH_TOKEN_SESSION_KEY, next);
    trySetStorageItem(window.localStorage, REFRESH_TOKEN_LOCAL_KEY, next);
    setClientSessionCookie(true);
  } else {
    tryRemoveStorageItem(window.sessionStorage, REFRESH_TOKEN_SESSION_KEY);
    tryRemoveStorageItem(window.localStorage, REFRESH_TOKEN_LOCAL_KEY);
  }
}

export function clearTokens(): void {
  accessTokenMemory = null;
  refreshTokenMemory = null;
  if (!isBrowser()) return;
  tryRemoveStorageItem(window.sessionStorage, ACCESS_TOKEN_SESSION_KEY);
  tryRemoveStorageItem(window.sessionStorage, REFRESH_TOKEN_SESSION_KEY);
  tryRemoveStorageItem(window.localStorage, ACCESS_TOKEN_LOCAL_KEY);
  tryRemoveStorageItem(window.localStorage, REFRESH_TOKEN_LOCAL_KEY);
  tryRemoveStorageItem(window.localStorage, ROLE_KEY);
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
