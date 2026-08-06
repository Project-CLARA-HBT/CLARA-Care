import { expect, test, type Page } from "@playwright/test";

type TodayPayload = {
  generated_at: string;
  tasks: Array<Record<string, unknown>>;
  episodes: Array<Record<string, unknown>>;
  pending_confirmation_count: number;
  completed_today_count: number;
  activity_days: Array<{ date: string; completed_count: number }>;
};

const week = [
  { date: "2026-07-31", completed_count: 1 },
  { date: "2026-08-01", completed_count: 0 },
  { date: "2026-08-02", completed_count: 2 },
  { date: "2026-08-03", completed_count: 1 },
  { date: "2026-08-04", completed_count: 0 },
  { date: "2026-08-05", completed_count: 1 },
  { date: "2026-08-06", completed_count: 1 },
];

async function prepareToday(page: Page, today: TodayPayload) {
  await page.addInitScript(() => {
    window.localStorage.setItem("clara_role", "normal");
    window.localStorage.setItem("clara-theme", "dark");
    window.localStorage.setItem("clara_ui_language", "vi");
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path.endsWith("/lifemap/today")
      ? today
      : path.endsWith("/auth/me")
        ? { id: 1, role: "normal" }
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

async function expectNoHorizontalOverflow(page: Page) {
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
}

test.describe("Today real-data states", () => {
  test("shows an accepted next task without claiming it is complete", async ({ page }) => {
    await prepareToday(page, {
      generated_at: "2026-08-06T06:00:00Z",
      tasks: [{ id: "task-1", title: "Ghi lại triệu chứng sau bữa trưa", due_at: "2026-08-06T06:30:00Z", status: "accepted", version: 3, episode_id: "episode-1", episode_title: "Theo dõi đau dạ dày" }],
      episodes: [{ id: "episode-1", title: "Theo dõi đau dạ dày", priority: "routine" }],
      pending_confirmation_count: 1,
      completed_today_count: 0,
      activity_days: week,
    });
    await page.goto("/today", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Ghi lại triệu chứng sau bữa trưa" })).toBeVisible();
    await expect(page.getByText("Theo dõi đau dạ dày")).toBeVisible();
    await expect(page.getByRole("link", { name: "Xem việc" })).toHaveAttribute("href", "/today/tasks/task-1");
    await expect(page.getByText(/Chưa dùng làm kết luận/)).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.screenshot({ path: `test-results/today-active-${test.info().project.name}.png`, fullPage: true });
  });

  test("shows completion and seven-day activity only from returned counts", async ({ page }) => {
    await prepareToday(page, {
      generated_at: "2026-08-06T06:00:00Z",
      tasks: [],
      episodes: [{ id: "episode-1", title: "Theo dõi đau dạ dày", priority: "routine" }],
      pending_confirmation_count: 0,
      completed_today_count: 1,
      activity_days: week,
    });
    await page.goto("/today", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Bạn đã hoàn thành các việc hôm nay" })).toBeVisible();
    await expect(page.getByText("5/7 ngày có việc hoàn thành")).toBeVisible();
    await expect(page.getByText("3 việc đã hoàn thành")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    await page.screenshot({ path: `test-results/today-completed-${test.info().project.name}.png`, fullPage: true });
  });

  test("keeps the first-time state focused and explains user control", async ({ page }) => {
    await prepareToday(page, {
      generated_at: "2026-08-06T06:00:00Z",
      tasks: [],
      episodes: [],
      pending_confirmation_count: 0,
      completed_today_count: 0,
      activity_days: week.map((day) => ({ ...day, completed_count: 0 })),
    });
    await page.goto("/today", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Bạn chưa có việc cần làm hôm nay" })).toBeVisible();
    await expect(page.getByText(/CLARA không tự thêm việc thay bạn/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Tạo hành trình" })).toHaveAttribute("href", "/lifemap/new");
    await expectNoHorizontalOverflow(page);
    await page.screenshot({ path: `test-results/today-first-time-${test.info().project.name}.png`, fullPage: true });
  });
});
