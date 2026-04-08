import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import {
  clearTokens,
  getAccessToken,
  getCsrfToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken
} from "@/lib/auth-store";

type RetryableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

const DEFAULT_TIMEOUT_MS = 90000;
const REFRESH_TIMEOUT_MS = 30000;

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

function trimLeadingApiV1(value: string): string {
  if (value === "/api/v1") return "/";
  return value.replace(/^\/api\/v1(?=\/|$)/, "");
}

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true
});

let refreshPromise: Promise<string | null> | null = null;

function isRetryableRefreshError(error: unknown): boolean {
  if (!(error instanceof AxiosError)) return false;
  if (error.code === "ECONNABORTED") return true;
  const status = Number(error.response?.status ?? 0);
  return status >= 500 && status < 600;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function resolveErrorMessage(error: AxiosError<{ detail?: string }>): Promise<string> {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
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
      return raw;
    } catch {
      return error.message || "Đã xảy ra lỗi không xác định.";
    }
  }

  if (typeof responseData === "string" && responseData.trim()) {
    return responseData;
  }

  return error.message || "Đã xảy ra lỗi không xác định.";
}

async function runTokenRefresh(): Promise<string | null> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {};
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const refreshAttempts: Array<() => Promise<unknown>> = [
    () =>
      axios.post(`${apiBaseUrl}/auth/refresh`, {}, { timeout: REFRESH_TIMEOUT_MS, withCredentials: true, headers }),
    () => {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        throw new Error("missing_refresh_token");
      }
      return axios.post(
        `${apiBaseUrl}/auth/refresh`,
        { refresh_token: refreshToken },
        { timeout: REFRESH_TIMEOUT_MS, withCredentials: true, headers }
      );
    }
  ];

  let refreshResponse: { data?: { access_token?: string; refresh_token?: string } } | null = null;
  let lastError: unknown = null;
  for (const attempt of refreshAttempts) {
    for (let idx = 0; idx < 2; idx += 1) {
      try {
        refreshResponse = (await attempt()) as { data?: { access_token?: string; refresh_token?: string } };
        break;
      } catch (error) {
        lastError = error;
        if (!isRetryableRefreshError(error) || idx === 1) {
          break;
        }
        await sleep(300 * (idx + 1));
      }
    }
    if (refreshResponse) break;
  }

  if (!refreshResponse) {
    throw lastError ?? new Error("token_refresh_failed");
  }

  const nextAccessToken = refreshResponse.data?.access_token as string | undefined;
  const nextRefreshToken = refreshResponse.data?.refresh_token as string | undefined;
  if (!nextAccessToken) {
    throw new Error("Không nhận được access token mới.");
  }

  setAccessToken(nextAccessToken);
  if (nextRefreshToken) {
    setRefreshToken(nextRefreshToken);
  }
  return nextAccessToken;
}

async function ensureSingleFlightRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = runTokenRefresh()
      .catch(() => {
        return null;
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

  const method = String(config.method ?? "get").toUpperCase();
  const isUnsafe = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";

  let token = getAccessToken();
  if (!token && isUnsafe) {
    // Recover from long-lived cookie-only sessions: refresh once to regain Bearer
    // token, so unsafe requests won't fail on CSRF-only path.
    token = await ensureSingleFlightRefresh();
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isAuthRefreshCall) {
      originalRequest._retry = true;

      try {
        const nextAccessToken = await ensureSingleFlightRefresh();
        if (!nextAccessToken) {
          throw new Error("Không nhận được access token mới.");
        }
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
        return api(originalRequest);
      } catch {
        clearTokens();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          const next = `${window.location.pathname}${window.location.search}`;
          window.location.href = `/login?next=${encodeURIComponent(next)}`;
        }
        return Promise.reject(new Error("Không thể làm mới phiên đăng nhập."));
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
