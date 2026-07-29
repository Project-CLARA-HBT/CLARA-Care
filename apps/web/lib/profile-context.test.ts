import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACTIVE_PROFILE_STORAGE_KEY,
  PROFILE_CACHE_PREFIX,
  clearActiveProfileContext,
  getActiveProfileId,
  setActiveProfileId,
} from "@/lib/profile-context";

describe("profile context boundary", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("changes context only after purging profile-scoped client state", () => {
    window.localStorage.setItem(`${PROFILE_CACHE_PREFIX}old-summary`, "private old profile data");
    window.sessionStorage.setItem(`${PROFILE_CACHE_PREFIX}old-chat`, "private old profile data");
    window.sessionStorage.setItem("clara_access_token_session", "must-survive");
    const changed = vi.fn();
    window.addEventListener("clara:profile-context-changed", changed);

    setActiveProfileId("42");

    expect(getActiveProfileId()).toBe("42");
    expect(window.localStorage.getItem(`${PROFILE_CACHE_PREFIX}old-summary`)).toBeNull();
    expect(window.sessionStorage.getItem(`${PROFILE_CACHE_PREFIX}old-chat`)).toBeNull();
    expect(window.sessionStorage.getItem("clara_access_token_session")).toBe("must-survive");
    expect(changed).toHaveBeenCalledTimes(1);
    window.removeEventListener("clara:profile-context-changed", changed);
  });

  it("clears an active selection on logout without treating it as health data storage", () => {
    window.localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, "42");
    window.localStorage.setItem(`${PROFILE_CACHE_PREFIX}summary`, "cached");

    clearActiveProfileContext();

    expect(getActiveProfileId()).toBeNull();
    expect(window.localStorage.getItem(`${PROFILE_CACHE_PREFIX}summary`)).toBeNull();
  });
});
