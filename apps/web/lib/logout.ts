"use client";

import { clearTokens } from "@/lib/auth-store";
import api from "@/lib/http-client";

const LOGOUT_ROUTE = "/logout";
const LOGOUT_API_TIMEOUT_MS = 5000;

let logoutStarted = false;

export function beginLogout(): void {
  if (logoutStarted) {
    return;
  }
  logoutStarted = true;

  void (async () => {
    try {
      await api.post("/auth/logout", {}, { timeout: LOGOUT_API_TIMEOUT_MS });
    } catch {
      // Continue with local/session cleanup even if server-side revocation fails.
    } finally {
      clearTokens();
      if (typeof window !== "undefined") {
        window.location.replace(LOGOUT_ROUTE);
      }
    }
  })();
}
