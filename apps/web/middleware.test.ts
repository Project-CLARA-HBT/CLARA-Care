import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware } from "@/middleware";

describe("authentication middleware", () => {
  it("redirects a protected route when no session signal exists", () => {
    const response = middleware(new NextRequest("https://clara.test/dashboard"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://clara.test/login?next=%2Fdashboard",
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
});
