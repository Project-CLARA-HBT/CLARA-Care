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
  confirmVisitPlan,
  createVisitDocument,
  createVisitPack,
  deleteVisitDocument,
  extractVisitPlan,
  getVisitPackOptions,
  revokeVisitShare,
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

  it("preserves an opaque persisted document id for safe plan extraction", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        id: "draft_K3",
        status: "extraction_unavailable",
        candidates: [],
        safe_unavailable: true,
      },
    });
    await extractVisitPlan("visit_A7", "document_B9");
    expect(api.post).toHaveBeenCalledWith("/visits/visit_A7/plan/extract", {
      document_id: "document_B9",
    });
  });

  it("loads only owner-scoped choices for an explicit Visit Pack selection", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        concerns: [{ id: "concern_A", label: "Đau khi đi bộ" }],
        episodes: [],
        events: [],
        medications: [{ id: "medication_B", label: "Metformin" }],
        instructions: [{ id: "instruction_I", label: "Theo dõi 7 ngày" }],
      },
    });

    await getVisitPackOptions("visit_A7");

    expect(api.get).toHaveBeenCalledWith("/visits/visit_A7/pack-options");
  });

  it("creates a Visit Pack from exact opaque selections instead of booleans", async () => {
    api.post.mockResolvedValueOnce({
      data: { id: "pack_P1", version_no: 1, status: "draft" },
    });

    const selection = {
      concern_ids: ["concern_A"],
      episode_ids: ["episode_C"],
      event_ids: [],
      medication_course_ids: ["medication_B"],
      instruction_candidate_ids: ["instruction_I"],
      questions: ["Tôi cần theo dõi gì?"],
    };
    await createVisitPack("visit_A7", selection);

    expect(api.post).toHaveBeenCalledWith("/visits/visit_A7/pack", { selection });
  });

  it("confirms only the explicitly selected grounded candidate ids", async () => {
    api.post.mockResolvedValueOnce({
      data: {
        id: "draft_K3",
        status: "confirmed",
        task_ids: ["task_T4"],
        task_status: "proposed",
        episode_event_ids: [],
      },
    });

    await confirmVisitPlan("visit_A7", {
      draft_id: "draft_K3",
      candidate_ids: ["candidate_C5"],
      episode_id: "episode_E6",
    });

    expect(api.post).toHaveBeenCalledWith("/visits/visit_A7/plan/confirm", {
      draft_id: "draft_K3",
      candidate_ids: ["candidate_C5"],
      episode_id: "episode_E6",
    });
  });

  it("revokes the exact opaque Visit Pack share", async () => {
    api.delete.mockResolvedValueOnce({ data: { status: "revoked" } });

    await revokeVisitShare("pack_P1", "share_S2");

    expect(api.delete).toHaveBeenCalledWith("/visit-packs/pack_P1/shares/share_S2");
  });
});
