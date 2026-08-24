import { describe, expect, it, vi } from "vitest";

const redirect = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirect(path),
}));

describe("LifeMap Visit Prep Canonical Redirect (Spec v5 Section 6.19)", () => {
  it("redirects to canonical /care/prepare with visitId preserved", async () => {
    redirect.mockClear();
    const mod = await import("./page");
    await mod.default({
      searchParams: Promise.resolve({ visitId: "v-123" }),
    });
    expect(redirect).toHaveBeenCalledWith("/care/prepare?visitId=v-123");
  });

  it("redirects to canonical /care/prepare when no visitId is supplied", async () => {
    redirect.mockClear();
    const mod = await import("./page");
    await mod.default({});
    expect(redirect).toHaveBeenCalledWith("/care/prepare");
  });
});
