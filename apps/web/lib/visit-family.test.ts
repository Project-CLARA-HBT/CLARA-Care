import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@/lib/http-client", () => ({ default: api }));

import {
  answerVisitIntake,
  createVisitDocument,
  deleteVisitDocument,
  extractVisitPlan,
} from "@/lib/visit-family";

describe("visit-family phase 3 API contracts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits exactly one intake answer and returns server-selected progress", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        id: "9",
        question_key: "visit_goal",
        response_state: "skipped",
        progress: { answered: 1, total: 3 },
        next_question: null,
        complete: true,
      },
    });

    await expect(
      answerVisitIntake("12", {
        question_key: "visit_goal",
        response_state: "skipped",
      }),
    ).resolves.toMatchObject({ progress: { answered: 1, total: 3 }, complete: true });
    expect(api.post).toHaveBeenCalledWith("/visits/12/intake/answers", {
      question_key: "visit_goal",
      response_state: "skipped",
    });
  });

  it("keeps selected document provenance and sends delete reason in the request body", async () => {
    api.post.mockResolvedValueOnce({ data: { id: "4", title: "lab.txt" } });
    api.delete.mockResolvedValueOnce({ data: { id: "4", deleted_at: "2026-07-25T00:00:00Z" } });

    await createVisitDocument("12", {
      title: "lab.txt",
      text_content: "HbA1c 6.5",
      metadata: { capture: "user_selected", source_file_name: "lab.txt" },
    });
    await deleteVisitDocument("12", "4", "user_requested");

    expect(api.post).toHaveBeenCalledWith("/visits/12/documents", {
      title: "lab.txt",
      text_content: "HbA1c 6.5",
      metadata: { capture: "user_selected", source_file_name: "lab.txt" },
      media_type: "text/plain",
    });
    expect(api.delete).toHaveBeenCalledWith("/visits/12/documents/4", {
      data: { reason: "user_requested" },
    });
  });

  it("uses a persisted document id for safe plan extraction", async () => {
    api.post.mockResolvedValueOnce({
      data: { id: "8", status: "extraction_unavailable", candidates: [], safe_unavailable: true },
    });
    await extractVisitPlan("12", "4");
    expect(api.post).toHaveBeenCalledWith("/visits/12/plan/extract", { document_id: 4 });
  });
});
