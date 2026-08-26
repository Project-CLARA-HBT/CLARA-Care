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

  it("preserves longitudinal context parameters like episodeId, journey, and source from LifeMap", async () => {
    redirect.mockClear();
    const mod = await import("./page");
    await mod.default({
      searchParams: Promise.resolve({
        episodeId: "ep-456",
        from: "lifemap",
        journey: "hypertension",
      }),
    });
    expect(redirect).toHaveBeenCalledWith(
      "/care/prepare?episodeId=ep-456&from=lifemap&journey=hypertension",
    );
  });

  it("maps visit alias parameter to canonical visitId parameter", async () => {
    redirect.mockClear();
    const mod = await import("./page");
    await mod.default({
      searchParams: Promise.resolve({ visit: "v-789" }),
    });
    expect(redirect).toHaveBeenCalledWith("/care/prepare?visit=v-789&visitId=v-789");
  });
});
