import { expect, test, type Page } from "@playwright/test";

/**
 * UI fixtures only: public-source metadata and empty owner-scoped workspaces.
 * They deliberately contain no patient, prescription, or clinical decision data.
 */
async function seedPersonalSession(page: Page) {
  await page.addInitScript(() => {
    // Council and Scribe are clinician workspaces.  The role is deliberately
    // scoped to this UI route test; authorization itself remains server-owned.
    window.localStorage.setItem("clara_role", "doctor");
    window.localStorage.setItem("clara-theme", "dark");
    window.localStorage.setItem("clara_ui_language", "vi");
  });
}

async function mockWorkspaceApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let payload: unknown = {};

    if (path.endsWith("/auth/consent-status")) {
      payload = { consent_type: "medical_content", required_version: "e2e", accepted: true, accepted_version: "e2e" };
    } else if (path.endsWith("/auth/me")) {
      payload = { id: 1, role: "doctor" };
    } else if (path.endsWith("/profiles/context")) {
      payload = { profiles: [{ id: "profile-e2e", kind: "self", display_name: "Tôi" }], active_profile_id: "profile-e2e", active_kind: "self", cache_scope: "profile-e2e", reset_required: false };
    } else if (path.endsWith("/lifemap/today")) {
      payload = { generated_at: "2026-08-08T00:00:00Z", tasks: [], episodes: [], pending_confirmation_count: 0 };
    } else if (path.endsWith("/evidence-subscriptions") || path.endsWith("/evidence-change-notifications")) {
      payload = [];
    } else if (path.endsWith("/research/source-hub/catalog")) {
      payload = { sources: [{ key: "pubmed", label: "PubMed", description: "Nguồn chỉ mục y văn công khai.", default_query: "guideline", supports_live_sync: true }] };
    } else if (path.endsWith("/research/source-hub/records")) {
      payload = { records: [{ id: "public-source-fixture-1", source: "pubmed", title: "Public source fixture for interface verification", query: "guideline", published_at: "2025-01-01T00:00:00Z", synced_at: "2026-08-08T00:00:00Z", metadata: {} }] };
    } else if (path.endsWith("/council/cases")) {
      payload = { items: [], total: 0 };
    } else if (path.endsWith("/scribe/sessions")) {
      payload = { items: [], total: 0 };
    } else if (path.endsWith("/scribe/analytics/summary")) {
      payload = { total_sessions: 0, completed_sessions: 0, draft_sessions: 0, sessions_today: 0, avg_transcript_chars: 0 };
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

test.describe("Evidence, Source Hub, Council and Scribe states", () => {
  test.beforeEach(async ({ page }) => {
    await mockWorkspaceApi(page);
    await seedPersonalSession(page);
  });

  test("renders deliberate first-use states and a public-source result without leaking technical errors", async ({ page }) => {
    test.setTimeout(90_000);
    const routes = [
      { path: "/evidence", content: "Cần một hành trình", semantic: "text" },
      { path: "/research/source-hub", content: "Nguồn nghiên cứu", semantic: "heading" },
      { path: "/council", content: "Chưa có dữ liệu phân tích", semantic: "text" },
      { path: "/scribe", content: "Danh sách phiên", semantic: "heading" },
    ];

    for (const route of routes) {
      const response = await page.goto(route.path, { waitUntil: "domcontentloaded", timeout: 20_000 });
      expect(response?.status(), `${route.path} document status`).toBeLessThan(400);
      await expect(page.locator("main#main-content")).toBeVisible();
      // Navigation may retain an off-canvas copy of a route label at tablet and
      // mobile widths.  Use the page heading only where the product renders a
      // heading; Council intentionally exposes its empty-state label as text.
      const content = route.semantic === "heading"
        ? page.getByRole("heading", { name: route.content, exact: true }).last()
        : page.getByText(route.content, { exact: true }).last();
      await expect(content).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Application error");
      await expect(page.locator("body")).not.toContainText("Traceback");
      const horizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(horizontalOverflow, `${route.path} must keep horizontal scrolling within its local controls`).toBeLessThanOrEqual(1);
    }

    await expect(page.getByText("Chưa có phiên nào.", { exact: true })).toBeVisible();

    await page.goto("/research/source-hub", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Kết quả nguồn nghiên cứu", { exact: true })).toBeVisible();
    await expect(page.getByText("Public source fixture for interface verification", { exact: true })).toBeVisible();
  });
});
