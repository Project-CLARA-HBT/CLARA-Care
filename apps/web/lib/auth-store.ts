export type UserRole = "normal" | "researcher" | "doctor" | "admin";

const ACCESS_TOKEN_KEY = "clara_access_token";
const REFRESH_TOKEN_KEY = "clara_refresh_token";
const ROLE_KEY = "clara_role";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setRefreshToken(token: string): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function getRole(): UserRole {
  if (!isBrowser()) return "normal";
  const value = window.localStorage.getItem(ROLE_KEY);
  if (value === "researcher" || value === "doctor" || value === "admin" || value === "normal") {
    return value;
  }
  return "normal";
}

export function setRole(role: UserRole): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ROLE_KEY, role);
}
