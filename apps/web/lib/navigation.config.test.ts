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
  getDefaultPresentationMode,
  getDefaultWorkspace,
  getMobileWorkspaceNav,
  getWorkspaceForPath,
  getWorkspaceNavigation,
  isWorkspaceAvailable,
  type WorkspaceId,
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
    expect(isAuthenticatedUtilityRoute("/onboarding")).toBe(true);
    expect(
      getNavItemsByRole("normal").some((item) => item.href === "/welcome"),
    ).toBe(false);
    expect(
      getNavItemsByRole("normal").some((item) => item.href === "/onboarding"),
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

  describe("4-mode presentation architecture", () => {
    it("defines default presentation mode / workspace mappings for all roles", () => {
      expect(getDefaultWorkspace("normal")).toBe("personal");
      expect(getDefaultPresentationMode("normal")).toBe("personal");

      expect(getDefaultWorkspace("doctor")).toBe("clinical");
      expect(getDefaultPresentationMode("doctor")).toBe("clinical");

      expect(getDefaultWorkspace("researcher")).toBe("research");
      expect(getDefaultPresentationMode("researcher")).toBe("research");

      expect(getDefaultWorkspace("admin")).toBe("admin");
      expect(getDefaultPresentationMode("admin")).toBe("admin");
    });

    it("gates available workspaces by role and allows doctors, researchers, and admins to switch to Personal view", () => {
      // Normal consumers only have personal mode
      const normalWorkspaces = getAvailableWorkspaces("normal").map((w) => w.id);
      expect(normalWorkspaces).toEqual(["personal"]);
      expect(isWorkspaceAvailable("normal", "personal")).toBe(true);
      expect(isWorkspaceAvailable("normal", "clinical")).toBe(false);
      expect(isWorkspaceAvailable("normal", "research")).toBe(false);
      expect(isWorkspaceAvailable("normal", "admin")).toBe(false);

      // Doctors have Personal, Clinical, and Research
      const doctorWorkspaces = getAvailableWorkspaces("doctor").map((w) => w.id);
      expect(doctorWorkspaces).toEqual(["personal", "clinical", "research"]);
      expect(isWorkspaceAvailable("doctor", "personal")).toBe(true);
      expect(isWorkspaceAvailable("doctor", "clinical")).toBe(true);
      expect(isWorkspaceAvailable("doctor", "research")).toBe(true);
      expect(isWorkspaceAvailable("doctor", "admin")).toBe(false);

      // Researchers have Personal and Research
      const researcherWorkspaces = getAvailableWorkspaces("researcher").map((w) => w.id);
      expect(researcherWorkspaces).toEqual(["personal", "research"]);
      expect(isWorkspaceAvailable("researcher", "personal")).toBe(true);
      expect(isWorkspaceAvailable("researcher", "clinical")).toBe(false);
      expect(isWorkspaceAvailable("researcher", "research")).toBe(true);
      expect(isWorkspaceAvailable("researcher", "admin")).toBe(false);

      // Admins have Personal, Clinical, Research, and Admin
      const adminWorkspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(adminWorkspaces).toEqual(["personal", "clinical", "research", "admin"]);
      expect(isWorkspaceAvailable("admin", "personal")).toBe(true);
      expect(isWorkspaceAvailable("admin", "clinical")).toBe(true);
      expect(isWorkspaceAvailable("admin", "research")).toBe(true);
      expect(isWorkspaceAvailable("admin", "admin")).toBe(true);
    });

    it("ensures server RBAC authorization is locked and unaffected by presentation mode changes", () => {
      // Admin routes remain locked to admin role regardless of mode
      expect(isRouteAllowedForRole("/admin/overview", "admin")).toBe(true);
      expect(isRouteAllowedForRole("/admin/overview", "doctor")).toBe(false);
      expect(isRouteAllowedForRole("/admin/overview", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/admin/overview", "normal")).toBe(false);

      // Clinical routes remain locked to doctor and admin
      expect(isRouteAllowedForRole("/council", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/council", "admin")).toBe(true);
      expect(isRouteAllowedForRole("/council", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/council", "normal")).toBe(false);

      expect(isRouteAllowedForRole("/scribe", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/scribe", "admin")).toBe(true);
      expect(isRouteAllowedForRole("/scribe", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/scribe", "normal")).toBe(false);

      // Professional dashboard remains locked to professional roles
      expect(isRouteAllowedForRole("/dashboard", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/dashboard", "researcher")).toBe(true);
      expect(isRouteAllowedForRole("/dashboard", "admin")).toBe(true);
      expect(isRouteAllowedForRole("/dashboard", "normal")).toBe(false);

      // Switching workspace does not mutate server permissions
      const doctorPersonalNav = getWorkspaceNavigation("doctor", "personal");
      expect(doctorPersonalNav.workspace.id).toBe("personal");
      // Even when viewing personal presentation, doctor route authorization is locked:
      expect(isRouteAllowedForRole("/council", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/admin", "doctor")).toBe(false);

      const adminPersonalNav = getWorkspaceNavigation("admin", "personal");
      expect(adminPersonalNav.workspace.id).toBe("personal");
      expect(isRouteAllowedForRole("/admin/overview", "admin")).toBe(true);
      expect(isRouteAllowedForRole("/council", "admin")).toBe(true);
    });
  });
});
