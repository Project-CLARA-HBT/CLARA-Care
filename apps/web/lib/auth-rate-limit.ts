/**
 * Client-Side Auth Rate Limiting & Brute-Force Mitigation Module
 *
 * Provides progressive delays, lockout enforcement, server 429 detection,
 * challenge gating, and session-persistent failure accounting for login & OTP flows.
 */

export interface AuthRateLimitRecord {
  failedCount: number;
  lockedUntil: number; // Unix epoch ms
  lastFailureTime: number; // Unix epoch ms
  captchaRequired: boolean;
  captchaSolved: boolean;
}

export const RATE_LIMIT_CONFIG = {
  // Escalating backoff per failed attempt: attempt 0: 0s, 1: 0s, 2: 1s, 3: 3s, 4: 5s, 5+: 30s
  TIERED_COOLDOWNS_SECONDS: [0, 0, 1, 3, 5, 30] as const,
  CAPTCHA_FAILURE_THRESHOLD: 3,
  MAX_FAILURES_BEFORE_EXTENDED_LOCKOUT: 5,
  DEFAULT_SERVER_LOCKOUT_SECONDS: 60,
  EXTENDED_LOCKOUT_SECONDS: 30,
  STORAGE_PREFIX: "clara_auth_rl_",
} as const;

const memoryStore = new Map<string, AuthRateLimitRecord>();

function getStorageKey(context: "login" | "otp", normalizedId: string): string {
  // Safe sanitized key representation
  const sanitizedId = encodeURIComponent(normalizedId).replace(/[^a-zA-Z0-9_-]/g, "_");
  return `${RATE_LIMIT_CONFIG.STORAGE_PREFIX}${context}_${sanitizedId}`;
}

function loadFromStorage(context: "login" | "otp", normalizedId: string): AuthRateLimitRecord | null {
  if (typeof window === "undefined" || !window.sessionStorage) return null;
  try {
    const raw = window.sessionStorage.getItem(getStorageKey(context, normalizedId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthRateLimitRecord>;
    if (typeof parsed.failedCount === "number" && typeof parsed.lockedUntil === "number") {
      return {
        failedCount: parsed.failedCount,
        lockedUntil: parsed.lockedUntil,
        lastFailureTime: parsed.lastFailureTime ?? 0,
        captchaRequired: Boolean(parsed.captchaRequired),
        captchaSolved: Boolean(parsed.captchaSolved),
      };
    }
  } catch {
    // SessionStorage may be restricted or corrupt; fallback safely to in-memory store
  }
  return null;
}

function saveToStorage(context: "login" | "otp", normalizedId: string, record: AuthRateLimitRecord): void {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    window.sessionStorage.setItem(
      getStorageKey(context, normalizedId),
      JSON.stringify(record),
    );
  } catch {
    // SessionStorage quota exceeded or storage blocked
  }
}

function removeFromStorage(context: "login" | "otp", normalizedId: string): void {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    window.sessionStorage.removeItem(getStorageKey(context, normalizedId));
  } catch {
    // Ignore storage errors on cleanup
  }
}

export function normalizeAuthIdentifier(identifier?: string | null): string {
  if (!identifier) return "anonymous";
  const trimmed = identifier.trim().toLowerCase();
  return trimmed || "anonymous";
}

export function extractRetryAfter(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;

  const errObj = error as Record<string, unknown>;

  // 1. Direct property from enriched client error
  if (typeof errObj.retryAfter === "number" && errObj.retryAfter > 0) {
    return Math.ceil(errObj.retryAfter);
  }

  // 2. Response body retry_after_seconds
  const response = errObj.response as Record<string, unknown> | undefined;
  if (response && typeof response === "object") {
    const data = response.data as Record<string, unknown> | undefined;
    if (data && typeof data.retry_after_seconds === "number" && data.retry_after_seconds > 0) {
      return Math.ceil(data.retry_after_seconds);
    }

    // 3. Header Retry-After
    const headers = response.headers as Record<string, unknown> | undefined;
    if (headers && typeof headers === "object") {
      const headerVal = headers["retry-after"] ?? headers["Retry-After"];
      if (typeof headerVal === "string" || typeof headerVal === "number") {
        const parsed = Number(headerVal);
        if (!Number.isNaN(parsed) && parsed > 0) {
          return Math.ceil(parsed);
        }
      }
    }
  }

  // 4. Regex match inside error message or detail string
  const rawMessage =
    (typeof errObj.message === "string" ? errObj.message : "") +
    " " +
    (response && typeof response.data === "object" && typeof (response.data as Record<string, unknown>).detail === "string"
      ? ((response.data as Record<string, unknown>).detail as string)
      : "");

  const match = rawMessage.match(/(?:thử lại sau|try again in|retry after)\s*(\d+)\s*s?/i);
  if (match && match[1]) {
    const seconds = parseInt(match[1], 10);
    if (!Number.isNaN(seconds) && seconds > 0) {
      return seconds;
    }
  }

  return null;
}

export function isRateLimitOrLockoutError(error: unknown): {
  isRateLimited: boolean;
  isLockedOut: boolean;
  retryAfter: number | null;
} {
  const retryAfter = extractRetryAfter(error);
  if (!error || typeof error !== "object") {
    return { isRateLimited: false, isLockedOut: false, retryAfter: null };
  }

  const errObj = error as Record<string, unknown>;
  const response = errObj.response as Record<string, unknown> | undefined;
  const status = typeof errObj.status === "number" ? errObj.status : response?.status;
  const is429 = status === 429 || Boolean(errObj.isRateLimited);

  const rawMessage = (
    (typeof errObj.message === "string" ? errObj.message : "") +
    " " +
    (response && typeof response.data === "object" && typeof (response.data as Record<string, unknown>).detail === "string"
      ? ((response.data as Record<string, unknown>).detail as string)
      : "")
  ).toLowerCase();

  const mentionsRateLimit =
    is429 ||
    rawMessage.includes("quá giới hạn") ||
    rawMessage.includes("quá số lần thử") ||
    rawMessage.includes("too many requests") ||
    rawMessage.includes("rate limit");

  const mentionsLockout =
    rawMessage.includes("tạm khóa") ||
    rawMessage.includes("bị khóa") ||
    rawMessage.includes("locked out") ||
    rawMessage.includes("quá nhiều lần thử sai");

  const isRateLimited = mentionsRateLimit || mentionsLockout || Boolean(retryAfter && retryAfter > 0);
  const isLockedOut = mentionsLockout || (is429 && Boolean(retryAfter && retryAfter > 10));

  return { isRateLimited, isLockedOut, retryAfter };
}

export function getAuthRateLimitRecord(
  context: "login" | "otp",
  identifier?: string | null,
): AuthRateLimitRecord {
  const normId = normalizeAuthIdentifier(identifier);
  const memKey = `${context}:${normId}`;

  // Check in-memory first
  let record = memoryStore.get(memKey);
  if (!record) {
    record = loadFromStorage(context, normId) ?? {
      failedCount: 0,
      lockedUntil: 0,
      lastFailureTime: 0,
      captchaRequired: false,
      captchaSolved: false,
    };
    memoryStore.set(memKey, record);
  }

  return { ...record };
}

export function recordAuthFailure(
  context: "login" | "otp",
  identifier?: string | null,
  serverRetryAfter?: number | null,
): {
  cooldownSeconds: number;
  captchaRequired: boolean;
  isLockedOut: boolean;
  failedCount: number;
} {
  const normId = normalizeAuthIdentifier(identifier);
  const memKey = `${context}:${normId}`;
  const existing = getAuthRateLimitRecord(context, normId);

  const failedCount = existing.failedCount + 1;
  const now = Date.now();

  let cooldownSeconds = 0;
  let isLockedOut = false;

  if (typeof serverRetryAfter === "number" && serverRetryAfter > 0) {
    cooldownSeconds = serverRetryAfter;
    isLockedOut = true;
  } else if (failedCount >= RATE_LIMIT_CONFIG.MAX_FAILURES_BEFORE_EXTENDED_LOCKOUT) {
    cooldownSeconds = RATE_LIMIT_CONFIG.EXTENDED_LOCKOUT_SECONDS;
    isLockedOut = true;
  } else {
    const tierIndex = Math.min(failedCount, RATE_LIMIT_CONFIG.TIERED_COOLDOWNS_SECONDS.length - 1);
    cooldownSeconds = RATE_LIMIT_CONFIG.TIERED_COOLDOWNS_SECONDS[tierIndex] ?? 0;
    isLockedOut = false;
  }

  const captchaRequired = failedCount >= RATE_LIMIT_CONFIG.CAPTCHA_FAILURE_THRESHOLD;
  const lockedUntil = now + cooldownSeconds * 1000;

  const updated: AuthRateLimitRecord = {
    failedCount,
    lockedUntil,
    lastFailureTime: now,
    captchaRequired,
    captchaSolved: false, // Invalidate previous solve on failure
  };

  memoryStore.set(memKey, updated);
  saveToStorage(context, normId, updated);

  return {
    cooldownSeconds,
    captchaRequired,
    isLockedOut,
    failedCount,
  };
}

export function recordAuthSuccess(
  context: "login" | "otp",
  identifier?: string | null,
): void {
  const normId = normalizeAuthIdentifier(identifier);
  const memKey = `${context}:${normId}`;

  memoryStore.delete(memKey);
  removeFromStorage(context, normId);
}

export function setAuthCaptchaSolved(
  context: "login" | "otp",
  identifier?: string | null,
  solved: boolean = true,
): void {
  const normId = normalizeAuthIdentifier(identifier);
  const memKey = `${context}:${normId}`;
  const record = getAuthRateLimitRecord(context, normId);

  record.captchaSolved = solved;
  memoryStore.set(memKey, record);
  saveToStorage(context, normId, record);
}

export function getAuthCooldownRemaining(
  context: "login" | "otp",
  identifier?: string | null,
): number {
  const record = getAuthRateLimitRecord(context, identifier);
  if (!record.lockedUntil) return 0;
  const diffMs = record.lockedUntil - Date.now();
  return diffMs > 0 ? Math.ceil(diffMs / 1000) : 0;
}

export function clearAllAuthRateLimits(): void {
  memoryStore.clear();
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const key = window.sessionStorage.key(i);
      if (key && key.startsWith(RATE_LIMIT_CONFIG.STORAGE_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => window.sessionStorage.removeItem(key));
  } catch {
    // Ignore storage clearance errors
  }
}
