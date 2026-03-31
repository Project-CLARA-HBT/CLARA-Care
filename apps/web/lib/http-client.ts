import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { clearTokens, getAccessToken, getRefreshToken, setAccessToken, setRefreshToken } from "@/lib/auth-store";

type RetryableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

const DEFAULT_TIMEOUT_MS = 90000;
const REFRESH_TIMEOUT_MS = 30000;

const fallbackBaseUrl =
  typeof window !== "undefined" ? `${window.location.origin}/api/v1` : "http://localhost:8100/api/v1";
const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? fallbackBaseUrl;

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
      const refreshToken = getRefreshToken();
      const payload = refreshToken ? { refresh_token: refreshToken } : {};

      try {
        const refreshResponse = await axios.post(
          `${apiBaseUrl}/auth/refresh`,
          payload,
          { timeout: REFRESH_TIMEOUT_MS, withCredentials: true }
        );

        const nextAccessToken = refreshResponse.data?.access_token as string | undefined;
        const nextRefreshToken = refreshResponse.data?.refresh_token as string | undefined;
        if (!nextAccessToken) {
          throw new Error("Không nhận được access token mới.");
        }

        setAccessToken(nextAccessToken);
        if (nextRefreshToken) {
          setRefreshToken(nextRefreshToken);
        }
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

    const message = error.response?.data?.detail ?? error.message ?? "Đã xảy ra lỗi không xác định.";
    return Promise.reject(new Error(message));
  }
);

export default api;
