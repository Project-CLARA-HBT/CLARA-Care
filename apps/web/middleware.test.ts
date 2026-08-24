import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware, LEGACY_ROUTE_REDIRECTS } from "@/middleware";

describe("authentication middleware", () => {
  it("redirects a protected route when no session signal exists", () => {
    const response = middleware(
      new NextRequest("https://clara.test/dashboard"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://clara.test/login?next=%2Fdashboard",
    );
  });

  it("redirects legacy routes to canonical targets in next param when unauthenticated", () => {
    const response = middleware(
      new NextRequest("https://clara.test/ask?view=calendar"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://clara.test/login?next=%2Fchat%3Fview%3Dcalendar",
    );
  });

  it("lets the client session hint reach AppShell for authoritative validation", () => {
    const request = new NextRequest("https://clara.test/dashboard", {
      headers: { cookie: "clara_client_session=1" },
    });
    const response = middleware(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("always leaves the login form reachable even with a session hint", () => {
    const request = new NextRequest("https://clara.test/login", {
      headers: { cookie: "clara_client_session=1" },
    });
    const response = middleware(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("leaves opaque public share routes reachable without a session", () => {
    for (const path of [
      "https://theclaracare.com/share/opaque-token",
      "https://theclaracare.com/chat/share/opaque-token",
      "https://theclaracare.com/phr/shared/opaque-token",
    ]) {
      const response = middleware(new NextRequest(path));
      expect(response.status).toBe(200);
      expect(response.headers.get("location")).toBeNull();
    }
  });

  describe("legacy route compatibility redirects when authenticated", () => {
    const testCases: Array<[string, string]> = [
      ["/ask", "/chat"],
      ["/health/medications", "/medicines"],
      ["/care/visits", "/visits"],
      ["/health/timeline", "/lifemap"],
      ["/health", "/phr"],
      ["/selfmed", "/medicines"],
      ["/careguard", "/medicines"],
      ["/admin/rag-sources", "/admin/knowledge-sources"],
      ["/admin/source-hub", "/admin/knowledge-sources"],
      ["/lifemap/visit-prep", "/care/prepare"],
      ["/role-select", "/dashboard"],
    ];

    for (const [legacyPath, canonicalPath] of testCases) {
      it(`redirects ${legacyPath} -> ${canonicalPath} while preserving query params`, () => {
        const request = new NextRequest(
          `https://clara.test${legacyPath}?tab=details&filter=active`,
          {
            headers: { cookie: "clara_client_session=1" },
          },
        );
        const response = middleware(request);

        expect(response.status).toBe(307);
        expect(response.headers.get("location")).toBe(
          `https://clara.test${canonicalPath}?tab=details&filter=active`,
        );
      });
    }

    it("verifies all expected legacy routes are in the redirect dictionary", () => {
      expect(LEGACY_ROUTE_REDIRECTS).toEqual({
        "/ask": "/chat",
        "/health/medications": "/medicines",
        "/care/visits": "/visits",
        "/health/timeline": "/lifemap",
        "/health": "/phr",
        "/selfmed": "/medicines",
        "/careguard": "/medicines",
        "/admin/rag-sources": "/admin/knowledge-sources",
        "/admin/source-hub": "/admin/knowledge-sources",
        "/lifemap/visit-prep": "/care/prepare",
        "/role-select": "/dashboard",
      });
    });
  });
});
