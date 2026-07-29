import { describe, expect, it } from "vitest";

import {
  getMobilePrimaryNav,
  getNavItemsByRole,
  getRoleHomePath,
  isAuthenticatedUtilityRoute,
  isRouteAllowedForRole,
  resolvePostLoginPath,
} from "@/lib/navigation.config";

describe("authenticated navigation defaults", () => {
  it("lands consumers on Today and professional roles on dashboard, never chat", () => {
    expect(getRoleHomePath("normal")).toBe("/today");
    expect(resolvePostLoginPath({ role: "normal" })).toBe("/today");
    for (const role of ["researcher", "doctor", "admin"] as const) {
      expect(getRoleHomePath(role)).toBe("/dashboard");
      expect(resolvePostLoginPath({ role })).toBe("/dashboard");
    }
  });

  it("keeps research visible for evidence roles while preserving consumer deep links", () => {
    for (const role of ["researcher", "doctor", "admin"] as const) {
      expect(getNavItemsByRole(role).some((item) => item.href === "/research")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/evidence")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/visits")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/family")).toBe(true);
    }
    const consumer = getNavItemsByRole("normal").map((item) => item.href);
    expect(consumer).not.toContain("/research");
    expect(consumer).not.toContain("/evidence");
    expect(isRouteAllowedForRole("/research", "normal")).toBe(true);
    expect(isRouteAllowedForRole("/evidence", "normal")).toBe(true);
  });

  it("preserves an explicit safe next destination after login", () => {
    expect(resolvePostLoginPath({ nextPath: "/phr", role: "normal" })).toBe("/phr");
  });

  it("leads the consumer mobile nav with Today/LifeMap, not Chat (chat is not the IA)", () => {
    const primary = getMobilePrimaryNav("normal").map((item) => item.href);
    // Per the LifeMap product spec §6.1, chat is an input/explanation surface,
    // not a primary consumer destination. Today must lead; chat is reached via
    // the persistent "Hỏi CLARA" action instead of a bottom tab.
    expect(primary[0]).toBe("/today");
    expect(primary).toContain("/lifemap");
    expect(primary).toContain("/medicines");
    expect(primary).not.toContain("/chat");
  });

  it("allows onboarding without turning it into permanent navigation", () => {
    expect(isAuthenticatedUtilityRoute("/welcome")).toBe(true);
    expect(isAuthenticatedUtilityRoute("/welcome/body")).toBe(true);
    expect(
      getNavItemsByRole("normal").some((item) => item.href === "/welcome"),
    ).toBe(false);
  });

  it("consolidates medication surfaces into one Medicines hub entry", () => {
    for (const role of ["normal", "researcher", "doctor", "admin"] as const) {
      const visible = getNavItemsByRole(role).map((item) => item.href);
      // Only the unified hub is shown; the legacy surfaces are hidden.
      expect(visible).toContain("/medicines");
      expect(visible).not.toContain("/selfmed");
      expect(visible).not.toContain("/careguard");
    }
  });

  it("keeps legacy consumer routes reachable without cluttering navigation", () => {
    const visible = getNavItemsByRole("normal").map((item) => item.href);
    expect(visible).not.toContain("/dashboard");
    expect(visible).not.toContain("/community");
    // Redirect stubs must stay route-allowed so the shell guard lets them load
    // and forward into the correct hub tab.
    expect(isRouteAllowedForRole("/selfmed", "normal")).toBe(true);
    expect(isRouteAllowedForRole("/careguard", "normal")).toBe(true);
  });
});
