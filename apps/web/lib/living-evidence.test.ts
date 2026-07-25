import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({ default: api }));

import {
  confirmEvidenceQuestion,
  createEvidenceQuestion,
  getEvidenceDetails,
  getEvidenceRun,
  pollEvidenceRun,
  runEvidenceQuestion,
} from "@/lib/living-evidence";

describe("living evidence API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates an unconfirmed question tied to the selected LifeMap episode", async () => {
    api.post.mockResolvedValue({ data: { id: "q-1" } });

    await createEvidenceQuestion("episode-1", {
      question: "Có bằng chứng nào về huyết áp?",
      outcomes: ["huyết áp"],
    });

    expect(api.post).toHaveBeenCalledWith(
      "/episodes/episode-1/evidence-questions",
      expect.objectContaining({
        question: "Có bằng chứng nào về huyết áp?",
        outcomes: ["huyết áp"],
        confirmed: false,
      }),
    );
  });

  it("requires explicit confirmation before a run is requested", async () => {
    api.patch.mockResolvedValue({ data: { id: "q-1", confirmed: true } });
    api.post.mockResolvedValue({ data: { id: "run-1" } });

    await confirmEvidenceQuestion("q-1");
    await runEvidenceQuestion("q-1");

    expect(api.patch).toHaveBeenCalledWith("/evidence-questions/q-1", { confirmed: true });
    expect(api.post).toHaveBeenLastCalledWith(
      "/evidence-questions/q-1/run",
      {},
      expect.objectContaining({ headers: expect.objectContaining({ "Idempotency-Key": expect.any(String) }) }),
    );
  });

  it("loads matrix, applicability and contradictions separately", async () => {
    api.get
      .mockResolvedValueOnce({ data: { source_classes: {} } })
      .mockResolvedValueOnce({ data: { status: "not_assessed" } })
      .mockResolvedValueOnce({ data: { status: "not_assessed", items: [] } });

    const details = await getEvidenceDetails("run-1");

    expect(api.get).toHaveBeenNthCalledWith(1, "/evidence-runs/run-1/matrix");
    expect(api.get).toHaveBeenNthCalledWith(2, "/evidence-runs/run-1/applicability");
    expect(api.get).toHaveBeenNthCalledWith(3, "/evidence-runs/run-1/contradictions");
    expect(details.matrix.source_classes).toEqual({});
  });

  it("reads and polls an asynchronous run until it completes", async () => {
    api.get
      .mockResolvedValueOnce({ data: { id: "run-1", status: "queued" } })
      .mockResolvedValueOnce({
        data: {
          id: "run-1",
          status: "completed",
          release_status: "evidence_available",
          evidence_count: 3,
        },
      });
    const onUpdate = vi.fn();

    const run = await pollEvidenceRun("run-1", {
      intervalMs: 0,
      maxAttempts: 3,
      onUpdate,
    });

    expect(api.get).toHaveBeenCalledTimes(2);
    expect(api.get).toHaveBeenNthCalledWith(1, "/evidence-runs/run-1");
    expect(run.status).toBe("completed");
    expect(onUpdate).toHaveBeenNthCalledWith(1, expect.objectContaining({ status: "queued" }), 1);
    expect(onUpdate).toHaveBeenNthCalledWith(2, expect.objectContaining({ status: "completed" }), 2);
  });

  it("returns a failed terminal run without requesting result details", async () => {
    api.get.mockResolvedValue({
      data: { id: "run-2", status: "failed", release_status: "evidence_unavailable" },
    });

    const run = await pollEvidenceRun("run-2", { intervalMs: 0 });

    expect(run.status).toBe("failed");
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it("stops polling after the configured bound", async () => {
    api.get.mockResolvedValue({
      data: { id: "run-3", status: "running", release_status: "evidence_unavailable" },
    });

    await expect(
      pollEvidenceRun("run-3", { intervalMs: 0, maxAttempts: 2 }),
    ).rejects.toThrow("mất nhiều thời gian hơn dự kiến");
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it("gets one run by its encoded identifier", async () => {
    api.get.mockResolvedValue({ data: { id: "run/4", status: "queued" } });

    await getEvidenceRun("run/4");

    expect(api.get).toHaveBeenCalledWith("/evidence-runs/run%2F4");
  });
});
