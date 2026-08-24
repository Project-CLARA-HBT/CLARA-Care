import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/http-client";
import {
  calculateExperimentStats,
  createExperiment,
  listExperiments,
  overrideKillSwitch,
  updateExperiment,
  type FeatureFlagExperiment,
} from "./experiments";

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

const sampleExperiments: FeatureFlagExperiment[] = [
  {
    id: "1",
    key: "rag_graphrag_pipeline",
    name: "GraphRAG Multi-Hop Knowledge Retrieval",
    nameVi: "Truy xuất Đồ thị Tri thức Đa bước GraphRAG",
    description: "Multi-hop knowledge graph expansion.",
    descriptionVi: "Mở rộng đồ thị tri thức đa bước.",
    category: "ai_systems",
    status: "gradual_rollout",
    rolloutPercentage: 35,
    targetRoles: ["admin", "doctor"],
    targetCohorts: ["beta_testers"],
    matchMode: "any",
    killSwitchActive: false,
    createdAt: "2026-03-01T08:00:00Z",
    updatedAt: "2026-04-10T14:30:00Z",
    updatedBy: "lead-engineer@clara.vn",
  },
  {
    id: "2",
    key: "fides_critical_ddi_blocking",
    name: "FIDES Critical Drug-DDI Blocking",
    nameVi: "Khóa Chặn Tương tác Thuốc Nguy hiểm FIDES",
    description: "Safety invariant blocking contraindicated drugs.",
    descriptionVi: "Bất biến khóa hồi quy tự động chặn tương tác nguy hiểm.",
    category: "safety_invariant",
    status: "active",
    rolloutPercentage: 100,
    targetRoles: ["admin", "doctor", "researcher", "normal"],
    targetCohorts: ["general_users"],
    matchMode: "any",
    killSwitchActive: false,
    isSafetyInvariant: true,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    updatedBy: "safety-board@clara.vn",
  },
  {
    id: "3",
    key: "scribe_ambient_noise_filter",
    name: "Scribe Ambient Noise Filter",
    nameVi: "Bộ lọc Tiếng ồn Môi trường Scribe",
    description: "Acoustic noise filter",
    descriptionVi: "Khử nhiễu âm học",
    category: "clinical",
    status: "killed",
    rolloutPercentage: 0,
    targetRoles: ["doctor"],
    targetCohorts: ["internal_clinicians"],
    matchMode: "all",
    killSwitchActive: true,
    killSwitchReason: "Acoustic degradation alert",
    createdAt: "2026-03-20T10:00:00Z",
    updatedAt: "2026-04-12T16:45:00Z",
    updatedBy: "scribe-team@clara.vn",
  },
];

describe("experiments domain library (Spec v5 Section 6.67)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("calculateExperimentStats", () => {
    it("calculates accurate summary stats from experiment list", () => {
      const stats = calculateExperimentStats(sampleExperiments);
      expect(stats.totalFlags).toBe(3);
      expect(stats.safetyInvariants).toBe(1);
      expect(stats.fullyEnabled).toBe(1);
      expect(stats.activeRollouts).toBe(1);
      expect(stats.killSwitched).toBe(1);
    });
  });

  describe("listExperiments", () => {
    it("fetches experiments from server and maps rollout basis points to percentages", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: [
          {
            id: 10,
            key: "rag_graphrag_pipeline",
            name: "GraphRAG",
            description: "Multi-hop RAG",
            status: "running",
            rollout_basis_points: 3500,
            safety_owner: "ai-team",
            resource_version: "1",
            target_rules_json: {
              category: "ai_systems",
              target_roles: ["admin", "doctor"],
              target_cohorts: ["beta_testers"],
            },
          },
        ],
      });

      const list = await listExperiments("running");
      expect(mockApi.get).toHaveBeenCalledWith("/admin/experiments", {
        params: { status: "running" },
      });
      expect(list.length).toBe(1);
      expect(list[0].id).toBe("10");
      expect(list[0].key).toBe("rag_graphrag_pipeline");
      expect(list[0].rolloutPercentage).toBe(35);
      expect(list[0].status).toBe("gradual_rollout");
    });

    it("fails closed on server error 500", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(listExperiments()).rejects.toThrow(/500/);
    });

    it("fails closed on 403 Forbidden", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("403 Forbidden"));

      await expect(listExperiments()).rejects.toThrow(/403 Forbidden/);
    });
  });

  describe("createExperiment", () => {
    it("posts new experiment to /admin/experiments and returns created entity", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          id: 15,
          key: "new_canary_feature",
          name: "New Canary Feature",
          description: "Testing feature",
          status: "draft",
          rollout_basis_points: 2000,
          safety_owner: "infra-team",
          resource_version: "1",
          target_rules_json: {
            category: "platform",
            target_roles: ["admin"],
            target_cohorts: ["canary_nodes"],
          },
        },
      });

      const res = await createExperiment({
        key: "new_canary_feature",
        name: "New Canary Feature",
        description: "Testing feature",
        rolloutPercentage: 20,
        category: "platform",
        targetRoles: ["admin"],
        targetCohorts: ["canary_nodes"],
        safetyOwner: "infra-team",
      });

      expect(mockApi.post).toHaveBeenCalledWith("/admin/experiments", {
        key: "new_canary_feature",
        name: "New Canary Feature",
        description: "Testing feature",
        rollout_basis_points: 2000,
        safety_owner: "infra-team",
        target_rules_json: {
          name_vi: undefined,
          description_vi: undefined,
          category: "platform",
          target_roles: ["admin"],
          target_cohorts: ["canary_nodes"],
          is_safety_invariant: undefined,
        },
      });
      expect(res.id).toBe("15");
      expect(res.rolloutPercentage).toBe(20);
    });

    it("fails closed on 409 Conflict (duplicate key)", async () => {
      mockApi.post.mockRejectedValueOnce(new Error("EXPERIMENT_KEY_EXISTS: new_canary_feature"));

      await expect(
        createExperiment({
          key: "new_canary_feature",
          name: "New Canary Feature",
        }),
      ).rejects.toThrow(/EXPERIMENT_KEY_EXISTS/);
    });
  });

  describe("updateExperiment", () => {
    it("patches rollout percentage via /admin/experiments/:id/rollout", async () => {
      mockApi.patch.mockResolvedValueOnce({
        data: {
          id: 10,
          key: "rag_graphrag_pipeline",
          name: "GraphRAG",
          description: "Multi-hop RAG",
          status: "running",
          rollout_basis_points: 7500,
          safety_owner: "ai-team",
          resource_version: "2",
          target_rules_json: {},
        },
      });

      const updated = await updateExperiment("10", {
        rolloutPercentage: 75,
        expectedResourceVersion: "1",
        reasonCode: "CANARY_STAGE_2",
      });

      expect(mockApi.patch).toHaveBeenCalledWith("/admin/experiments/10/rollout", {
        rollout_basis_points: 7500,
        expected_resource_version: "1",
        reason_code: "CANARY_STAGE_2",
      });
      expect(updated.rolloutPercentage).toBe(75);
      expect(updated.status).toBe("gradual_rollout");
    });

    it("fails closed on 409 Conflict (RESOURCE_VERSION_CONFLICT)", async () => {
      mockApi.patch.mockRejectedValueOnce(
        new Error("RESOURCE_VERSION_CONFLICT: Expected 1, found 2"),
      );

      await expect(
        updateExperiment("10", {
          rolloutPercentage: 80,
          expectedResourceVersion: "1",
        }),
      ).rejects.toThrow(/RESOURCE_VERSION_CONFLICT/);
    });

    it("enforces ANA-005 invariant: prevents reducing rollout on safety invariants", async () => {
      await expect(
        updateExperiment("2", {
          isSafetyInvariant: true,
          rolloutPercentage: 50,
        }),
      ).rejects.toThrow(/safety invariant/i);
    });

    it("enforces ANA-005 invariant: prevents kill switch on safety invariants", async () => {
      await expect(
        updateExperiment("2", {
          isSafetyInvariant: true,
          killSwitchActive: true,
        }),
      ).rejects.toThrow(/safety invariant/i);
    });
  });

  describe("overrideKillSwitch", () => {
    it("activates emergency kill switch via POST /admin/experiments/:id/kill", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          id: 12,
          key: "scribe_ambient_noise_filter",
          name: "Scribe Filter",
          status: "killed",
          rollout_basis_points: 0,
          safety_owner: "scribe-team",
          resource_version: "3",
          target_rules_json: {},
        },
      });

      const killed = await overrideKillSwitch("12", true, "Acoustic noise degradation reported");

      expect(mockApi.post).toHaveBeenCalledWith("/admin/experiments/12/kill", {
        reason: "Acoustic noise degradation reported",
        expected_resource_version: undefined,
      });
      expect(killed.status).toBe("killed");
      expect(killed.killSwitchActive).toBe(true);
    });

    it("restores feature rollout via PATCH /admin/experiments/:id/rollout", async () => {
      mockApi.patch.mockResolvedValueOnce({
        data: {
          id: 12,
          key: "scribe_ambient_noise_filter",
          name: "Scribe Filter",
          status: "paused",
          rollout_basis_points: 0,
          safety_owner: "scribe-team",
          resource_version: "4",
          target_rules_json: {},
        },
      });

      const restored = await overrideKillSwitch("12", false, "Restoring feature");

      expect(mockApi.patch).toHaveBeenCalledWith("/admin/experiments/12/rollout", {
        rollout_basis_points: 0,
        expected_resource_version: undefined,
        reason_code: "Restoring feature",
      });
      expect(restored.killSwitchActive).toBe(false);
    });

    it("fails closed on 500 error during kill switch operation", async () => {
      mockApi.post.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(overrideKillSwitch("12", true)).rejects.toThrow(/500/);
    });
  });
});
