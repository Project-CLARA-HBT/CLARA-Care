import { expect, test, type Page } from "@playwright/test";

async function prepareDashboard(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("clara_role", "researcher");
    window.localStorage.setItem("clara-theme", "light");
    window.localStorage.setItem("clara_ui_language", "vi");
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path.endsWith("/system/dashboard")
      ? {
          generated_at: "2026-08-06T06:00:00Z",
          user: { role: "researcher" },
          cabinet: { item_total: 2, expiring_soon_total: 1 },
          research: {
            recent_queries: [
              { id: "query-1", query: "Tổng hợp bằng chứng tăng huyết áp", created_at: "2026-08-06T05:00:00Z" },
            ],
          },
          alerts: [
            { id: "source-review", severity: "warning", message: "Có nguồn cần xem lại trước khi tổng hợp.", href: "/research/source-hub" },
          ],
          tasks: [
            { id: "review-source", title: "Rà soát nguồn nghiên cứu", detail: "Kiểm tra nguồn trước khi tiếp tục.", tone: "warn", href: "/research/source-hub" },
          ],
        }
      : path.endsWith("/auth/me")
        ? { id: 1, role: "researcher" }
        : path.endsWith("/auth/consent-status")
          ? { accepted: true, required_version: "e2e", accepted_version: "e2e" }
          : path.endsWith("/profiles/context")
            ? { profiles: [], active_profile_id: null, active_kind: "self", cache_scope: "self", reset_required: false }
            : path.endsWith("/phr/onboarding")
              ? { status: "completed", needs_onboarding: false, version: 1 }
              : [];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

test.describe("professional dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await prepareDashboard(page);
  });

  test("prioritizes the real alert and role-aware workflow without overflow", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Tổng quan công việc", exact: true })).toBeVisible();
    await expect(page.getByText("Có nguồn cần xem lại trước khi tổng hợp.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Mở mục liên quan" })).toHaveAttribute("href", "/research/source-hub");
    await expect(page.getByRole("heading", { name: "Rà soát nguồn nghiên cứu" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Thư viện bằng chứng" })).toBeVisible();
    await expect(page.getByText("Ổn định", { exact: true })).toHaveCount(0);

    const layout = await page.evaluate(() => {
      const viewport = document.documentElement.clientWidth;
      return {
        overflow: document.documentElement.scrollWidth - viewport,
        offenders: Array.from(document.querySelectorAll<HTMLElement>("body *"))
          .filter((element) => element.getBoundingClientRect().right > viewport + 1)
          .slice(0, 8)
          .map((element) => ({
            tag: element.tagName,
            className: element.className,
            right: Math.round(element.getBoundingClientRect().right),
            text: element.textContent?.trim().slice(0, 80),
          })),
      };
    });
    expect(layout.overflow, JSON.stringify(layout.offenders)).toBeLessThanOrEqual(1);

    await page.screenshot({
      path: `test-results/dashboard-${test.info().project.name}.png`,
      fullPage: true,
    });
  });

  test("keeps the loading and failed states non-reassuring", async ({ page }) => {
    await page.route("**/api/v1/system/dashboard", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/system/dashboard")) {
        await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
        return;
      }
      await route.continue();
    });
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Chưa thể xác định trạng thái công việc.")).toBeVisible();
    await expect(page.locator("span").filter({ hasText: "Trạng thái công việc" })).toContainText("Chưa xác định");
    await expect(page.getByText("Hôm nay chưa có việc cần xử lý")).toHaveCount(0);
  });
});
