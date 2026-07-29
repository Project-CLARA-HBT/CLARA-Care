import { describe, expect, it } from "vitest";
import { UI_MESSAGES, formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";

describe("typed UI catalog", () => {
  it("keeps Vietnamese and English keys in parity", () => {
    expect(Object.keys(UI_MESSAGES.en).sort()).toEqual(Object.keys(UI_MESSAGES.vi).sort());
  });

  it("formats interpolation and locale-sensitive values", () => {
    expect(t("en", "profile.currentRole", { role: "Doctor" })).toBe("Current role: Doctor");
    expect(t("vi", "family.pendingTasks", { count: 2 })).toContain("2");
    expect(formatLocaleNumber("vi", 12345.6)).not.toEqual(formatLocaleNumber("en", 12345.6));
    expect(formatLocaleDate("vi", "2026-07-30")).not.toEqual(formatLocaleDate("en", "2026-07-30"));
  });
});
