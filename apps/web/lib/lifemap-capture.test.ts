import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: { get, post },
}));

import {
  correctLifeMapEvent,
  getLifeMapCaptureCapability,
  getLifeMapReplay,
  getLifeMapNextQuestion,
  reviewLifeMapCaptureCandidate,
  startLifeMapGuidedAnswer,
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

  it("loads revision-aware replay with an opaque episode id", async () => {
    get.mockResolvedValueOnce({
      data: { episode: { id: "episode/id" }, events: [], tasks: [], decisions: [] },
    });
    await getLifeMapReplay("episode/id");
    expect(get).toHaveBeenCalledWith("/episodes/episode%2Fid/replay");
  });

  it("corrects the exact revision with optimistic concurrency", async () => {
    post.mockResolvedValueOnce({ data: { revision: 3 } });
    await correctLifeMapEvent("event/id", 2, { text: "đúng" }, "sửa");
    expect(post).toHaveBeenCalledWith(
      "/lifemap/events/event%2Fid/correct",
      { payload: { text: "đúng" }, reason: "sửa" },
      {
        headers: {
          "Idempotency-Key": expect.any(String),
          "If-Match": "2",
        },
      },
    );
  });

  it("loads one governed question and routes its answer through Capture", async () => {
    get.mockResolvedValueOnce({
      data: {
        episode_id: "episode-1",
        ask: true,
        question_id: "question-1",
        reason_code: "highest_value_question",
      },
    });
    post.mockResolvedValueOnce({
      data: { id: "session-1", emergency: false, persisted: true },
    });
    await getLifeMapNextQuestion("episode-1");
    await startLifeMapGuidedAnswer(
      "episode-1",
      "question-1",
      { value: "Tốt hơn" },
    );
    expect(get).toHaveBeenCalledWith(
      "/episodes/episode-1/next-question",
      { params: { locale: "vi" } },
    );
    expect(post).toHaveBeenCalledWith("/lifemap/capture/guided-answers", {
      episode_id: "episode-1",
      question_id: "question-1",
      answer: { value: "Tốt hơn" },
      locale: "vi",
    });
  });
});
