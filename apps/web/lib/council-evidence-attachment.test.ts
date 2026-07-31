import { afterEach, describe, expect, it, vi } from "vitest";

import {
  attachCouncilEvidenceSnapshot,
  listCouncilEvidenceAttachments,
  listCouncilEvidenceSnapshotOptions,
} from "@/lib/council";
import api from "@/lib/http-client";

vi.mock("@/lib/http-client", () => ({
  default: { post: vi.fn(), get: vi.fn(), patch: vi.fn() },
}));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Council Research snapshot attachment client", () => {
  it("selects and attaches only a job id; it never sends a browser-built evidence packet", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { id: 7 } });

    await attachCouncilEvidenceSnapshot(42, "research-opaque-id");

    expect(api.post).toHaveBeenCalledWith(
      "/council/cases/42/evidence-snapshots/research-opaque-id/attach",
    );
    expect(api.post).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ council_evidence_packet: expect.anything() }),
    );
  });

  it("uses the owner-scoped options and attachment endpoints without query parameters", async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: { items: [{ job_id: "own-job" }] } })
      .mockResolvedValueOnce({ data: { items: [{ id: 1, research_job_id: "own-job" }] } });

    await expect(listCouncilEvidenceSnapshotOptions(42)).resolves.toEqual([
      { job_id: "own-job" },
    ]);
    await expect(listCouncilEvidenceAttachments(42)).resolves.toEqual([
      { id: 1, research_job_id: "own-job" },
    ]);

    expect(api.get).toHaveBeenNthCalledWith(
      1,
      "/council/cases/42/evidence-snapshots",
    );
    expect(api.get).toHaveBeenNthCalledWith(
      2,
      "/council/cases/42/evidence-attachments",
    );
  });
});
