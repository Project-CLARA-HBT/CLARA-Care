import { expect, test, type Page } from "@playwright/test";

async function seedPersonalSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("clara_role", "normal");
    window.localStorage.setItem("clara-theme", "light");
    window.localStorage.setItem("clara_ui_language", "vi");
  });
}

async function mockAuthenticatedApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let payload: unknown = {};

    if (path.endsWith("/auth/consent-status")) {
      payload = {
        consent_type: "medical_content",
        required_version: "e2e",
        accepted: true,
        accepted_version: "e2e",
      };
    } else if (path.endsWith("/auth/me")) {
      payload = { id: 1, role: "normal" };
    } else if (path.endsWith("/profiles/context")) {
      payload = {
        profiles: [{ id: "profile-1", kind: "self", display_name: "Tôi" }],
        active_profile_id: "profile-1",
        active_kind: "self",
        cache_scope: "profile-1",
        reset_required: false,
      };
    } else if (path.endsWith("/profiles/profile-1/capabilities")) {
      payload = {
        capabilities: {
          lifemap_capture: { enabled: true },
          lifemap_next_question_v2: { enabled: true },
          lifemap_ask_ai: { enabled: true },
          lifemap_ai_review_findings: { enabled: true },
          lifemap_baselines_v2: { enabled: true },
        },
      };
    } else if (path.endsWith("/phr/onboarding")) {
      payload = {
        status: "completed",
        needs_onboarding: false,
        version: 1,
        completed_at: "2026-07-28T00:00:00Z",
        personalization_consent: false,
        optional_fields: [],
        record: { allergies: [], conditions: [], medications: [] },
      };
    } else if (path.endsWith("/phr/record")) {
      payload = { allergies: [], conditions: [], medications: [] };
    } else if (
      path.endsWith("/family/notifications") ||
      path.endsWith("/medication-courses") ||
      path.includes("/social/")
    ) {
      payload = [];
    } else if (path.endsWith("/lifemap/today")) {
      payload = {
        generated_at: "2026-07-28T00:00:00Z",
        tasks: [{ id: "task-1", title: "Ghi lại giờ đi ngủ", due_at: null }],
        episodes: [
          {
            id: "episode-1",
            title: "Theo dõi giấc ngủ",
            priority: "routine",
          },
        ],
        pending_confirmation_count: 0,
      };
    } else if (
      path.endsWith("/lifemap/v2/disputes") ||
      path.endsWith("/lifemap/v2/baselines")
    ) {
      payload = [];
    } else if (path.endsWith("/careguard/cabinet")) {
      payload = { items: [] };
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });
}

test.describe("public experience", () => {
  test("landing and authentication entry points render without document errors", async ({ page }) => {
    for (const path of ["/", "/login", "/register", "/huong-dan", "/legal/privacy"]) {
      const response = await page.goto(path, { waitUntil: "domcontentloaded", timeout: 20_000 });
      expect(response?.status(), `${path} should return a successful document`).toBeLessThan(400);
      await expect(page.locator("main#main-content")).toBeVisible();
    }
  });
});

test.describe("authenticated care workspace", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedApi(page);
    await seedPersonalSession(page);
  });

  test("critical personal-care routes render end to end", async ({ page }) => {
    test.setTimeout(90_000);
    for (const path of [
      "/dashboard",
      "/chat",
      "/today",
      "/lifemap",
      "/phr",
      "/medicines",
      "/community",
    ]) {
      const response = await page.goto(path, { waitUntil: "domcontentloaded", timeout: 20_000 });
      expect(response?.status(), `${path} should return a successful document`).toBeLessThan(400);
      await expect(page.locator("main#main-content")).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Application error");
    }
  });

  test("desktop navigation, command bar, theme and collapse state work", async ({ page, isMobile }) => {
    test.skip(isMobile, "desktop shell assertion");
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("complementary", { name: "Điều hướng chính" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Mở CLARA Chat" })).toBeVisible();
    await expect(page.getByText("Tổng quan công việc", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Chuyển sang giao diện tối" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);

    await page.getByRole("button", { name: "Thu gọn thanh điều hướng" }).click();
    await expect(page.locator("aside.app-navigation")).toHaveClass(/w-\[5rem\]/);
    await page.reload();
    await expect(page.locator("aside.app-navigation")).toHaveClass(/w-\[5rem\]/);
  });

  test("mobile navigation opens, routes, and leaves the accessibility tree when closed", async ({ page, isMobile }) => {
    test.skip(!isMobile, "mobile shell assertion");
    await page.goto("/dashboard");

    await expect(page.getByRole("dialog", { name: "Mobile navigation" })).toHaveCount(0);
    await page.getByRole("button", { name: "Open navigation menu" }).click();
    await expect(page.getByRole("dialog", { name: "Mobile navigation" })).toBeVisible();
    await page.getByRole("link", { name: /Thuốc & an toàn/ }).first().click();
    await expect(page).toHaveURL(/\/medicines/);
    await expect(page.getByRole("dialog", { name: "Mobile navigation" })).toHaveCount(0);
  });

  test("LifeMap meets the keyboard, semantic, text-scale and reduced-motion matrix", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/lifemap", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "LifeMap", exact: true })).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByLabel("Bạn muốn tìm điều gì?")).toBeVisible();
    await expect(page.getByLabel("Điều bạn muốn ghi lại")).toBeVisible();

    await page.keyboard.press("Home");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Bỏ qua, tới nội dung chính" })).toBeFocused();

    const reducedMotion = await page.getByRole("button", { name: "Tra cứu" }).evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        animationDuration: style.animationDuration,
        transitionDuration: style.transitionDuration,
      };
    });
    expect(Number.parseFloat(reducedMotion.animationDuration)).toBeLessThanOrEqual(0.00001);
    expect(Number.parseFloat(reducedMotion.transitionDuration)).toBeLessThanOrEqual(0.00001);

    await page.evaluate(() => {
      document.documentElement.style.fontSize = "200%";
    });
    await expect(page.getByRole("heading", { name: "Ghi nhận nhanh" })).toBeVisible();
    const layout = await page.evaluate(() => {
      const viewportWidth = document.documentElement.clientWidth;
      return {
        overflow: document.documentElement.scrollWidth - viewportWidth,
        offenders: Array.from(document.querySelectorAll<HTMLElement>("body *"))
          .map((element) => {
            const bounds = element.getBoundingClientRect();
            return {
              tag: element.tagName,
              className: element.className.toString().slice(0, 100),
              text: element.textContent?.trim().slice(0, 60) ?? "",
              left: Math.round(bounds.left),
              right: Math.round(bounds.right),
            };
          })
          .filter((item) => item.left < -1 || item.right > viewportWidth + 1)
          .slice(0, 12),
      };
    });
    expect(
      layout.overflow,
      `200% text overflow: ${JSON.stringify(layout.offenders)}`,
    ).toBeLessThanOrEqual(1);

    const contrast = await page.getByRole("heading", { name: "Ghi nhận nhanh" }).evaluate((node) => {
      const parse = (value: string) => {
        const parts = value.match(/\d+(?:\.\d+)?/g)?.map(Number) ?? [];
        return parts.slice(0, 3);
      };
      const luminance = (rgb: number[]) => {
        const channels = rgb.map((value) => {
          const normalized = value / 255;
          return normalized <= 0.03928
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const foreground = luminance(parse(getComputedStyle(node).color));
      const background = luminance(parse(getComputedStyle(document.body).backgroundColor));
      return (Math.max(foreground, background) + 0.05) /
        (Math.min(foreground, background) + 0.05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
  });
});
