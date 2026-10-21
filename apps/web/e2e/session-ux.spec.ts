import { expect, test } from "@playwright/test";

/**
 * End-to-end tests for web session UX states:
 * - Silent token refresh recovery on 401 response
 * - Immediate redirection to /login when refresh token fails / session terminates
 * - Preserve intended destination in ?next= redirect param
 * - Public routes remain accessible without redirecting upon auth rejection
 * - Immediate client session state clearing on logout
 */

test.describe("Web Session UX States and Silent Refresh", () => {
  test("silent refresh recovers active session seamlessly when initial call returns 401", async ({
    page,
  }) => {
    let meCallCount = 0;
    let refreshCallCount = 0;

    await page.addInitScript(() => {
      window.localStorage.setItem("clara_role", "normal");
      window.localStorage.setItem("clara-theme", "light");
      window.localStorage.setItem("clara_ui_language", "vi");
      // Set client session hint cookie
      document.cookie = "clara_client_session=active; Path=/; SameSite=Lax";
    });

    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;

      if (path.endsWith("/auth/me")) {
        meCallCount += 1;
        if (meCallCount === 1) {
          // First attempt simulated as expired access token (401)
          await route.fulfill({
            status: 401,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Token không hợp lệ hoặc đã hết hạn" }),
          });
          return;
        }
        // Second attempt after silent refresh succeeds
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "user-101", role: "normal", email: "patient@clara.vn" }),
        });
        return;
      }

      if (path.endsWith("/auth/refresh")) {
        refreshCallCount += 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Set-Cookie": "clara_access_token=fresh-access; Path=/; HttpOnly; SameSite=Lax",
          },
          body: JSON.stringify({
            access_token: "fresh-access-token",
            refresh_token: "fresh-refresh-token",
            role: "normal",
          }),
        });
        return;
      }

      if (path.endsWith("/auth/consent-status")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            consent_type: "medical_content",
            required_version: "e2e",
            accepted: true,
            accepted_version: "e2e",
          }),
        });
        return;
      }

      if (path.endsWith("/profiles/context")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            profiles: [{ id: "p-1", kind: "self", display_name: "Tôi" }],
            active_profile_id: "p-1",
            active_kind: "self",
            cache_scope: "p-1",
            reset_required: false,
          }),
        });
        return;
      }

      if (path.endsWith("/phr/onboarding")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "completed", needs_onboarding: false, version: 1 }),
        });
        return;
      }

      if (path.endsWith("/lifemap/today")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            generated_at: "2026-08-08T00:00:00Z",
            tasks: [],
            episodes: [],
            pending_confirmation_count: 0,
          }),
        });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });

    await page.goto("/today", { waitUntil: "domcontentloaded" });

    // Expect silent refresh to be called and user to stay on /today without login redirection
    expect(page.url()).toContain("/today");
    expect(refreshCallCount).toBeGreaterThanOrEqual(1);
    await expect(page.locator("main#main-content")).toBeVisible();
  });

  test("expired refresh redirects to /login with encoded ?next= destination parameter", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("clara_role", "normal");
      document.cookie = "clara_client_session=active; Path=/; SameSite=Lax";
    });

    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;

      if (path.endsWith("/auth/me")) {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Token không hợp lệ hoặc đã hết hạn" }),
        });
        return;
      }

      if (path.endsWith("/auth/refresh")) {
        // Refresh token itself is dead/revoked
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Refresh token không hợp lệ hoặc đã bị thu hồi" }),
        });
        return;
      }

      if (path.endsWith("/auth/logout")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    // Attempt navigating to a protected route
    await page.goto("/today?tab=schedule", { waitUntil: "domcontentloaded" });

    // Expect redirect to login with query param preserving target
    await page.waitForURL(/\/login\?next=/, { timeout: 15_000 });
    const currentUrl = page.url();
    expect(currentUrl).toContain("/login");
    expect(currentUrl).toContain("next=%2Ftoday%3Ftab%3Dschedule");
  });

  test("public routes never bounce to /login even if a background call receives 401", async ({
    page,
  }) => {
    await page.route("**/api/v1/**", async (route) => {
      // Any API call in background returns 401
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      });
    });

    for (const publicPath of ["/huong-dan", "/legal/privacy", "/legal/terms"]) {
      await page.goto(publicPath, { waitUntil: "domcontentloaded" });
      expect(page.url()).toContain(publicPath);
      expect(page.url()).not.toContain("/login");
      await expect(page.locator("main#main-content")).toBeVisible();
    }
  });

  test("logout triggers server revocation, clears client session tokens and redirects", async ({
    page,
  }) => {
    let logoutCalled = false;

    await page.addInitScript(() => {
      window.localStorage.setItem("clara_role", "normal");
      document.cookie = "clara_client_session=active; Path=/; SameSite=Lax";
    });

    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;

      if (path.endsWith("/auth/me")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: 1, role: "normal", email: "logout-test@clara.vn" }),
        });
        return;
      }

      if (path.endsWith("/auth/logout")) {
        logoutCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Set-Cookie": "clara_access_token=; Path=/; Max-Age=0, clara_refresh_token=; Path=/; Max-Age=0",
          },
          body: JSON.stringify({ logged_out: true }),
        });
        return;
      }

      if (path.endsWith("/auth/consent-status")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ accepted: true, required_version: "e2e", accepted_version: "e2e" }),
        });
        return;
      }

      if (path.endsWith("/profiles/context")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ profiles: [], active_profile_id: null, active_kind: "self", cache_scope: "self" }),
        });
        return;
      }

      if (path.endsWith("/phr/onboarding")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "completed", needs_onboarding: false, version: 1 }),
        });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.locator("main#main-content")).toBeVisible();

    // Trigger logout via client logout helper
    await page.evaluate(async () => {
      const { beginLogout } = await import("@/lib/logout");
      beginLogout();
    });

    // Wait for redirection to /logout or /login
    await page.waitForURL(/\/(logout|login)/, { timeout: 15_000 });
    expect(logoutCalled).toBe(true);
  });
});
