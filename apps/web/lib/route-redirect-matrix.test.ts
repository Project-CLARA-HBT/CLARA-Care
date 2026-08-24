import { describe, expect, it } from "vitest";
import { LEGACY_ROUTE_REDIRECTS } from "@/middleware";
import {
  getRoleHomePath,
  isPublicRoute,
  isRouteAllowedForRole,
  type UserRole,
} from "@/lib/navigation.access";

describe("Route Capability and Redirect Matrix", () => {
  describe("Legacy route redirect mappings", () => {
    const requiredRedirects: Array<[string, string]> = [
      ["/today", "/home"],
      ["/chat", "/ask"],
      ["/lifemap", "/health/timeline"],
      ["/phr", "/health"],
      ["/medicines", "/health/medications"],
      ["/visits", "/care/visits"],
      ["/family", "/you/sharing"],
      ["/account/consent", "/you/privacy"],
      ["/account/data", "/you/privacy"],
    ];

    for (const [legacyRoute, canonicalRoute] of requiredRedirects) {
      it(`maps legacy ${legacyRoute} -> ${canonicalRoute}`, () => {
        expect(LEGACY_ROUTE_REDIRECTS[legacyRoute]).toBe(canonicalRoute);
      });
    }
  });

  describe("Server-side authoritative route authorization", () => {
    const canonicalConsumerRoutes = [
      "/home",
      "/ask",
      "/health",
      "/care",
      "/you",
      "/health/timeline",
      "/health/medications",
      "/care/visits",
      "/you/sharing",
      "/you/privacy",
    ];

    const roles: UserRole[] = ["normal", "researcher", "doctor", "admin"];

    for (const role of roles) {
      it(`allows role '${role}' to access all canonical consumer routes`, () => {
        for (const route of canonicalConsumerRoutes) {
          expect(isRouteAllowedForRole(route, role)).toBe(true);
        }
      });
    }

    it("restricts professional routes to authorized roles only", () => {
      // /dashboard is professional-only
      expect(isRouteAllowedForRole("/dashboard", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/dashboard", "researcher")).toBe(true);
      expect(isRouteAllowedForRole("/dashboard", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/dashboard", "admin")).toBe(true);

      // /council and /scribe are clinical-only
      expect(isRouteAllowedForRole("/council", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/council", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/council", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/council", "admin")).toBe(true);

      expect(isRouteAllowedForRole("/scribe", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/scribe", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/scribe", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/scribe", "admin")).toBe(true);

      // /admin is admin-only
      expect(isRouteAllowedForRole("/admin/overview", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/admin/overview", "researcher")).toBe(false);
      expect(isRouteAllowedForRole("/admin/overview", "doctor")).toBe(false);
      expect(isRouteAllowedForRole("/admin/overview", "admin")).toBe(true);
    });

    it("verifies default home paths for each role", () => {
      expect(getRoleHomePath("normal")).toBe("/home");
      expect(getRoleHomePath("researcher")).toBe("/dashboard");
      expect(getRoleHomePath("doctor")).toBe("/dashboard");
      expect(getRoleHomePath("admin")).toBe("/dashboard");
    });

    it("verifies public and share routes are public without auth requirement", () => {
      expect(isPublicRoute("/")).toBe(true);
      expect(isPublicRoute("/login")).toBe(true);
      expect(isPublicRoute("/register")).toBe(true);
      expect(isPublicRoute("/legal")).toBe(true);
      expect(isPublicRoute("/share/some-token-123")).toBe(true);
      expect(isPublicRoute("/chat/share/some-chat-token-789")).toBe(true);
      expect(isPublicRoute("/phr/shared/some-phr-token-456")).toBe(true);

      expect(isPublicRoute("/home")).toBe(false);
      expect(isPublicRoute("/health")).toBe(false);
      expect(isPublicRoute("/dashboard")).toBe(false);
    });
  });
});
