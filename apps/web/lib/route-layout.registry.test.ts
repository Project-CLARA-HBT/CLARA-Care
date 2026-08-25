import { readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  ROUTE_LAYOUT_BY_ID,
  ROUTE_LAYOUT_BY_PATH,
  ROUTE_LAYOUT_REGISTRY,
  getRouteLayout,
  getRouteLayoutById,
  getRoutesByAccess,
  getRoutesByExperience,
  getRoutesByShellMode,
  getRoutesForRole,
  isAliasRoute,
  matchRouteLayout,
} from "./route-layout.registry";
import type {
  CanonicalExperience,
  RouteAccessCategory,
  RouteLayoutContract,
  ShellMode,
  UserRole,
} from "./route-layout.contract";

const VALID_ACCESS: RouteAccessCategory[] = [
  "public",
  "personal",
  "clinical",
  "research",
  "admin",
  "utility",
];

const VALID_EXPERIENCES: CanonicalExperience[] = [
  "personal",
  "clinical",
  "research",
  "admin",
  "public",
  "utility",
];

const VALID_SHELL_MODES: ShellMode[] = [
  "PUBLIC_MARKETING",
  "PUBLIC_AUTH",
  "PUBLIC_LEGAL",
  "PUBLIC_SHARE",
  "EXPLORE",
  "FOCUS",
  "IMMERSIVE",
  "READ",
  "READ_COMPOSE",
  "DENSE",
  "ADMIN_COMMAND",
  "ROLE_ADAPTER",
  "UTILITY_FOCUS",
  "ALIAS_REDIRECT",
  "ALIAS_CONTEXT",
];

const VALID_ROLES: UserRole[] = ["normal", "researcher", "doctor", "admin"];

function scanAppPageRoutes(dir: string, baseDir: string = dir): string[] {
  const entries = readdirSync(dir, { withFileTypes: true });
  const routes: string[] = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      routes.push(...scanAppPageRoutes(fullPath, baseDir));
    } else if (entry.name === "page.tsx") {
      const rel = relative(baseDir, fullPath).replaceAll("\\", "/");
      const dirName = rel.endsWith("/page.tsx")
        ? rel.slice(0, -"/page.tsx".length)
        : rel === "page.tsx"
          ? ""
          : rel;
      const segments = dirName
        ? dirName.split("/").filter((s) => !/^\(.*\)$/.test(s))
        : [];
      routes.push("/" + segments.join("/"));
    }
  }
  return routes.sort();
}

describe("RouteLayoutRegistry", () => {
  const appDirectory = resolve(__dirname, "../app");
  const filesystemRoutes = scanAppPageRoutes(appDirectory);
  const filesystemRouteSet = new Set(filesystemRoutes);

  describe("Dynamic filesystem coverage & structural integrity", () => {
    it("achieves 100% dynamic filesystem route coverage without missing or extra routes", () => {
      expect(filesystemRoutes.length).toBeGreaterThan(0);
      expect(ROUTE_LAYOUT_REGISTRY).toHaveLength(filesystemRoutes.length);

      const missingFromRegistry = filesystemRoutes.filter(
        (route) => !ROUTE_LAYOUT_BY_PATH[route],
      );
      expect(missingFromRegistry).toEqual([]);

      const extraInRegistry = ROUTE_LAYOUT_REGISTRY.map((r) => r.path).filter(
        (path) => !filesystemRouteSet.has(path),
      );
      expect(extraInRegistry).toEqual([]);
    });

    it("has unique routeIds across all registered routes", () => {
      const routeIds = ROUTE_LAYOUT_REGISTRY.map((r) => r.routeId);
      const uniqueRouteIds = new Set(routeIds);
      expect(uniqueRouteIds.size).toBe(ROUTE_LAYOUT_REGISTRY.length);
    });

    it("has unique paths across all registered routes", () => {
      const paths = ROUTE_LAYOUT_REGISTRY.map((r) => r.path);
      const uniquePaths = new Set(paths);
      expect(uniquePaths.size).toBe(ROUTE_LAYOUT_REGISTRY.length);
    });

    it("ensures every route conforms strictly to RouteLayoutContract", () => {
      for (const route of ROUTE_LAYOUT_REGISTRY) {
        expect(route.routeId).toBeTypeOf("string");
        expect(route.routeId.trim().length).toBeGreaterThan(0);

        expect(route.path).toBeTypeOf("string");
        expect(route.path.startsWith("/")).toBe(true);

        expect(VALID_ACCESS).toContain(route.access);
        expect(VALID_EXPERIENCES).toContain(route.canonicalExperience);
        expect(VALID_SHELL_MODES).toContain(route.shellMode);

        expect(Array.isArray(route.roles)).toBe(true);
        expect(route.roles.length).toBeGreaterThan(0);
        for (const role of route.roles) {
          expect(VALID_ROLES).toContain(role);
        }

        expect(route.layoutArchetype).toBeTypeOf("string");
        expect(route.layoutArchetype.trim().length).toBeGreaterThan(0);

        if (route.shellMode === "ALIAS_REDIRECT" || route.shellMode === "ALIAS_CONTEXT") {
          expect(route.targetPath).toBeTypeOf("string");
          expect(route.targetPath?.startsWith("/")).toBe(true);
        }
      }
    });

    it("ensures indexed lookups match registry entries", () => {
      expect(Object.keys(ROUTE_LAYOUT_BY_PATH)).toHaveLength(ROUTE_LAYOUT_REGISTRY.length);
      expect(Object.keys(ROUTE_LAYOUT_BY_ID)).toHaveLength(ROUTE_LAYOUT_REGISTRY.length);

      for (const route of ROUTE_LAYOUT_REGISTRY) {
        expect(ROUTE_LAYOUT_BY_PATH[route.path]).toBe(route);
        expect(ROUTE_LAYOUT_BY_ID[route.routeId]).toBe(route);
      }
    });
  });

  describe("Spec v5 Section 5 conformance mapping", () => {
    const EXPECTED_SPEC_ROUTES: Array<{
      num: number;
      path: string;
      shellMode: ShellMode;
      layoutArchetype: string;
    }> = [
      { num: 1, path: "/", shellMode: "PUBLIC_MARKETING", layoutArchetype: "Brand Story" },
      { num: 2, path: "/login", shellMode: "PUBLIC_AUTH", layoutArchetype: "Auth Focus" },
      { num: 3, path: "/register", shellMode: "PUBLIC_AUTH", layoutArchetype: "Auth Focus" },
      { num: 4, path: "/forgot-password", shellMode: "PUBLIC_AUTH", layoutArchetype: "Recovery Focus" },
      { num: 5, path: "/reset-password", shellMode: "PUBLIC_AUTH", layoutArchetype: "Recovery Focus" },
      { num: 6, path: "/verify-email", shellMode: "PUBLIC_AUTH", layoutArchetype: "Verification Status" },
      { num: 7, path: "/legal", shellMode: "PUBLIC_LEGAL", layoutArchetype: "Legal Index" },
      { num: 8, path: "/legal/consent", shellMode: "PUBLIC_LEGAL", layoutArchetype: "Legal Reader" },
      { num: 9, path: "/legal/cookies", shellMode: "PUBLIC_LEGAL", layoutArchetype: "Legal Reader" },
      { num: 10, path: "/legal/privacy", shellMode: "PUBLIC_LEGAL", layoutArchetype: "Legal Reader" },
      { num: 11, path: "/legal/terms", shellMode: "PUBLIC_LEGAL", layoutArchetype: "Legal Reader" },
      { num: 12, path: "/share/[token]", shellMode: "PUBLIC_SHARE", layoutArchetype: "Shared Content Reader" },
      { num: 13, path: "/phr/shared/[token]", shellMode: "PUBLIC_SHARE", layoutArchetype: "Bounded Record Reader" },
      { num: 14, path: "/today", shellMode: "EXPLORE", layoutArchetype: "Next-Action Canvas" },
      { num: 15, path: "/today/tasks/[taskId]", shellMode: "FOCUS", layoutArchetype: "Task Detail" },
      { num: 16, path: "/lifemap", shellMode: "EXPLORE", layoutArchetype: "Journey Canvas" },
      { num: 17, path: "/lifemap/new", shellMode: "FOCUS", layoutArchetype: "Journey Entry" },
      { num: 18, path: "/lifemap/new/[draftId]/[step]", shellMode: "FOCUS", layoutArchetype: "Journey Stepper" },
      { num: 19, path: "/lifemap/visit-prep", shellMode: "ALIAS_CONTEXT", layoutArchetype: "Canonical Redirect" },
      { num: 20, path: "/visits", shellMode: "EXPLORE", layoutArchetype: "Visit Timeline" },
      { num: 21, path: "/visits/new", shellMode: "FOCUS", layoutArchetype: "Visit Prep Wizard" },
      { num: 22, path: "/family", shellMode: "EXPLORE", layoutArchetype: "Sharing Hub" },
      { num: 23, path: "/family/invite", shellMode: "FOCUS", layoutArchetype: "Invite Wizard" },
      { num: 24, path: "/family/accept", shellMode: "FOCUS", layoutArchetype: "Scope Review" },
      { num: 25, path: "/phr", shellMode: "FOCUS", layoutArchetype: "Health Record Workbench" },
      { num: 26, path: "/phr/[section]", shellMode: "FOCUS", layoutArchetype: "Record Section Editor" },
      { num: 27, path: "/medicines", shellMode: "EXPLORE", layoutArchetype: "Medicines Safety Workspace" },
      { num: 28, path: "/medicines/add", shellMode: "FOCUS", layoutArchetype: "Medication Wizard" },
      { num: 29, path: "/medicines/cabinet/add", shellMode: "FOCUS", layoutArchetype: "Cabinet Wizard" },
      { num: 30, path: "/selfmed", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 31, path: "/selfmed/add", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 32, path: "/selfmed/ddi", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 33, path: "/careguard", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 34, path: "/chat", shellMode: "READ_COMPOSE", layoutArchetype: "Editorial AI Workspace" },
      { num: 35, path: "/chat/shares", shellMode: "EXPLORE", layoutArchetype: "Shared Conversations Library" },
      { num: 36, path: "/evidence", shellMode: "READ", layoutArchetype: "Evidence Synthesis" },
      { num: 37, path: "/research", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 38, path: "/research/analyze", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 39, path: "/research/citations", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 40, path: "/research/deepdive", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 41, path: "/research/details", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 42, path: "/research/source-hub", shellMode: "DENSE", layoutArchetype: "Source Workbench" },
      { num: 43, path: "/council", shellMode: "EXPLORE", layoutArchetype: "Case Library" },
      { num: 44, path: "/council/new", shellMode: "FOCUS", layoutArchetype: "Council Entry" },
      { num: 45, path: "/council/new/intake", shellMode: "FOCUS", layoutArchetype: "Case Intake" },
      { num: 46, path: "/council/new/specialists", shellMode: "FOCUS", layoutArchetype: "Specialist Selection" },
      { num: 47, path: "/council/new/review", shellMode: "FOCUS", layoutArchetype: "Preflight Review" },
      { num: 48, path: "/council/result", shellMode: "READ", layoutArchetype: "Decision Review" },
      { num: 49, path: "/council/analyze", shellMode: "READ", layoutArchetype: "Analysis Focus" },
      { num: 50, path: "/council/citations", shellMode: "READ", layoutArchetype: "Citation Focus" },
      { num: 51, path: "/council/deepdive", shellMode: "READ", layoutArchetype: "Expert Deep Dive" },
      { num: 52, path: "/council/details", shellMode: "READ", layoutArchetype: "Technical Detail" },
      { num: 53, path: "/council/research", shellMode: "READ", layoutArchetype: "Evidence Focus" },
      { num: 54, path: "/scribe", shellMode: "IMMERSIVE", layoutArchetype: "Scribe State Machine" },
      { num: 55, path: "/dashboard", shellMode: "ROLE_ADAPTER", layoutArchetype: "Role-Adaptive Home" },
      { num: 56, path: "/dashboard/control-tower", shellMode: "DENSE", layoutArchetype: "System Topology Workbench" },
      { num: 57, path: "/dashboard/ecosystem", shellMode: "DENSE", layoutArchetype: "Integration Workbench" },
      { num: 58, path: "/admin", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 59, path: "/admin/overview", shellMode: "ADMIN_COMMAND", layoutArchetype: "Operations Overview" },
      { num: 60, path: "/admin/knowledge-sources", shellMode: "ADMIN_COMMAND", layoutArchetype: "Knowledge Registry" },
      { num: 61, path: "/admin/answer-flow", shellMode: "ADMIN_COMMAND", layoutArchetype: "Answer Flow Explorer" },
      { num: 62, path: "/admin/observability", shellMode: "ADMIN_COMMAND", layoutArchetype: "Observability Cockpit" },
      { num: 63, path: "/admin/analytics", shellMode: "ADMIN_COMMAND", layoutArchetype: "Product Analytics Report" },
      { num: 64, path: "/admin/analytics/clinical", shellMode: "ADMIN_COMMAND", layoutArchetype: "Clinical Analytics Report" },
      { num: 65, path: "/admin/community-moderation", shellMode: "ADMIN_COMMAND", layoutArchetype: "Moderation Workbench" },
      { num: 66, path: "/admin/dsar", shellMode: "ADMIN_COMMAND", layoutArchetype: "DSAR Workbench" },
      { num: 67, path: "/admin/audit-log", shellMode: "ADMIN_COMMAND", layoutArchetype: "Audit Ledger" },
      { num: 68, path: "/admin/rag-eval", shellMode: "ADMIN_COMMAND", layoutArchetype: "RAG Evaluation Workbench" },
      { num: 69, path: "/admin/rag-ingestion", shellMode: "ADMIN_COMMAND", layoutArchetype: "Ingestion Monitor" },
      { num: 70, path: "/admin/rag-sources", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 71, path: "/admin/source-hub", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 72, path: "/community", shellMode: "EXPLORE", layoutArchetype: "Community Feed" },
      { num: 73, path: "/huong-dan", shellMode: "READ", layoutArchetype: "Help Library" },
      { num: 74, path: "/welcome", shellMode: "UTILITY_FOCUS", layoutArchetype: "Onboarding Router" },
      { num: 75, path: "/welcome/[step]", shellMode: "UTILITY_FOCUS", layoutArchetype: "Role-Aware Onboarding" },
      { num: 76, path: "/role-select", shellMode: "ALIAS_REDIRECT", layoutArchetype: "Redirect" },
      { num: 77, path: "/account/consent", shellMode: "FOCUS", layoutArchetype: "Consent Ledger" },
      { num: 78, path: "/account/data", shellMode: "FOCUS", layoutArchetype: "Data Rights Center" },
      { num: 79, path: "/account/data/delete/[step]", shellMode: "UTILITY_FOCUS", layoutArchetype: "Deletion Confirmation" },
    ];

    it("verifies all 79 Spec v5 Section 5 routes conform to specification", () => {
      for (const spec of EXPECTED_SPEC_ROUTES) {
        const registered = ROUTE_LAYOUT_BY_PATH[spec.path];
        expect(registered).toBeDefined();
        expect(registered.path).toBe(spec.path);
        expect(registered.shellMode).toBe(spec.shellMode);
        expect(registered.layoutArchetype).toBe(spec.layoutArchetype);
      }
    });
  });

  describe("Lookup helpers", () => {
    it("retrieves route layout by path", () => {
      const todayRoute = getRouteLayout("/today");
      expect(todayRoute).toBeDefined();
      expect(todayRoute?.routeId).toBe("personal-today");
      expect(todayRoute?.shellMode).toBe("EXPLORE");

      const unknownRoute = getRouteLayout("/not-a-valid-route");
      expect(unknownRoute).toBeUndefined();
    });

    it("retrieves route layout by id", () => {
      const councilRoute = getRouteLayoutById("clinical-council");
      expect(councilRoute).toBeDefined();
      expect(councilRoute?.path).toBe("/council");
      expect(councilRoute?.shellMode).toBe("EXPLORE");

      const unknownId = getRouteLayoutById("unknown-route-id");
      expect(unknownId).toBeUndefined();
    });

    it("matches static routes accurately", () => {
      expect(matchRouteLayout("/")?.routeId).toBe("public-landing");
      expect(matchRouteLayout("/today")?.routeId).toBe("personal-today");
      expect(matchRouteLayout("/home")?.routeId).toBe("personal-home");
      expect(matchRouteLayout("/ask")?.routeId).toBe("personal-ask");
      expect(matchRouteLayout("/care")?.routeId).toBe("personal-care");
      expect(matchRouteLayout("/admin/overview")?.routeId).toBe("admin-overview");
    });

    it("matches dynamic parameterized routes accurately", () => {
      expect(matchRouteLayout("/share/token-xyz-123")?.routeId).toBe("public-share-token");
      expect(matchRouteLayout("/chat/share/token-share-456")?.routeId).toBe("public-chat-share-token");
      expect(matchRouteLayout("/phr/shared/token-phr-456")?.routeId).toBe("public-phr-shared-token");
      expect(matchRouteLayout("/today/tasks/task-99")?.routeId).toBe("personal-today-task-detail");
      expect(matchRouteLayout("/lifemap/new/draft-123/goal")?.routeId).toBe("personal-lifemap-stepper");
      expect(matchRouteLayout("/phr/medications")?.routeId).toBe("personal-phr-section");
      expect(matchRouteLayout("/welcome/step-profile")?.routeId).toBe("utility-welcome-step");
      expect(matchRouteLayout("/account/data/delete/confirm")?.routeId).toBe("account-data-delete-step");
      expect(matchRouteLayout("/visits/visit-789")?.routeId).toBe("personal-visits-detail");
      expect(matchRouteLayout("/medicines/med-abc")?.routeId).toBe("personal-medicines-detail");
      expect(matchRouteLayout("/chat/session-def")?.routeId).toBe("chat-session-detail");

      expect(matchRouteLayout("/unknown/deep/nested/path/not/found")).toBeUndefined();
    });
  });

  describe("Filtering & categorization helpers", () => {
    it("identifies alias routes correctly", () => {
      const aliasRoutes = ROUTE_LAYOUT_REGISTRY.filter(isAliasRoute);
      expect(aliasRoutes.length).toBe(16); // 15 ALIAS_REDIRECT + 1 ALIAS_CONTEXT
      for (const route of aliasRoutes) {
        expect(route.targetPath).toBeDefined();
        expect(route.targetPath?.length).toBeGreaterThan(0);
      }
    });

    it("filters routes by canonical experience", () => {
      const personalRoutes = getRoutesByExperience("personal");
      const clinicalRoutes = getRoutesByExperience("clinical");
      const researchRoutes = getRoutesByExperience("research");
      const adminRoutes = getRoutesByExperience("admin");
      const publicRoutes = getRoutesByExperience("public");
      const utilityRoutes = getRoutesByExperience("utility");

      const totalGrouped =
        personalRoutes.length +
        clinicalRoutes.length +
        researchRoutes.length +
        adminRoutes.length +
        publicRoutes.length +
        utilityRoutes.length;

      expect(totalGrouped).toBe(ROUTE_LAYOUT_REGISTRY.length);
      expect(publicRoutes).toHaveLength(23);
      expect(personalRoutes).toHaveLength(49);
      expect(clinicalRoutes).toHaveLength(17);
      expect(researchRoutes).toHaveLength(7);
      expect(adminRoutes).toHaveLength(21);
      expect(utilityRoutes).toHaveLength(6);
    });

    it("filters routes by shell mode", () => {
      const adminCommandRoutes = getRoutesByShellMode("ADMIN_COMMAND");
      expect(adminCommandRoutes.length).toBeGreaterThan(0);
      for (const r of adminCommandRoutes) {
        expect(r.shellMode).toBe("ADMIN_COMMAND");
      }

      const exploreRoutes = getRoutesByShellMode("EXPLORE");
      expect(exploreRoutes.length).toBeGreaterThan(0);
      for (const r of exploreRoutes) {
        expect(r.shellMode).toBe("EXPLORE");
      }
    });

    it("filters routes by access category", () => {
      const publicAccess = getRoutesByAccess("public");
      expect(publicAccess).toHaveLength(23);

      const personalAccess = getRoutesByAccess("personal");
      expect(personalAccess).toHaveLength(49);

      const clinicalAccess = getRoutesByAccess("clinical");
      expect(clinicalAccess).toHaveLength(17);

      const researchAccess = getRoutesByAccess("research");
      expect(researchAccess).toHaveLength(7);

      const adminAccess = getRoutesByAccess("admin");
      expect(adminAccess).toHaveLength(21);

      const utilityAccess = getRoutesByAccess("utility");
      expect(utilityAccess).toHaveLength(6);
    });

    it("filters routes by user role correctly", () => {
      const adminRoutes = getRoutesForRole("admin");
      expect(adminRoutes).toHaveLength(ROUTE_LAYOUT_REGISTRY.length); // Admin has access to all routes

      const normalRoutes = getRoutesForRole("normal");
      const adminOnlyPaths = getRoutesByAccess("admin").map((r) => r.path);
      for (const normalRoute of normalRoutes) {
        expect(adminOnlyPaths).not.toContain(normalRoute.path);
      }

      const doctorRoutes = getRoutesForRole("doctor");
      const councilRoute = doctorRoutes.find((r) => r.path === "/council");
      expect(councilRoute).toBeDefined();
    });
  });

  describe("Fast-check property-based verification", () => {
    it("consistently resolves every registered contract by path and id", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(...ROUTE_LAYOUT_REGISTRY),
          (contract: RouteLayoutContract) => {
            const byPath = getRouteLayout(contract.path);
            const byId = getRouteLayoutById(contract.routeId);
            const matched = matchRouteLayout(contract.path);

            expect(byPath).toBe(contract);
            expect(byId).toBe(contract);
            expect(matched).toBe(contract);
          },
        ),
      );
    });
  });
});
