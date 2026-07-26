import { describe, expect, it, vi } from "vitest";

/**
 * Feature: clara-ui-ux-redesign — medicines consolidation (Req 2.2, 2.3).
 *
 * The three legacy medication surfaces (`/selfmed`, `/selfmed/ddi`, `/careguard`)
 * must be thin redirect stubs into the correct tab of the unified `/medicines`
 * hub, so there is exactly one medication destination and no duplicate surface.
 */

const redirect = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirect(path),
}));

describe("medicines consolidation redirects", () => {
  it("routes /selfmed to the cabinet tab", async () => {
    redirect.mockClear();
    const mod = await import("./../selfmed/page");
    mod.default();
    expect(redirect).toHaveBeenCalledWith("/medicines?tab=cabinet");
  });

  it("routes /selfmed/ddi to the safety tab", async () => {
    redirect.mockClear();
    const mod = await import("./../selfmed/ddi/page");
    mod.default();
    expect(redirect).toHaveBeenCalledWith("/medicines?tab=safety");
  });

  it("routes /careguard to the safety tab", async () => {
    redirect.mockClear();
    const mod = await import("./../careguard/page");
    mod.default();
    expect(redirect).toHaveBeenCalledWith("/medicines?tab=safety");
  });
});
