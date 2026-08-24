import { describe, expect, it, vi } from "vitest";
import {
  getProfileScopeFromKey,
  isProfileScopedKey,
  queryKeys,
  useActiveProfileQueryKeys,
} from "./query-keys";
import * as profileContext from "@/lib/profile-context";

describe("TanStack Query Key Factory", () => {
  it("produces static global query keys", () => {
    expect(queryKeys.global.all).toEqual(["global"]);
    expect(queryKeys.global.session()).toEqual(["global", "session"]);
    expect(queryKeys.global.auth()).toEqual(["global", "auth"]);
    expect(queryKeys.global.config()).toEqual(["global", "config"]);
    expect(queryKeys.global.systemHealth()).toEqual(["global", "system-health"]);
  });

  it("produces profiles management keys", () => {
    expect(queryKeys.profiles.all).toEqual(["profiles"]);
    expect(queryKeys.profiles.list()).toEqual(["profiles", "list"]);
    expect(queryKeys.profiles.detail("p1")).toEqual(["profiles", "detail", "p1"]);
    expect(queryKeys.profiles.grants()).toEqual(["profiles", "grants", "all"]);
    expect(queryKeys.profiles.grants("p1")).toEqual(["profiles", "grants", "p1"]);
  });

  it("scopes all profile vertical keys under ['profile', profileId]", () => {
    const keys = queryKeys.profile("user-profile-99");
    expect(keys.all).toEqual(["profile", "user-profile-99"]);

    // Home
    expect(keys.home.all).toEqual(["profile", "user-profile-99", "home"]);
    expect(keys.home.overview()).toEqual(["profile", "user-profile-99", "home", "overview"]);
    expect(queryKeys.home.overview("user-profile-99")).toEqual([
      "profile",
      "user-profile-99",
      "home",
      "overview",
    ]);
    expect(queryKeys.home.overview()).toEqual(["profile", "anonymous", "home", "overview"]);
    expect(keys.home.summary({ filter: "today" })).toEqual([
      "profile",
      "user-profile-99",
      "home",
      "summary",
      { filter: "today" },
    ]);
    expect(keys.home.schedule("2026-08-19")).toEqual([
      "profile",
      "user-profile-99",
      "home",
      "schedule",
      { date: "2026-08-19" },
    ]);
    expect(keys.home.recentChanges(10)).toEqual([
      "profile",
      "user-profile-99",
      "home",
      "recent-changes",
      { limit: 10 },
    ]);
    expect(keys.home.alerts()).toEqual(["profile", "user-profile-99", "home", "alerts"]);

    // Health
    expect(keys.health.all).toEqual(["profile", "user-profile-99", "health"]);
    expect(keys.health.summary("ctx-v1")).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "summary",
      { contextVersion: "ctx-v1" },
    ]);
    expect(keys.health.timeline({ cursor: "tok-1", types: ["medication"] })).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "timeline",
      { cursor: "tok-1", types: ["medication"] },
    ]);
    expect(keys.health.demographics()).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "demographics",
    ]);
    expect(keys.health.allergies.list()).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "allergies",
      "list",
      {},
    ]);
    expect(keys.health.allergies.detail("alg-1")).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "allergies",
      "detail",
      "alg-1",
    ]);
    expect(keys.health.medications.changes("med-1")).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "medications",
      "med-1",
      "changes",
    ]);
    expect(keys.health.measurements.latest()).toEqual([
      "profile",
      "user-profile-99",
      "health",
      "measurements",
      "latest",
    ]);

    // Care
    expect(keys.care.all).toEqual(["profile", "user-profile-99", "care"]);
    expect(keys.care.tasks.list({ status: "pending" })).toEqual([
      "profile",
      "user-profile-99",
      "care",
      "tasks",
      "list",
      { status: "pending" },
    ]);
    expect(keys.care.family.members()).toEqual([
      "profile",
      "user-profile-99",
      "care",
      "family",
      "members",
    ]);

    // Ask
    expect(keys.ask.threads({ limit: 5 })).toEqual([
      "profile",
      "user-profile-99",
      "ask",
      "threads",
      { limit: 5 },
    ]);
    expect(keys.ask.thread("t-1")).toEqual([
      "profile",
      "user-profile-99",
      "ask",
      "threads",
      "t-1",
    ]);

    // Connectors
    expect(keys.connectors.status()).toEqual([
      "profile",
      "user-profile-99",
      "connectors",
      "status",
    ]);

    // You / Privacy / Sharing / Integrations
    expect(keys.you.all).toEqual(["profile", "user-profile-99", "you"]);
    expect(keys.you.overview()).toEqual(["profile", "user-profile-99", "you", "overview"]);
    expect(keys.you.profile()).toEqual(["profile", "user-profile-99", "you", "profile"]);
    expect(keys.you.emergencyCard()).toEqual(["profile", "user-profile-99", "you", "emergency-card"]);
    expect(keys.you.sharing.overview()).toEqual(["profile", "user-profile-99", "you", "sharing", "overview"]);
    expect(keys.you.privacy.aiTransparency()).toEqual(["profile", "user-profile-99", "you", "privacy", "ai-transparency"]);
    expect(keys.you.integrations()).toEqual(["profile", "user-profile-99", "you", "integrations"]);
    expect(keys.you.notifications()).toEqual(["profile", "user-profile-99", "you", "notifications"]);
    expect(keys.you.settings()).toEqual(["profile", "user-profile-99", "you", "settings"]);
    expect(keys.you.security()).toEqual(["profile", "user-profile-99", "you", "security"]);

    // Custom
    expect(keys.custom("insights", "weekly")).toEqual([
      "profile",
      "user-profile-99",
      "insights",
      "weekly",
    ]);
  });

  it("handles empty / null profileId falling back to 'anonymous'", () => {
    const keysNull = queryKeys.profile(null);
    expect(keysNull.all).toEqual(["profile", "anonymous"]);

    const keysUndefined = queryKeys.profile(undefined);
    expect(keysUndefined.all).toEqual(["profile", "anonymous"]);

    const keysBlank = queryKeys.profile("   ");
    expect(keysBlank.all).toEqual(["profile", "anonymous"]);
  });

  it("isProfileScopedKey and getProfileScopeFromKey accurately detect profile keys", () => {
    const profileKey = ["profile", "p-42", "health", "summary"] as const;
    const globalKey = ["global", "session"] as const;
    const invalidKey = ["something-else"] as const;

    expect(isProfileScopedKey(profileKey)).toBe(true);
    expect(isProfileScopedKey(profileKey, "p-42")).toBe(true);
    expect(isProfileScopedKey(profileKey, "p-other")).toBe(false);

    expect(isProfileScopedKey(globalKey)).toBe(false);
    expect(isProfileScopedKey(invalidKey)).toBe(false);

    expect(getProfileScopeFromKey(profileKey)).toBe("p-42");
    expect(getProfileScopeFromKey(globalKey)).toBeNull();
  });

  it("useActiveProfileQueryKeys respects active profile context", () => {
    vi.spyOn(profileContext, "getActiveProfileId").mockReturnValue("active-profile-77");
    const keys = useActiveProfileQueryKeys();
    expect(keys.all).toEqual(["profile", "active-profile-77"]);

    const overrideKeys = useActiveProfileQueryKeys("manual-id");
    expect(overrideKeys.all).toEqual(["profile", "manual-id"]);

    vi.restoreAllMocks();
  });
});
