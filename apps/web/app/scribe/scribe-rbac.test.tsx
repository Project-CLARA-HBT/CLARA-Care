import { describe, expect, it } from "vitest";
import { isRouteAllowedForRole } from "@/lib/navigation.access";
import { getRouteLayout, getRoutesForRole } from "@/lib/route-layout.registry";
import { getAvailableWorkspaces, isWorkspaceAvailable } from "@/lib/navigation.workspaces";

describe("Scribe RBAC & Role Access Verification (/scribe)", () => {
  it("verifies Admin role has full access to /scribe without 403 blocks", () => {
    expect(isRouteAllowedForRole("/scribe", "admin")).toBe(true);

    const layout = getRouteLayout("/scribe");
    expect(layout).toBeDefined();
    expect(layout?.roles).toContain("admin");
    expect(layout?.roles).toContain("doctor");

    const adminRoutes = getRoutesForRole("admin").map((r) => r.path);
    expect(adminRoutes).toContain("/scribe");

    const adminWorkspaces = getAvailableWorkspaces("admin").map((w) => w.id);
    expect(adminWorkspaces).toContain("clinical");
    expect(isWorkspaceAvailable("admin", "clinical")).toBe(true);
  });

  it("verifies Doctor role has access to /scribe", () => {
    expect(isRouteAllowedForRole("/scribe", "doctor")).toBe(true);

    const doctorRoutes = getRoutesForRole("doctor").map((r) => r.path);
    expect(doctorRoutes).toContain("/scribe");

    const doctorWorkspaces = getAvailableWorkspaces("doctor").map((w) => w.id);
    expect(doctorWorkspaces).toContain("clinical");
    expect(isWorkspaceAvailable("doctor", "clinical")).toBe(true);
  });

  it("verifies non-clinical roles (normal, researcher) are restricted from direct /scribe entry", () => {
    expect(isRouteAllowedForRole("/scribe", "normal")).toBe(false);
    expect(isRouteAllowedForRole("/scribe", "researcher")).toBe(false);

    const normalWorkspaces = getAvailableWorkspaces("normal").map((w) => w.id);
    expect(normalWorkspaces).not.toContain("clinical");
    expect(isWorkspaceAvailable("normal", "clinical")).toBe(false);
  });
});
