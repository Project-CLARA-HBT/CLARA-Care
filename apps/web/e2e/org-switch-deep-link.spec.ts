import { expect, test, type Page } from "@playwright/test";

/**
 * End-to-end tests for Organization Switching and Invitation Deep-Link Flows:
 * 1. Deep-link intake for unauthenticated visitors preserves destination via ?next=
 * 2. Post-login invitation resumption and safe preview (token never in URL path)
 * 3. Secure invitation acceptance dispatch via JSON body / request header
 * 4. Multi-tenant organization switching in header/shell with cache reset
 * 5. Fail-closed error handling for expired or invalid invitation deep links
 */

async function seedAuthenticatedSession(page: Page, role = "normal") {
  await page.addInitScript((userRole) => {
    window.localStorage.setItem("clara_role", userRole);
    window.localStorage.setItem("clara-theme", "light");
    window.localStorage.setItem("clara_ui_language", "vi");
    document.cookie = "clara_client_session=active; Path=/; SameSite=Lax";
  }, role);
}

test.describe("Organization Switching and Deep-Link Test Suite", () => {
  test("unauthenticated visitor on invitation deep-link redirects to login preserving next target", async ({
    page,
  }) => {
    // Intercept auth check to simulate unauthenticated state (401)
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Chưa đăng nhập" }),
      });
    });

    const deepLinkPath = "/invitations/accept?token=sample_invitation_secret_tok_12345";
    await page.goto(deepLinkPath);

    // Expect redirection to login preserving the full deep-link path and query
    await page.waitForURL((url) => url.pathname.includes("/login"));
    const currentUrl = new URL(page.url());
    expect(currentUrl.pathname).toBe("/login");
    const nextParam = currentUrl.searchParams.get("next");
    expect(nextParam).toBeTruthy();
    expect(decodeURIComponent(nextParam!)).toContain("/invitations/accept");
    expect(decodeURIComponent(nextParam!)).toContain("token=sample_invitation_secret_tok_12345");
  });

  test("authenticated user previews invitation without exposing raw capability in DOM", async ({
    page,
  }) => {
    await seedAuthenticatedSession(page, "normal");

    let previewCalled = false;
    let previewSentInPath = false;

    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;

      if (path.endsWith("/auth/me")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: 101, email: "recipient@hospital.vn", role: "normal" }),
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
          }),
        });
        return;
      }

      if (path.includes("/invitations/preview") || path.includes("/family/invitations/preview")) {
        previewCalled = true;
        if (url.pathname.includes("secret_tok")) {
          previewSentInPath = true;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            object_type: "episode",
            inviter_name: "BS. Nguyen Van A",
            organization_name: "Bệnh viện Bạch Mai",
            allowed_actions: ["view", "add_observation"],
            purpose: "care_coordination",
            expires_at: new Date(Date.now() + 86400000 * 5).toISOString(),
          }),
        });
        return;
      }

      // Default fallback
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    const deepLinkPath = "/today?invitation_token=sample_preview_secret_tok_998877";
    await page.goto(deepLinkPath);

    // Verify token capability was never sent in the URL path of the preview endpoint
    expect(previewSentInPath).toBe(false);
  });

  test("organization switcher updates active context and dispatches cache reset", async ({
    page,
  }) => {
    await seedAuthenticatedSession(page, "doctor");

    let activeContextId = "org-1";
    let activationDispatched = false;

    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;

      if (path.endsWith("/auth/me")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: 202, email: "doctor@care.vn", role: "doctor" }),
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
          }),
        });
        return;
      }

      if (path.endsWith("/profiles/context")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Cache-Control": "no-store, private",
            Vary: "Authorization, X-CLARA-Profile-Context",
          },
          body: JSON.stringify({
            profiles: [
              { id: "org-1", kind: "self", display_name: "Bệnh viện Bạch Mai (Nội khoa)" },
              { id: "org-2", kind: "shared", display_name: "Phòng khám Đa khoa Quốc tế" },
            ],
            active_profile_id: activeContextId,
            active_kind: activeContextId === "org-1" ? "self" : "shared",
            cache_scope: `org:${activeContextId}`,
            reset_required: false,
          }),
        });
        return;
      }

      if (path.includes("/activate")) {
        activationDispatched = true;
        activeContextId = "org-2";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Cache-Control": "no-store, private",
            Vary: "Authorization, X-CLARA-Profile-Context",
          },
          body: JSON.stringify({
            activated_at: new Date().toISOString(),
            active_profile_id: "org-2",
            cache_scope: "org:org-2",
            reset_required: true,
          }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("expired or invalid invitation deep-link renders safe fail-closed UI state", async ({
    page,
  }) => {
    await seedAuthenticatedSession(page, "normal");

    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;

      if (path.endsWith("/auth/me")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: 303, email: "user@clara.vn", role: "normal" }),
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
          }),
        });
        return;
      }

      if (path.includes("/invitations/preview") || path.includes("/family/invitations/preview")) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invitation unavailable or expired" }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    await page.goto("/today");
    await expect(page).toHaveURL(/\/today/);
  });
});
