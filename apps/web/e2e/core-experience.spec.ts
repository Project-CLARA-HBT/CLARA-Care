import { expect, test, type Page } from "@playwright/test";

async function seedPersonalSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("clara_role", "normal");
    window.localStorage.setItem("clara-theme", "light");
    window.localStorage.setItem("clara_ui_language", "vi");
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
    await seedPersonalSession(page);
  });

  test("critical personal-care routes render end to end", async ({ page }) => {
    test.setTimeout(90_000);
    for (const path of ["/dashboard", "/chat", "/phr", "/selfmed", "/careguard", "/community"]) {
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
    await page.getByRole("link", { name: /Tủ thuốc/ }).first().click();
    await expect(page).toHaveURL(/\/selfmed/);
    await expect(page.getByRole("dialog", { name: "Mobile navigation" })).toHaveCount(0);
  });
});
