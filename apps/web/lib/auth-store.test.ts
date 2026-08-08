import { afterEach, describe, expect, it } from "vitest";
import { getCsrfToken } from "./auth-store";

describe("getCsrfToken", () => {
  afterEach(() => {
    document.cookie = "clara_csrf_token=; Path=/; Max-Age=0";
  });

  it("reads the browser CSRF cookie", () => {
    document.cookie = "clara_csrf_token=active-token; Path=/";
    expect(getCsrfToken()).toBe("active-token");
  });

  it("uses the final duplicate-name value, matching the API cookie parser", () => {
    const descriptor = Object.getOwnPropertyDescriptor(document, "cookie");
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => "clara_csrf_token=stale; clara_csrf_token=fresh",
    });
    try {
      expect(getCsrfToken()).toBe("fresh");
    } finally {
      if (descriptor) Object.defineProperty(document, "cookie", descriptor);
      else delete (document as { cookie?: string }).cookie;
    }
  });
});
