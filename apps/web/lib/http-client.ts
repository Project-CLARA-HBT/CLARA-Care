import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { clearTokens, getCsrfToken } from "@/lib/auth-store";
import { getActiveProfileId } from "@/lib/profile-context";

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  _csrfRetry?: boolean;
};

const DEFAULT_TIMEOUT_MS = 90000;
const REFRESH_TIMEOUT_MS = 30000;
const AUTH_REFRESH_BYPASS_PATHS = [
  "/auth/login",
  "/auth/register",
  "/auth/login-otp/verify",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/verify-email",
  "/auth/resend-verification",
  "/auth/logout"
];

function resolveApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";
  }
  const fallback = `${window.location.origin}/api/v1`;
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!configured) return fallback;
  const allowCrossOrigin = process.env.NEXT_PUBLIC_API_ALLOW_CROSS_ORIGIN === "true";
  try {
    const resolved = new URL(configured, window.location.origin);
    if (!allowCrossOrigin && resolved.origin !== window.location.origin) {
      return fallback;
    }
    return resolved.toString();
  } catch {
    return fallback;
  }
}

const apiBaseUrl = resolveApiBaseUrl();

function hasApiV1Suffix(value: string): boolean {
  return /\/api\/v1\/?$/.test(value);
}

function isUnsafeMethod(method: unknown): boolean {
  const normalized = String(method ?? "get").toUpperCase();
  return normalized !== "GET" && normalized !== "HEAD" && normalized !== "OPTIONS";
}

/**
 * A refresh rotates the server's double-submit CSRF cookie. A stale browser
 * tab can therefore receive one 403 after a refresh/login in another tab.
 * Retry only that exact, server-declared condition once; no mutation ever
 * proceeds without the newly matched cookie/header pair.
 */
export function shouldRetryCsrfFailure(
  error: { response?: { status?: number; data?: { detail?: string } } },
  request: Pick<RetryableRequestConfig, "method" | "_csrfRetry"> | undefined,
  isAuthBypassCall: boolean,
): boolean {
  return Boolean(
    request &&
      !request._csrfRetry &&
      !isAuthBypassCall &&
      isUnsafeMethod(request.method) &&
      error.response?.status === 403 &&
      error.response.data?.detail === "CSRF validation failed",
  );
}

function trimLeadingApiV1(value: string): string {
  if (value === "/api/v1") return "/";
  return value.replace(/^\/api\/v1(?=\/|$)/, "");
}

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true
});

let refreshPromise: Promise<boolean> | null = null;
let authFailureRedirectInProgress = false;

function isRetryableRefreshError(error: unknown): boolean {
  if (!(error instanceof AxiosError)) return false;
  if (error.code === "ECONNABORTED") return true;
  const status = Number(error.response?.status ?? 0);
  return status >= 500 && status < 600;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeGatewayLikePayload(rawValue: string): string | null {
  const raw = String(rawValue ?? "").trim();
  if (!raw) return null;
  const lowered = raw.toLowerCase();
  const looksLikeHtml =
    lowered.includes("<html") || lowered.includes("<!doctype html") || lowered.includes("</html>");
  if (!looksLikeHtml) return null;
  if (lowered.includes("502 bad gateway")) {
    return "Dich vu tam thoi gian doan (502). Vui long thu lai sau it phut.";
  }
  if (lowered.includes("503 service unavailable")) {
    return "Dich vu tam thoi khong kha dung (503). Vui long thu lai sau it phut.";
  }
  if (lowered.includes("504 gateway timeout")) {
    return "Dich vu timeout tu gateway (504). Vui long thu lai sau it phut.";
  }
  return "He thong tra ve loi gateway khong hop le. Vui long thu lai.";
}

async function resolveErrorMessage(error: AxiosError<{ detail?: string }>): Promise<string> {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string" && item.trim()) return item.trim();
        if (item && typeof item === "object" && "msg" in item) {
          const msg = (item as { msg?: unknown }).msg;
          if (typeof msg === "string" && msg.trim()) return msg.trim();
        }
        return null;
      })
      .filter((value): value is string => Boolean(value));
    if (messages.length > 0) {
      return messages.join("\n");
    }
  }

  const responseData: unknown = error.response?.data;
  if (typeof Blob !== "undefined" && responseData instanceof Blob) {
    try {
      const raw = (await responseData.text()).trim();
      if (!raw) {
        return error.message || "Đã xảy ra lỗi không xác định.";
      }
      try {
        const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) {
          return parsed.detail;
        }
        if (typeof parsed.message === "string" && parsed.message.trim()) {
          return parsed.message;
        }
      } catch {
        // fall through and return raw payload when JSON parse fails.
      }
      const normalizedGateway = normalizeGatewayLikePayload(raw);
      if (normalizedGateway) {
        return normalizedGateway;
      }
      return raw;
    } catch {
      return error.message || "Đã xảy ra lỗi không xác định.";
    }
  }

  if (typeof responseData === "string" && responseData.trim()) {
    const normalizedGateway = normalizeGatewayLikePayload(responseData);
    if (normalizedGateway) {
      return normalizedGateway;
    }
    return responseData;
  }

  return error.message || "Đã xảy ra lỗi không xác định.";
}

async function runTokenRefresh(): Promise<boolean> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {};
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  let refreshResponse: unknown = null;
  let lastError: unknown = null;
  for (let idx = 0; idx < 2; idx += 1) {
    try {
      // Browser refresh is deliberately cookie-only. The API rotates HttpOnly
      // cookies; response tokens are for non-browser clients and must never be
      // persisted or attached by the web app.
      refreshResponse = await axios.post(
        `${apiBaseUrl}/auth/refresh`,
        {},
        { timeout: REFRESH_TIMEOUT_MS, withCredentials: true, headers }
      );
      break;
    } catch (error) {
      lastError = error;
      if (!isRetryableRefreshError(error) || idx === 1) {
        break;
      }
    }
    await sleep(300 * (idx + 1));
  }

  if (!refreshResponse) {
    throw lastError ?? new Error("token_refresh_failed");
  }

  authFailureRedirectInProgress = false;
  return true;
}

async function bestEffortServerLogout(): Promise<void> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {};
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }
  try {
    await axios.post(`${apiBaseUrl}/auth/logout`, {}, {
      timeout: REFRESH_TIMEOUT_MS,
      withCredentials: true,
      headers,
      validateStatus: () => true
    });
  } catch {
    // Ignore network/logout failures; local token clear + redirect still proceeds.
  }
}

// Public routes never bounce to /login on an auth failure: the landing page and
// other marketing/legal/help surfaces are meant to be viewable without a
// session, so a background 401 (e.g. an optional summary fetch) must NOT eject
// the visitor. Mirrors the middleware public-path set.
const AUTH_FAILURE_REDIRECT_SKIP_PREFIXES = [
  "/login",
  "/register",
  "/legal",
  "/huong-dan",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/share/",
  "/chat/share/",
  "/phr/shared/",
];

function redirectToLoginAfterAuthFailure(): void {
  if (typeof window === "undefined") return;
  const path = window.location.pathname;
  // The landing page ("/") is always allowed; other public surfaces are matched
  // by prefix. Never redirect away from any of them.
  if (path === "/") return;
  if (AUTH_FAILURE_REDIRECT_SKIP_PREFIXES.some((p) => path.startsWith(p))) return;
  if (authFailureRedirectInProgress) return;
  authFailureRedirectInProgress = true;
  const next = `${window.location.pathname}${window.location.search}`;
  window.location.replace(`/login?next=${encodeURIComponent(next)}`);
}

async function ensureSingleFlightRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = runTokenRefresh()
      .catch(() => {
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.request.use(async (config) => {
  const requestUrl = String(config.url ?? "");
  const currentBase = String(config.baseURL ?? api.defaults.baseURL ?? "");
  if (requestUrl.startsWith("/api/v1") && hasApiV1Suffix(currentBase)) {
    config.url = trimLeadingApiV1(requestUrl);
  }

  const isUnsafe = isUnsafeMethod(config.method);

  // This is a presentation/cache partition hint, never an authorization
  // credential. The API resolves it only against owned profiles or live grants.
  const activeProfileId = getActiveProfileId();
  if (activeProfileId) {
    config.headers["X-CLARA-Profile-Context"] = activeProfileId;
  }

  if (isUnsafe) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      config.headers["X-CSRF-Token"] = csrfToken;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;
    const requestUrl = String(originalRequest?.url ?? "");
    const isAuthRefreshCall = requestUrl.includes("/auth/refresh");
    const isAuthBypassCall = AUTH_REFRESH_BYPASS_PATHS.some((path) => requestUrl.includes(path));

    if (shouldRetryCsrfFailure(error, originalRequest, isAuthBypassCall)) {
      originalRequest!._csrfRetry = true;
      const refreshed = await ensureSingleFlightRefresh();
      if (refreshed) {
        // The request interceptor reads document.cookie again here, so this
        // retry uses the CSRF value just rotated by `/auth/refresh`.
        return api(originalRequest!);
      }
    }

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthRefreshCall &&
      !isAuthBypassCall
    ) {
      originalRequest._retry = true;

      try {
        const refreshed = await ensureSingleFlightRefresh();
        if (!refreshed) {
          throw new Error("Không thể làm mới phiên đăng nhập.");
        }
        return api(originalRequest);
      } catch {
        await bestEffortServerLogout();
        clearTokens();
        redirectToLoginAfterAuthFailure();
        return Promise.reject(new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."));
      }
    }

    if (error.code === "ECONNABORTED") {
      return Promise.reject(new Error("Yêu cầu xử lý quá thời gian chờ. Vui lòng thử lại."));
    }

    const message = await resolveErrorMessage(error);
    return Promise.reject(new Error(message));
  }
);

export default api;
