import { describe, expect, it } from "vitest";

import {
  getGroupedNavItems,
  getNavItemsByRole,
  getPageMeta,
  getRoleHomePath,
  isAuthenticatedUtilityRoute,
  isPublicRoute,
  isRouteAllowedForRole,
  resolvePostLoginPath,
} from "@/lib/navigation.config";
import {
  getAvailableWorkspaces,
  getMobileWorkspaceNav,
  getWorkspaceForPath,
  getWorkspaceNavigation,
} from "@/lib/navigation.workspaces";

describe("authenticated navigation defaults", () => {
  it("lands consumers on Home and professional roles on dashboard, never chat", () => {
    expect(getRoleHomePath("normal")).toBe("/home");
    expect(resolvePostLoginPath({ role: "normal" })).toBe("/home");
    for (const role of ["researcher", "doctor", "admin"] as const) {
      expect(getRoleHomePath(role)).toBe("/dashboard");
      expect(resolvePostLoginPath({ role })).toBe("/dashboard");
    }
  });

  it("treats the professional overview as a default route, not a workspace item", () => {
    for (const role of ["researcher", "doctor", "admin"] as const) {
      for (const workspace of getAvailableWorkspaces(role)) {
        expect(getWorkspaceNavigation(role, workspace.id).primary.map((item) => item.href))
          .not.toContain("/dashboard");
      }
    }
    expect(getWorkspaceForPath("/dashboard", "doctor", "research")).toBe("research");
    expect(getWorkspaceForPath("/dashboard", "doctor")).toBe("clinical");
    expect(getWorkspaceForPath("/dashboard", "researcher")).toBe("research");
    expect(getWorkspaceForPath("/dashboard", "admin")).toBe("admin");
  });

  it("keeps research visible for evidence roles while preserving consumer deep links", () => {
    for (const role of ["researcher", "doctor", "admin"] as const) {
      expect(
        getNavItemsByRole(role).some((item) => item.href === "/research"),
      ).toBe(true);
      expect(
        getNavItemsByRole(role).some((item) => item.href === "/evidence"),
      ).toBe(true);
      expect(
        getNavItemsByRole(role).some((item) => item.href === "/visits"),
      ).toBe(true);
      expect(
        getNavItemsByRole(role).some((item) => item.href === "/family"),
      ).toBe(true);
    }
    const consumer = getNavItemsByRole("normal").map((item) => item.href);
    expect(consumer).not.toContain("/research");
    expect(consumer).not.toContain("/evidence");
    expect(isRouteAllowedForRole("/research", "normal")).toBe(true);
    expect(isRouteAllowedForRole("/evidence", "normal")).toBe(true);
  });

  it("preserves an explicit safe next destination after login", () => {
    expect(resolvePostLoginPath({ nextPath: "/phr", role: "normal" })).toBe(
      "/phr",
    );
  });

  it("keeps mobile navigation to four workspace tasks plus the separate More control", () => {
    const primary = getMobileWorkspaceNav("normal", "personal").map((item) => item.href);
    expect(primary[0]).toBe("/today");
    expect(primary).toContain("/chat");
    expect(primary).toContain("/lifemap");
    expect(primary).toContain("/medicines");
    expect(primary).toHaveLength(4);
  });

  it("limits every available workspace to seven primary destinations", () => {
    for (const role of ["normal", "researcher", "doctor", "admin"] as const) {
      for (const workspace of getAvailableWorkspaces(role)) {
        const navigation = getWorkspaceNavigation(role, workspace.id);
        expect(navigation.primary.length).toBeGreaterThan(0);
        expect(navigation.primary.length).toBeLessThanOrEqual(7);
        expect(new Set(navigation.primary.map((item) => item.href)).size).toBe(
          navigation.primary.length,
        );
      }
    }
  });

  it("keeps secondary personal capabilities reachable through More", () => {
    const secondary = getWorkspaceNavigation("normal", "personal").secondary.map(
      (item) => item.href,
    );
    expect(secondary).toEqual(
      expect.arrayContaining(["/visits", "/family", "/chat/shares", "/huong-dan"]),
    );
  });

  it("allows onboarding without turning it into permanent navigation", () => {
    expect(isAuthenticatedUtilityRoute("/welcome")).toBe(true);
    expect(isAuthenticatedUtilityRoute("/welcome/body")).toBe(true);
    expect(
      getNavItemsByRole("normal").some((item) => item.href === "/welcome"),
    ).toBe(false);
  });

  it("keeps opaque public PHR share routes outside the authenticated shell", () => {
    expect(isPublicRoute("/phr/shared/opaque-token")).toBe(true);
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

  it("localizes every visible navigation label, page meta, and group label", () => {
    const english = getNavItemsByRole("admin", "en");
    expect(english.find((item) => item.href === "/scribe")?.label).toBe(
      "Visit notes",
    );
    expect(
      english.find((item) => item.href === "/admin/observability")?.page.title,
    ).toBe("Operational monitoring");
    expect(
      getGroupedNavItems("doctor", "en").find(
        (group) => group.key === "clinical",
      )?.label,
    ).toBe("Clinical");
    expect(getPageMeta("/dashboard/control-tower", "en").title).toBe(
      "Knowledge control",
    );
    expect(getPageMeta("/unknown-route", "en").title).toBe("Workspace");
  });
});
