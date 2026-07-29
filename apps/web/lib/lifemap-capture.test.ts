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
  disputeLifeMapEvent,
  getLifeMapCaptureCapability,
  getLifeMapCaptureArtifact,
  getActiveLifeMapCaptureSession,
  getLifeMapCaptureNormalization,
  getLifeMapCaptureSession,
  getLifeMapDisputes,
  getLifeMapReplay,
  getLifeMapSummary,
  getLifeMapNextQuestion,
  reviewLifeMapCaptureCandidate,
  scanLifeMapReviewFindings,
  resolveLifeMapEvent,
  abandonLifeMapCaptureSession,
  startLifeMapArtifactCapture,
  startLifeMapGuidedAnswer,
  startLifeMapTextCapture,
  uploadLifeMapCaptureArtifact,
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

  it("starts, uploads, resumes, previews, and abandons an artifact draft", async () => {
    post
      .mockResolvedValueOnce({
        data: { id: "session/id", emergency: false, persisted: true },
      })
      .mockResolvedValueOnce({
        data: { id: "artifact/id", job: { id: "job/id", status: "queued" } },
      })
      .mockResolvedValueOnce({ data: { id: "session/id", status: "abandoned" } });
    get
      .mockResolvedValueOnce({
        data: { id: "session/id", status: "draft", candidates: [] },
      })
      .mockResolvedValueOnce({ data: { session: null } })
      .mockResolvedValueOnce({ data: new Blob(["source"]) });

    const session = await startLifeMapArtifactCapture("medication_label");
    const file = new File(["image"], "label.png", { type: "image/png" });
    await uploadLifeMapCaptureArtifact(String(session.id), file);
    await getLifeMapCaptureSession("session/id");
    await getActiveLifeMapCaptureSession();
    await getLifeMapCaptureArtifact({
      id: "artifact/id",
      media_type: "image/png",
      filename: "label.png",
      checksum: "checksum",
      access_token: "short-lived",
      access_expires_at: "2026-07-29T00:00:00Z",
    });
    await abandonLifeMapCaptureSession("session/id");

    expect(post).toHaveBeenNthCalledWith(
      1,
      "/lifemap/capture/artifact-sessions",
      { input_kind: "medication_label", locale: "vi" },
    );
    expect(post.mock.calls[1][0]).toBe(
      "/lifemap/capture/sessions/session%2Fid/artifacts",
    );
    expect(post.mock.calls[1][1]).toBeInstanceOf(FormData);
    expect(get).toHaveBeenNthCalledWith(
      1,
      "/lifemap/capture/sessions/session%2Fid",
    );
    expect(get).toHaveBeenNthCalledWith(
      2,
      "/lifemap/capture/active-session",
    );
    expect(get).toHaveBeenNthCalledWith(
      3,
      "/lifemap/capture/artifacts/artifact%2Fid/content",
      {
        headers: { "X-Capture-Artifact-Token": "short-lived" },
        responseType: "blob",
      },
    );
    expect(post).toHaveBeenNthCalledWith(
      3,
      "/lifemap/capture/sessions/session%2Fid/abandon",
    );
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
      accept_normalization: true,
    });
    expect(post).toHaveBeenCalledWith(
      "/lifemap/capture/candidates/candidate/review",
      {
        action: "confirm",
        reason: "reviewed",
        accept_normalization: true,
      },
      { headers: { "Idempotency-Key": expect.any(String) } },
    );
  });

  it("reads a server-owned medication normalization proposal", async () => {
    get.mockResolvedValueOnce({
      data: {
        candidate_id: "candidate/id",
        status: "candidate",
        proposal: { system: "rxnorm", code: "161" },
        auto_confirmable: false,
      },
    });
    await getLifeMapCaptureNormalization("candidate/id");
    expect(get).toHaveBeenCalledWith(
      "/lifemap/capture/candidates/candidate%2Fid/normalization",
    );
  });

  it("loads an episode summary with exact server-side scoping", async () => {
    get.mockResolvedValueOnce({
      data: {
        id: "summary",
        level: "episode",
        status: "ready",
        children: [],
      },
    });
    await getLifeMapSummary("episode", "episode/id");
    expect(get).toHaveBeenCalledWith("/lifemap/v2/summaries/episode", {
      params: { locale: "vi", episode_id: "episode/id" },
    });
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

  it("uses typed event dispute and resolution commands", async () => {
    get.mockResolvedValueOnce({ data: [] });
    await getLifeMapDisputes();
    expect(get).toHaveBeenCalledWith("/lifemap/v2/disputes");

    await disputeLifeMapEvent("event/id", 2, "nguồn chưa rõ");
    expect(post).toHaveBeenCalledWith(
      "/lifemap/events/event%2Fid/dispute",
      { reason: "nguồn chưa rõ" },
      {
        headers: {
          "Idempotency-Key": expect.any(String),
          "If-Match": "2",
        },
      },
    );

    await resolveLifeMapEvent("event/id", 3, "đã kiểm tra");
    expect(post).toHaveBeenCalledWith(
      "/lifemap/events/event%2Fid/resolve",
      { reason: "đã kiểm tra" },
      {
        headers: {
          "Idempotency-Key": expect.any(String),
          "If-Match": "3",
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
