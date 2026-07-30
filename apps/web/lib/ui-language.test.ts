import { afterEach, describe, expect, it } from "vitest";

import {
  UI_LANGUAGE_COOKIE_NAME,
  UI_LANGUAGE_STORAGE_KEY,
  getStoredUILanguage,
  saveUILanguage,
} from "@/lib/ui-language";

afterEach(() => {
  window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
  document.cookie = `${UI_LANGUAGE_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
});

describe("UI language persistence", () => {
  it("uses the Vietnamese fallback when no persisted value exists", () => {
    expect(getStoredUILanguage()).toBe("vi");
  });

  it("persists a language in both browser stores for server and client rendering", () => {
    saveUILanguage("en");

    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe("en");
    expect(document.cookie).toContain(`${UI_LANGUAGE_COOKIE_NAME}=en`);
    expect(document.documentElement.lang).toBe("en");
  });

  it("falls back to the locale cookie when legacy local storage is absent", () => {
    document.cookie = `${UI_LANGUAGE_COOKIE_NAME}=en; Path=/; SameSite=Lax`;

    expect(getStoredUILanguage()).toBe("en");
  });
});
