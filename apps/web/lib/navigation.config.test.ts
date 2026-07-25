import { describe, expect, it } from "vitest";

import {
  getNavItemsByRole,
  getRoleHomePath,
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
});
