import { beforeEach, describe, expect, it } from "vitest";

import { clearTokens, markAuthenticatedBrowserSession } from "@/lib/auth-store";

const LEGACY_ACCESS_TOKEN_KEY = "clara_access_token_session";
const LEGACY_REFRESH_TOKEN_KEY = "clara_refresh_token_session";

describe("browser auth storage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    document.cookie = "clara_client_session=; Path=/; Max-Age=0; SameSite=Lax";
  });

  it("purges legacy script-readable tokens after a successful cookie login", () => {
    window.sessionStorage.setItem(LEGACY_ACCESS_TOKEN_KEY, "legacy-access");
    window.sessionStorage.setItem(LEGACY_REFRESH_TOKEN_KEY, "legacy-refresh");

    markAuthenticatedBrowserSession();

    expect(window.sessionStorage.getItem(LEGACY_ACCESS_TOKEN_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(LEGACY_REFRESH_TOKEN_KEY)).toBeNull();
    expect(document.cookie).toContain("clara_client_session=1");
  });

  it("clears legacy tokens on logout as well", () => {
    window.sessionStorage.setItem(LEGACY_ACCESS_TOKEN_KEY, "legacy-access");
    window.sessionStorage.setItem(LEGACY_REFRESH_TOKEN_KEY, "legacy-refresh");

    clearTokens();

    expect(window.sessionStorage.getItem(LEGACY_ACCESS_TOKEN_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(LEGACY_REFRESH_TOKEN_KEY)).toBeNull();
  });
});
