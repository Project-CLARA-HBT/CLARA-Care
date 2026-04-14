"use client";

import { clearTokens } from "@/lib/auth-store";

const LOGOUT_ROUTE = "/logout";

export function beginLogout(): void {
  clearTokens();
  if (typeof window === "undefined") {
    return;
  }
  window.location.replace(LOGOUT_ROUTE);
}
