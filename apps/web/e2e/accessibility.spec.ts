import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("baseline accessibility smoke", () => {
  for (const path of ["/", "/login"]) {
    test(`has no serious axe violations on ${path}`, async ({ page }) => {
      await page.goto(path, { waitUntil: "domcontentloaded", timeout: 15_000 });
      await expect(page.locator("main#main-content")).toBeVisible({ timeout: 15_000 });
      const results = await new AxeBuilder({ page }).analyze();
      const serious = results.violations.filter((violation) =>
        ["serious", "critical"].includes(violation.impact ?? ""),
      );
      expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
    });
  }
});
