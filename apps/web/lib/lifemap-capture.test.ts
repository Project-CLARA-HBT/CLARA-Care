import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: { get, post },
}));

import {
  getLifeMapCaptureCapability,
  reviewLifeMapCaptureCandidate,
  startLifeMapTextCapture,
} from "@/lib/lifemap";

describe("LifeMap Universal Capture client", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it("starts text capture and preserves the emergency response", async () => {
    post.mockResolvedValueOnce({
      data: { emergency: true, persisted: false, message: "Escalate" },
    });
    await expect(startLifeMapTextCapture("đau ngực")).resolves.toMatchObject({
      emergency: true,
      persisted: false,
    });
    expect(post).toHaveBeenCalledWith("/lifemap/capture/sessions", {
      text: "đau ngực",
      locale: "vi",
    });
  });

  it("confirms a candidate with an idempotency key", async () => {
    post.mockResolvedValueOnce({
      data: { id: "candidate", status: "confirmed", event_id: "event" },
    });
    await reviewLifeMapCaptureCandidate("candidate", "confirm", {
      reason: "reviewed",
    });
    expect(post).toHaveBeenCalledWith(
      "/lifemap/capture/candidates/candidate/review",
      { action: "confirm", reason: "reviewed" },
      { headers: { "Idempotency-Key": expect.any(String) } },
    );
  });

  it("reads the server-authoritative profile capability", async () => {
    get.mockResolvedValueOnce({
      data: { capabilities: { lifemap_capture: { enabled: true } } },
    });
    await expect(getLifeMapCaptureCapability("profile/id")).resolves.toBe(true);
    expect(get).toHaveBeenCalledWith(
      "/profiles/profile%2Fid/capabilities",
    );
  });
});
