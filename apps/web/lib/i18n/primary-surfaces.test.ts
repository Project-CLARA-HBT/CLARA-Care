import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "../..");
const PRIMARY_SHELL_SURFACES = [
  "components/app-shell.tsx",
  "components/navigation/app-topbar.tsx",
  "components/sidebar-nav.tsx",
];

// This scanner deliberately starts with the authenticated shell, where a
// locale switch is globally visible. Legacy/domain pages retain their existing
// bilingual maps until migrated, and must not be mistaken for catalog coverage.
const BANNED_LITERAL_COPY = [
  "Hỏi CLARA",
  "Ask CLARA",
  "Đăng xuất",
  "Sign out",
  "Đổi ngôn ngữ",
  "Change language",
  "Primary navigation",
  "Điều hướng chính",
];

describe("primary shell i18n hard-coded copy scanner", () => {
  it("uses catalog keys instead of duplicated end-user shell text", () => {
    for (const relativePath of PRIMARY_SHELL_SURFACES) {
      const source = readFileSync(resolve(ROOT, relativePath), "utf8");
      expect(source).toContain('from "@/lib/i18n/catalog"');
      for (const literal of BANNED_LITERAL_COPY) {
        expect(source).not.toContain(`"${literal}"`);
      }
    }
  });

  it("keeps the Today task-first surface catalog-backed and locale-formatted", () => {
    const source = readFileSync(resolve(ROOT, "app/today/page.tsx"), "utf8");
    expect(source).toContain('from "@/lib/i18n/catalog"');
    expect(source).toContain('getStoredUILanguage');
    expect(source).toContain('t(language, "today.title")');
    expect(source).toContain('t(language, "today.emptyDescription")');
    expect(source).toContain('language === "vi" ? "vi-VN" : "en-US"');
    for (const literal of ["Việc nên làm tiếp theo", "Hôm nay chưa có việc nào", "Mở LifeMap"]) {
      expect(source).not.toContain(`"${literal}"`);
    }
  });
});
