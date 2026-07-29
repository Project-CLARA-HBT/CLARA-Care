import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: { get, post },
}));

import {
  askLifeMap,
  actOnLifeMapReviewFinding,
  correctLifeMapEvent,
  getLifeMapCaptureCapability,
  getLifeMapReplay,
  getLifeMapNextQuestion,
  reviewLifeMapCaptureCandidate,
  scanLifeMapReviewFindings,
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

  it("asks only through the governed LifeMap endpoint", async () => {
    post.mockResolvedValueOnce({
      data: {
        status: "grounded",
        claims: [],
        evidence: [],
        disclosure: { mutates_lifemap: false },
      },
    });
    await askLifeMap("Các ghi nhận gần đây?", "episode/id");
    expect(post).toHaveBeenCalledWith("/lifemap/v2/ask", {
      query: "Các ghi nhận gần đây?",
      episode_id: "episode/id",
      locale: "vi",
    });
  });

  it("scans and resolves review findings through explicit actions", async () => {
    post
      .mockResolvedValueOnce({ data: [{ id: "finding-1", status: "pending" }] })
      .mockResolvedValueOnce({ data: { id: "finding-1", status: "resolved" } });
    await scanLifeMapReviewFindings();
    await actOnLifeMapReviewFinding(
      "finding/id",
      "resolved",
      "Đã kiểm tra nguồn",
    );
    expect(post).toHaveBeenNthCalledWith(
      1,
      "/lifemap/v2/review-findings/scan",
    );
    expect(post).toHaveBeenNthCalledWith(
      2,
      "/lifemap/v2/review-findings/finding%2Fid/actions",
      { action: "resolved", reason: "Đã kiểm tra nguồn" },
      { headers: { "Idempotency-Key": expect.any(String) } },
    );
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
