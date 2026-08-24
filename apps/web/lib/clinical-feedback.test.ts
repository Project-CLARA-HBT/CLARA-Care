import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/http-client";
import {
  computeFeedbackMetrics,
  exportFeedbackToBenchmark,
  getCategoryMeta,
  getClinicalFeedbackDetail,
  getRoleMeta,
  getSeverityMeta,
  getTriageStatusMeta,
  listClinicalFeedback,
  updateFeedbackTriage,
  type ClinicalFeedbackItem,
} from "./clinical-feedback";

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const sampleFeedbackItems: ClinicalFeedbackItem[] = [
  {
    id: "FB-801",
    query_id: "Q-101",
    user_query: "Metformin with renal failure",
    clara_response: "Can use Metformin",
    rating: 1,
    category: "dosage_ddi",
    severity: "critical",
    triage_status: "new",
    submitter_role: "specialist",
    comment: "Contraindicated under eGFR 30",
    created_at: "2026-08-20T08:15:00Z",
  },
  {
    id: "FB-802",
    query_id: "Q-102",
    user_query: "Isotretinoin in pregnancy",
    clara_response: "Topical may be considered",
    rating: 1,
    category: "contraindication",
    severity: "critical",
    triage_status: "in_triage",
    submitter_role: "pharmacist",
    comment: "Pregnancy Category X",
    created_at: "2026-08-21T09:30:00Z",
  },
  {
    id: "FB-805",
    query_id: "Q-105",
    user_query: "Levothyroxine timing",
    clara_response: "Take before breakfast",
    rating: 4,
    category: "clinical_nuance",
    severity: "low",
    triage_status: "resolved",
    submitter_role: "doctor",
    comment: "Take away from Calcium/Iron",
    created_at: "2026-08-23T16:45:00Z",
    resolved_at: "2026-08-24T09:00:00Z",
    resolution_note: "Updated prompt rules",
  },
];

describe("clinical-feedback domain and client (Spec v5 Section 6.71)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("listClinicalFeedback", () => {
    it("preserves known_empty when server returns empty array []", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: [],
      });

      const list = await listClinicalFeedback();
      expect(mockApi.get).toHaveBeenCalledWith("/admin/feedback", { params: {} });
      expect(list).toEqual([]);
      expect(list.length).toBe(0);
    });

    it("preserves known_empty when server returns { items: [], total: 0 }", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          items: [],
          total: 0,
          next_cursor: null,
        },
      });

      const list = await listClinicalFeedback({ status: "new" });
      expect(mockApi.get).toHaveBeenCalledWith("/admin/feedback", {
        params: { status: "open" },
      });
      expect(list).toEqual([]);
      expect(list.length).toBe(0);
    });

    it("maps server items to typed ClinicalFeedbackItem array", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: [
          {
            id: 801,
            public_id: "FB-801",
            source_workflow: "chat_copilot",
            target_id: "Q-101",
            status: "open",
            category: "dosage_ddi",
            clinical_severity: "critical",
            free_text_redacted: "Contraindicated under eGFR 30",
            metadata_json: {
              user_query: "Metformin in CKD",
              clara_response: "Can use Metformin",
              rating: 1,
              submitter_role: "specialist",
            },
            resource_version: "1",
            created_at: "2026-08-20T08:15:00Z",
          },
        ],
      });

      const list = await listClinicalFeedback();
      expect(list.length).toBe(1);
      expect(list[0].id).toBe("FB-801");
      expect(list[0].category).toBe("dosage_ddi");
      expect(list[0].severity).toBe("critical");
      expect(list[0].triage_status).toBe("new");
      expect(list[0].rating).toBe(1);
    });

    it("fails closed on 403 Forbidden", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("403 Forbidden: Insufficient permissions"));

      await expect(listClinicalFeedback()).rejects.toThrow(/403 Forbidden/);
    });

    it("fails closed on 500 Server Error", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(listClinicalFeedback()).rejects.toThrow(/500/);
    });
  });

  describe("getClinicalFeedbackDetail", () => {
    it("fetches single item from /admin/feedback/:id", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          id: 801,
          public_id: "FB-801",
          status: "open",
          category: "dosage_ddi",
          clinical_severity: "critical",
          free_text_redacted: "Test comment",
        },
      });

      const detail = await getClinicalFeedbackDetail("801");
      expect(mockApi.get).toHaveBeenCalledWith("/admin/feedback/801");
      expect(detail.id).toBe("FB-801");
    });

    it("fails closed on 404 NOT_FOUND", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("FEEDBACK_NOT_FOUND"));

      await expect(getClinicalFeedbackDetail("999")).rejects.toThrow(/FEEDBACK_NOT_FOUND/);
    });
  });

  describe("updateFeedbackTriage", () => {
    it("patches status via /admin/feedback/:id/status", async () => {
      mockApi.patch.mockResolvedValueOnce({
        data: {
          id: 801,
          public_id: "FB-801",
          status: "in_review",
          category: "dosage_ddi",
          clinical_severity: "critical",
          resource_version: "2",
        },
      });

      const updated = await updateFeedbackTriage("801", {
        triage_status: "in_triage",
        expectedResourceVersion: "1",
      });

      expect(mockApi.patch).toHaveBeenCalledWith("/admin/feedback/801/status", {
        status: "in_review",
        notes: "",
        expected_resource_version: "1",
      });
      expect(updated.triage_status).toBe("in_triage");
    });

    it("resolves feedback via resolution endpoint when resolving", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          id: 801,
          public_id: "FB-801",
          status: "resolved",
          category: "dosage_ddi",
          clinical_severity: "critical",
          resolution_json: {
            resolution_summary: "Fixed knowledge prompt rule",
            action_taken: "PROMPT_UPDATE",
          },
          resource_version: "2",
        },
      });

      const updated = await updateFeedbackTriage("801", {
        triage_status: "resolved",
        resolution_note: "Fixed knowledge prompt rule",
        root_cause: "PROMPT_UPDATE",
      });

      expect(mockApi.post).toHaveBeenCalledWith("/admin/feedback/801/resolution", {
        resolution_summary: "Fixed knowledge prompt rule",
        action_taken: "PROMPT_UPDATE",
        clinical_notes: undefined,
        benchmark_candidate: false,
      });
      expect(updated.triage_status).toBe("resolved");
    });

    it("fails closed on 409 Conflict (RESOURCE_VERSION_CONFLICT)", async () => {
      mockApi.patch.mockRejectedValueOnce(
        new Error("RESOURCE_VERSION_CONFLICT: Expected 1, found 2"),
      );

      await expect(
        updateFeedbackTriage("801", {
          triage_status: "dismissed",
          expectedResourceVersion: "1",
        }),
      ).rejects.toThrow(/RESOURCE_VERSION_CONFLICT/);
    });
  });

  describe("exportFeedbackToBenchmark", () => {
    it("posts to benchmark export resolution", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          id: 801,
          public_id: "FB-801",
          status: "resolved",
        },
      });

      const res = await exportFeedbackToBenchmark("801");
      expect(res.success).toBe(true);
      expect(res.benchmark_id).toBe("BENCH-GOLDEN-801");
    });

    it("fails closed on HTTP error", async () => {
      mockApi.post.mockRejectedValue(new Error("500 Export Failed"));

      await expect(exportFeedbackToBenchmark("801")).rejects.toThrow(/500/);
    });
  });

  describe("computeFeedbackMetrics", () => {
    it("handles known_empty array without dividing by zero", () => {
      const stats = computeFeedbackMetrics([]);
      expect(stats.total_feedback).toBe(0);
      expect(stats.avg_accuracy_rating).toBe(0);
      expect(stats.unresolved_critical_high).toBe(0);
      expect(stats.resolution_rate).toBe(0);
    });

    it("calculates accurate summary stats from sample feedback items", () => {
      const stats = computeFeedbackMetrics(sampleFeedbackItems);
      expect(stats.total_feedback).toBe(3);
      expect(stats.unresolved_critical_high).toBe(2); // FB-801 (new) + FB-802 (in_triage)
      expect(stats.resolution_rate).toBe(33); // 1 out of 3 resolved = 33%
      expect(stats.category_breakdown.dosage_ddi).toBe(1);
      expect(stats.category_breakdown.contraindication).toBe(1);
      expect(stats.category_breakdown.clinical_nuance).toBe(1);
      expect(stats.status_breakdown.new).toBe(1);
      expect(stats.status_breakdown.in_triage).toBe(1);
      expect(stats.status_breakdown.resolved).toBe(1);
    });
  });

  describe("metadata helpers", () => {
    it("provides metadata for all categories", () => {
      for (const cat of [
        "dosage_ddi",
        "contraindication",
        "hallucination",
        "citation_mismatch",
        "clinical_nuance",
        "positive_accurate",
      ] as const) {
        const metaVi = getCategoryMeta(cat, "vi");
        const metaEn = getCategoryMeta(cat, "en");
        expect(metaVi.label).toBeDefined();
        expect(metaEn.label).toBeDefined();
        expect(metaVi.tone).toBeDefined();
      }
    });

    it("provides metadata for all severities", () => {
      for (const sev of ["critical", "high", "medium", "low"] as const) {
        const metaVi = getSeverityMeta(sev, "vi");
        expect(metaVi.label).toBeDefined();
        expect(metaVi.tone).toBeDefined();
      }
    });

    it("provides metadata for all triage statuses", () => {
      for (const st of ["new", "in_triage", "resolved", "dismissed"] as const) {
        const metaVi = getTriageStatusMeta(st, "vi");
        expect(metaVi.label).toBeDefined();
        expect(metaVi.tone).toBeDefined();
      }
    });

    it("provides metadata for all roles", () => {
      for (const role of ["doctor", "specialist", "pharmacist", "researcher", "normal"] as const) {
        const metaVi = getRoleMeta(role, "vi");
        expect(metaVi.label).toBeDefined();
        expect(metaVi.badge).toBeDefined();
      }
    });
  });
});
