import { describe, expect, it } from "vitest";

import {
  getNavItemsByRole,
  getRoleHomePath,
  resolvePostLoginPath,
} from "@/lib/navigation.config";

describe("authenticated navigation defaults", () => {
  it("lands every authenticated role on the dashboard instead of chat", () => {
    for (const role of ["normal", "researcher", "doctor", "admin"] as const) {
      expect(getRoleHomePath(role)).toBe("/dashboard");
      expect(resolvePostLoginPath({ role })).toBe("/dashboard");
    }
  });

  it("exposes Research as a first-class destination to every supported role", () => {
    for (const role of ["normal", "researcher", "doctor", "admin"] as const) {
      expect(getNavItemsByRole(role).some((item) => item.href === "/research")).toBe(true);
    }
  });

  it("preserves an explicit safe next destination after login", () => {
    expect(resolvePostLoginPath({ nextPath: "/phr", role: "normal" })).toBe("/phr");
  });
});
