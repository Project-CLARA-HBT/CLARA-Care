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
});
