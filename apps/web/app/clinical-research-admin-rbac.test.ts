import { describe, expect, it } from "vitest";
import { isRouteAllowedForRole } from "@/lib/navigation.access";
import {
  ROUTE_LAYOUT_REGISTRY,
  getRouteLayout,
  getRoutesForRole,
  matchRouteLayout,
} from "@/lib/route-layout.registry";
import {
  getAvailableWorkspaces,
  getDefaultWorkspace,
  getWorkspaceForPath,
  isWorkspaceAvailable,
} from "@/lib/navigation.workspaces";

const AUDITED_CLINICAL_AND_RESEARCH_ROUTES = [
  "/evidence",
  "/research/source-hub",
  "/dashboard",
  "/dashboard/control-tower",
  "/dashboard/ecosystem",
  "/council",
  "/council/new",
  "/council/new/intake",
  "/council/new/specialists",
  "/council/new/review",
  "/council/result",
  "/scribe",
  "/clinical",
  "/clinical/overview",
  "/clinical/patients",
];

const CLINICAL_WORKFLOW_ROUTES = [
  "/council",
  "/council/new",
  "/council/new/intake",
  "/council/new/specialists",
  "/council/new/review",
  "/council/result",
  "/scribe",
  "/clinical",
  "/clinical/overview",
  "/clinical/patients",
];

const RESEARCH_WORKFLOW_ROUTES = [
  "/evidence",
  "/research",
  "/research/source-hub",
  "/research/analyze",
  "/research/citations",
  "/research/deepdive",
  "/research/details",
];

const PERSONAL_WORKFLOW_ROUTES = [
  "/home",
  "/ask",
  "/today",
  "/lifemap",
  "/visits",
  "/visits/new",
  "/family",
  "/phr",
  "/medicines",
  "/selfmed",
  "/careguard",
  "/chat",
  "/chat/shares",
  "/health",
  "/care",
  "/you",
  "/huong-dan",
];

const ADMIN_MANAGEMENT_ROUTES = [
  "/admin/overview",
  "/admin/knowledge-sources",
  "/admin/answer-flow",
  "/admin/observability",
  "/admin/analytics",
  "/admin/analytics/clinical",
  "/admin/community-moderation",
  "/admin/dsar",
  "/admin/audit-log",
  "/admin/rag-eval",
  "/admin/rag-ingestion",
  "/dashboard/control-tower",
  "/dashboard/ecosystem",
];

describe("Clinical & Research Pages RBAC Audit (Admin Full Accessibility)", () => {
  describe("1. Audited Clinical & Research Routes Accessibility", () => {
    it.each(AUDITED_CLINICAL_AND_RESEARCH_ROUTES)(
      "verifies Admin role can access %s without restriction",
      (path) => {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);

        const route = getRouteLayout(path) ?? matchRouteLayout(path);
        if (route) {
          expect(route.roles).toContain("admin");
        }
      },
    );
  });

  describe("2. Admin access to Clinical (doctor) workflows", () => {
    it.each(CLINICAL_WORKFLOW_ROUTES)(
      "verifies Admin has unhindered access to Clinical route %s",
      (path) => {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);
        expect(isRouteAllowedForRole(path, "doctor")).toBe(true);
      },
    );

    it("verifies Admin has access to Clinical workspace", () => {
      expect(isWorkspaceAvailable("admin", "clinical")).toBe(true);
      const workspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(workspaces).toContain("clinical");
    });
  });

  describe("3. Admin access to Research (researcher) workflows", () => {
    it.each(RESEARCH_WORKFLOW_ROUTES)(
      "verifies Admin has unhindered access to Research route %s",
      (path) => {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);
      },
    );

    it("verifies Admin has access to Research workspace", () => {
      expect(isWorkspaceAvailable("admin", "research")).toBe(true);
      const workspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(workspaces).toContain("research");
    });
  });

  describe("4. Admin access to Personal (normal) workflows", () => {
    it.each(PERSONAL_WORKFLOW_ROUTES)(
      "verifies Admin has unhindered access to Personal route %s",
      (path) => {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);
      },
    );

    it("verifies Admin has access to Personal workspace", () => {
      expect(isWorkspaceAvailable("admin", "personal")).toBe(true);
      const workspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(workspaces).toContain("personal");
    });
  });

  describe("5. Admin access to System & Admin Management workflows", () => {
    it.each(ADMIN_MANAGEMENT_ROUTES)(
      "verifies Admin has access to Admin route %s",
      (path) => {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);
      },
    );

    it("verifies Admin has access to Admin workspace", () => {
      expect(isWorkspaceAvailable("admin", "admin")).toBe(true);
      const workspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(workspaces).toContain("admin");
    });
  });

  describe("6. Complete 79-Route Registry Admin Invariant", () => {
    it("verifies every registered route includes 'admin' in its roles definition", () => {
      for (const route of ROUTE_LAYOUT_REGISTRY) {
        expect(route.roles).toContain("admin");
        expect(isRouteAllowedForRole(route.path, "admin")).toBe(true);
      }
    });

    it("verifies Admin has all 4 workspaces available simultaneously", () => {
      const workspaces = getAvailableWorkspaces("admin").map((w) => w.id);
      expect(workspaces).toEqual(["personal", "clinical", "research", "admin"]);
    });

    it("verifies workspace routing for Admin resolves seamlessly for any pathway", () => {
      expect(getWorkspaceForPath("/council/new", "admin")).toBe("clinical");
      expect(getWorkspaceForPath("/scribe", "admin")).toBe("clinical");
      expect(getWorkspaceForPath("/evidence", "admin")).toBe("research");
      expect(getWorkspaceForPath("/research/source-hub", "admin")).toBe("research");
      expect(getWorkspaceForPath("/admin/overview", "admin")).toBe("admin");
      expect(getWorkspaceForPath("/today", "admin")).toBe("personal");
    });
  });
});
