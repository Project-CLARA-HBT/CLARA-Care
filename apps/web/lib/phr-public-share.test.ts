import { describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("@/lib/http-client", () => ({ default: { get } }));

describe("public PHR share client", () => {
  it("encodes the opaque capability token in the public read-only request", async () => {
    get.mockResolvedValueOnce({ data: { scope: "full", record: {} } });
    const { getPublicPhrShare } = await import("@/lib/phr");

    await expect(getPublicPhrShare("opaque/token")).resolves.toEqual({
      scope: "full",
      record: {},
    });
    expect(get).toHaveBeenCalledWith("/api/v1/phr/shared/opaque%2Ftoken");
  });
});
