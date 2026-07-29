import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({ default: mocks }));

import {
  commitLifeMapEpisodeDraft,
  createLifeMapEpisodeDraft,
  listLifeMapEpisodeDrafts,
  updateLifeMapEpisodeDraft,
} from "@/lib/guided-flows";

describe("guided-flow API client", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists only resumable LifeMap episode drafts", async () => {
    mocks.get.mockResolvedValue({ data: { items: [] } });
    await expect(listLifeMapEpisodeDrafts()).resolves.toEqual([]);
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/guided-flows", {
      params: { flow_type: "lifemap_episode" },
    });
  });

  it("creates a server-owned empty draft with an idempotency key", async () => {
    mocks.post.mockResolvedValue({ data: { id: "draft-1" } });
    await createLifeMapEpisodeDraft("create-key-123");
    expect(mocks.post).toHaveBeenCalledWith(
      "/api/v1/guided-flows",
      {
        flow_type: "lifemap_episode",
        current_step: "title",
        payload: {},
      },
      { headers: { "Idempotency-Key": "create-key-123" } },
    );
  });

  it("uses revision preconditions for updates and idempotent commit", async () => {
    mocks.patch.mockResolvedValue({ data: { revision: 5 } });
    await updateLifeMapEpisodeDraft("draft/1", 4, "goal", { title: "Sleep" });
    expect(mocks.patch).toHaveBeenCalledWith(
      "/api/v1/guided-flows/draft%2F1",
      { current_step: "goal", payload: { title: "Sleep" } },
      { headers: { "If-Match": "\"4\"" } },
    );

    mocks.post.mockResolvedValue({ data: { status: "committed" } });
    await commitLifeMapEpisodeDraft("draft-1", 5, "commit-key-123");
    expect(mocks.post).toHaveBeenLastCalledWith(
      "/api/v1/guided-flows/draft-1/commit",
      {},
      {
        headers: {
          "Idempotency-Key": "commit-key-123",
          "If-Match": "\"5\"",
        },
      },
    );
  });
});
