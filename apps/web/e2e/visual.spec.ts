import { expect, test } from "@playwright/test";

test.describe("baseline visual smoke", () => {
  for (const path of ["/", "/login"]) {
    test(`captures a stable synthetic screenshot for ${path}`, async ({ page }) => {
      const runtimeErrors: string[] = [];
      page.on("pageerror", (error) => runtimeErrors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") runtimeErrors.push(message.text());
      });
      await page.goto(path, { waitUntil: "domcontentloaded", timeout: 15_000 });
      await expect(page.locator("main#main-content")).toBeVisible({ timeout: 15_000 });
      const viewport = await page.evaluate(() => ({
        width: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(viewport.scrollWidth - viewport.width).toBeLessThanOrEqual(1);
      await page.screenshot({
        path: `test-results/visual-${path === "/" ? "landing" : "login"}-${test.info().project.name}.png`,
        fullPage: true,
      });
      expect(runtimeErrors, `Unexpected browser errors on ${path}`).toEqual([]);
    });
  }
});
