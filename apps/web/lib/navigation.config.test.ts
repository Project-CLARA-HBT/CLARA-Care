import { describe, expect, it } from "vitest";

import {
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

  it("exposes Research as a first-class destination to every supported role", () => {
    for (const role of ["normal", "researcher", "doctor", "admin"] as const) {
      expect(getNavItemsByRole(role).some((item) => item.href === "/research")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/evidence")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/visits")).toBe(true);
      expect(getNavItemsByRole(role).some((item) => item.href === "/family")).toBe(true);
    }
  });

  it("preserves an explicit safe next destination after login", () => {
    expect(resolvePostLoginPath({ nextPath: "/phr", role: "normal" })).toBe("/phr");
  });

  it("allows onboarding without turning it into permanent navigation", () => {
    expect(isAuthenticatedUtilityRoute("/welcome")).toBe(true);
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
