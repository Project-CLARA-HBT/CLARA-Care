import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminExperimentsPage from "@/app/admin/experiments/page";
import ClinicalFeedbackTriagePage from "@/app/admin/feedback/page";
import type { FeatureFlagExperiment } from "@/lib/experiments";
import type { ClinicalFeedbackItem } from "@/lib/clinical-feedback";

// ---------------------------------------------------------------------------
// Mock Definitions & State
// ---------------------------------------------------------------------------

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

const mockListExperiments = vi.fn();
const mockUpdateExperiment = vi.fn();
const mockOverrideKillSwitch = vi.fn();
const mockCreateExperiment = vi.fn();

const mockListClinicalFeedback = vi.fn();
const mockUpdateFeedbackTriage = vi.fn();
const mockExportFeedbackToBenchmark = vi.fn();

// Mock Experiments Data
const TEST_EXPERIMENTS: FeatureFlagExperiment[] = [
  {
    id: "exp-graphrag",
    key: "rag_graphrag_pipeline",
    name: "GraphRAG Multi-Hop Knowledge Retrieval",
    nameVi: "Truy xuất Đồ thị Tri thức Đa bước GraphRAG",
    description: "Multi-hop knowledge graph expansion for complex clinical inquiries.",
    descriptionVi: "Mở rộng đồ thị tri thức đa bước cho các câu hỏi lâm sàng phức tạp.",
    category: "ai_systems",
    status: "gradual_rollout",
    rolloutPercentage: 40,
    targetRoles: ["admin", "doctor"],
    targetCohorts: ["beta_testers", "vietnam_hospitals"],
    matchMode: "any",
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 18450,
      treatmentImpressions: 7380,
      controlImpressions: 11070,
      errorRate: 0.005,
      latencyP95Ms: 385,
    },
    createdAt: "2026-03-01T08:00:00Z",
    updatedAt: "2026-04-10T14:30:00Z",
    updatedBy: "lead-engineer@clara.vn",
  },
  {
    id: "exp-fides-gate",
    key: "fides_critical_ddi_blocking",
    name: "FIDES Critical Drug-DDI Blocking (Safety Invariant)",
    nameVi: "Khóa Chặn Tương tác Thuốc Nguy hiểm FIDES (Bất biến An toàn)",
    description: "Regression-locked invariant blocking critical contraindicated drug-drug interactions.",
    descriptionVi: "Bất biến khóa hồi quy tự động chặn các tương tác thuốc chống chỉ định nghiêm trọng.",
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
    id: "exp-canary-agent",
    key: "clinical_triage_tier2_pro",
    name: "Tier 2 Pro Reasoning Agent",
    nameVi: "Tác tử Tư duy Lâm sàng Chuyên sâu Tier 2 Pro",
    description: "High-context clinical reasoning agent with multi-specialist verification.",
    descriptionVi: "Tác tử tư duy chuyên sâu ngữ cảnh cao với kiểm định đa chuyên khoa.",
    category: "clinical",
    status: "killed",
    rolloutPercentage: 20,
    targetRoles: ["doctor", "specialist" as any],
    targetCohorts: ["internal_clinicians"],
    matchMode: "all",
    killSwitchActive: true,
    killSwitchReason: "Drift detected in nephrology dosage recommendation",
    createdAt: "2026-05-10T09:00:00Z",
    updatedAt: "2026-05-15T10:00:00Z",
    updatedBy: "safety-board@clara.vn",
  },
];

// Mock Feedback Data
const TEST_FEEDBACK: ClinicalFeedbackItem[] = [
  {
    id: "FB-901",
    query_id: "Q-20492",
    user_query: "Bệnh nhân suy thận eGFR 25 mL/min có dùng được Metformin 1000mg x 2 lần/ngày không?",
    clara_response: "Metformin có thể sử dụng ở liều 1000mg x 2 lần/ngày, cần theo dõi định kỳ chức năng thận.",
    rating: 1,
    category: "dosage_ddi",
    severity: "critical",
    triage_status: "new",
    submitter_role: "specialist",
    submitter_specialty: "Nội thận - Lọc máu",
    comment: "Chống chỉ định tuyệt đối Metformin khi eGFR < 30 mL/min do nguy cơ nhiễm toan acid lactic đe dọa tính mạng.",
    proposed_correction: "Ngừng ngay Metformin. Chuyển sang Linagliptin hoặc Insulin hiệu chỉnh liều theo chức năng thận.",
    cited_guidelines: [
      "Dược thư Quốc gia Việt Nam 2022 - Chuyên luận Metformin",
      "KDIGO 2023 Clinical Practice Guideline for Diabetes Management in CKD",
    ],
    fides_verdict: "BLOCKED_CRITICAL",
    created_at: "2026-08-20T08:15:00Z",
    assigned_to: "Hội đồng An toàn Dược lâm sàng",
    added_to_eval_benchmark: false,
  },
  {
    id: "FB-902",
    query_id: "Q-20488",
    user_query: "Phụ nữ mang thai 3 tháng đầu dùng Isotretinoin bôi ngoài trị mụn được không?",
    clara_response: "Isotretinoin dạng bôi ngoài da có tỷ lệ hấp thu toàn thân thấp, có thể cân nhắc.",
    rating: 1,
    category: "contraindication",
    severity: "critical",
    triage_status: "in_triage",
    submitter_role: "pharmacist",
    submitter_specialty: "Dược lâm sàng",
    comment: "Isotretinoin dù dạng bôi hay uống đều xếp Phân loại X thai kỳ (nguy cơ gây quái thai dị tật tim mặt).",
    proposed_correction: "Tuyệt đối không sử dụng cho phụ nữ có thai. Thay thế bằng Azelaic acid bôi.",
    cited_guidelines: [
      "Thông tư 01/2020/TT-BYT Hướng dẫn sử dụng thuốc cho phụ nữ có thai",
    ],
    fides_verdict: "CONTESTED",
    created_at: "2026-08-21T09:30:00Z",
    assigned_to: "Ban An toàn Dược lâm sàng",
    added_to_eval_benchmark: false,
  },
  {
    id: "FB-903",
    query_id: "Q-20450",
    user_query: "Thời điểm uống Levothyroxine tốt nhất trong ngày là khi nào?",
    clara_response: "Nên uống Levothyroxine vào buổi sáng lúc đói, trước bữa ăn sáng 30-60 phút với một cốc nước đầy.",
    rating: 4,
    category: "clinical_nuance",
    severity: "low",
    triage_status: "resolved",
    submitter_role: "doctor",
    submitter_specialty: "Nội tiết",
    comment: "Hướng dẫn đúng, nên lưu ý thêm cách xa Canxi/Sắt ít nhất 4 giờ.",
    proposed_correction: "Bổ sung lưu ý cách xa Canxi/Sắt ít nhất 4 giờ.",
    cited_guidelines: [
      "American Thyroid Association (ATA) Guidelines on Hypothyroidism",
    ],
    fides_verdict: "VERIFIED",
    created_at: "2026-08-23T16:45:00Z",
    resolved_at: "2026-08-24T09:00:00Z",
    resolution_note: "Đã cập nhật prompt rule về tương tác thức ăn của Levothyroxine.",
    root_cause: "Thiếu rule bổ trợ tương tác vi chất trong hệ thống prompt lâm sàng.",
    assigned_to: "Tổ Y văn & Guideline",
    added_to_eval_benchmark: true,
  },
  {
    id: "FB-904",
    query_id: "Q-20432",
    user_query: "Tương tác giữa Clopidogrel và Omeprazole có làm giảm hiệu quả chống đông không?",
    clara_response: "Omeprazole ức chế CYP2C19, làm giảm chuyển hóa Clopidogrel thành chất có hoạt tính sinh học. Khuyên dùng Pantoprazole.",
    rating: 5,
    category: "positive_accurate",
    severity: "low",
    triage_status: "resolved",
    submitter_role: "specialist",
    submitter_specialty: "Dược lý lâm sàng",
    comment: "Tư vấn rất chính xác, cơ chế rõ ràng.",
    cited_guidelines: ["Dược thư Quốc gia Việt Nam 2022"],
    fides_verdict: "VERIFIED",
    created_at: "2026-08-24T07:20:00Z",
    resolved_at: "2026-08-24T08:30:00Z",
    resolution_note: "Đã lưu vào golden sample corpus.",
    assigned_to: "Hội đồng Thẩm định Y khoa",
    added_to_eval_benchmark: true,
  },
];

// ---------------------------------------------------------------------------
// Module Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/experiments", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/experiments")>();
  return {
    ...actual,
    listExperiments: () => mockListExperiments(),
    createExperiment: (payload: any) => mockCreateExperiment(payload),
    updateExperiment: (id: string | number, updates: any) =>
      mockUpdateExperiment(id, updates),
    overrideKillSwitch: (id: string | number, kill: boolean, reason?: string) =>
      mockOverrideKillSwitch(id, kill, reason),
  };
});

vi.mock("@/lib/clinical-feedback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/clinical-feedback")>();
  return {
    ...actual,
    listClinicalFeedback: (options?: any) => mockListClinicalFeedback(options),
    updateFeedbackTriage: (id: string | number, updates: any) =>
      mockUpdateFeedbackTriage(id, updates),
    exportFeedbackToBenchmark: (id: string | number) =>
      mockExportFeedbackToBenchmark(id),
  };
});

// ---------------------------------------------------------------------------
// Test Suite Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockListExperiments.mockResolvedValue([...TEST_EXPERIMENTS]);
  mockCreateExperiment.mockImplementation(async (payload) => ({
    id: `exp-${Date.now()}`,
    ...payload,
    status: (payload.rolloutPercentage ?? 0) === 100 ? "active" : (payload.rolloutPercentage ?? 0) > 0 ? "gradual_rollout" : "inactive",
    killSwitchActive: false,
    targetRoles: payload.targetRoles || ["admin"],
    targetCohorts: payload.targetCohorts || ["beta_testers"],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    updatedBy: "admin@clara.vn",
  }));
  mockUpdateExperiment.mockImplementation(async (id, updates) => {
    const item = TEST_EXPERIMENTS.find((e) => e.id === id);
    return {
      ...(item ?? TEST_EXPERIMENTS[0]),
      ...updates,
      id,
      updatedAt: new Date().toISOString(),
    };
  });
  mockOverrideKillSwitch.mockImplementation(async (id, kill, reason) => {
    const item = TEST_EXPERIMENTS.find((e) => e.id === id);
    return {
      ...(item ?? TEST_EXPERIMENTS[0]),
      id,
      killSwitchActive: kill,
      status: kill ? "killed" : "gradual_rollout",
      killSwitchReason: reason,
      updatedAt: new Date().toISOString(),
    };
  });

  mockListClinicalFeedback.mockResolvedValue([...TEST_FEEDBACK]);
  mockUpdateFeedbackTriage.mockImplementation(async (id, updates) => {
    const item = TEST_FEEDBACK.find((f) => String(f.id) === String(id));
    return {
      ...(item ?? TEST_FEEDBACK[0]),
      ...updates,
      id,
      updated_at: new Date().toISOString(),
    };
  });
  mockExportFeedbackToBenchmark.mockResolvedValue({
    success: true,
    benchmark_id: "BENCH-GOLDEN-FB-901",
  });
});

afterEach(() => {
  vi.clearAllMocks();
  roleState.role = "admin";
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------
// Test Cases
// ---------------------------------------------------------------------------

describe("Spec v8 Section 12.7 & 12.8: Admin Experiments & Feedback Workbenches", () => {
  describe("Section 12.7: /admin/experiments Feature Flags & Rollout Workbench", () => {
    it("renders AdminShell with ADMIN_COMMAND shell mode and Feature Flags archetype", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(mockListExperiments).toHaveBeenCalled();
        expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
      });

      const workbench = document.querySelector(
        '[data-layout-archetype="Feature Flags & Experimentation Workbench"]'
      );
      expect(workbench).toBeInTheDocument();
      expect(workbench).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");

      // Verify KPI Metrics
      expect(screen.getByText("Total Feature Flags")).toBeInTheDocument();
      expect(screen.getByText("Active Rollouts (1-99%)")).toBeInTheDocument();
      expect(screen.getByText("Fully Enabled (100%)")).toBeInTheDocument();
      expect(screen.getByText("Kill Switch Active")).toBeInTheDocument();
      expect(screen.getAllByText("Safety Invariants").length).toBeGreaterThan(0);
    });

    it("enforces defense-in-depth: non-admin roles receive an Access Denied alert", async () => {
      roleState.role = "doctor";
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
      });

      expect(mockListExperiments).not.toHaveBeenCalled();
    });

    it("displays the global Emergency Kill Switch Alert when any flag is killed", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/1 feature flags are under Emergency Kill Switch Override/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /View Kill-Switched Flags/i })).toBeInTheDocument();
    });

    it("enforces ANA-005 Safety Invariant protection: cannot reduce rollout or trigger kill switch", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
      });

      // ANA-005 badge is visible
      expect(screen.getByText("ANA-005")).toBeInTheDocument();

      // Kill switch is locked
      expect(screen.getByTitle(/Safety invariant locked/i)).toBeInTheDocument();

      // Inline slider is disabled
      const slider = screen.getByLabelText(/Rollout percentage slider for fides_critical_ddi_blocking/i);
      expect(slider).toBeDisabled();
    });

    it("allows adjusting rollout percentage via the Inspector drawer and presets", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
      });

      // Open inspector for GraphRAG
      const inspectButtons = screen.getAllByRole("button", { name: /inspect/i });
      fireEvent.click(inspectButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Experiment Inspector/i)).toBeInTheDocument();
        expect(screen.getByText(/Target Roles/i)).toBeInTheDocument();
        expect(screen.getByText(/Target Cohorts/i)).toBeInTheDocument();
      });

      // Click preset 75%
      const preset75 = screen.getByRole("button", { name: "75%" });
      fireEvent.click(preset75);

      // Save changes
      const saveBtn = screen.getByRole("button", { name: /Save Changes/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateExperiment).toHaveBeenCalledWith(
          "exp-graphrag",
          expect.objectContaining({
            rolloutPercentage: 75,
          })
        );
      });
    });

    it("triggers Emergency Kill Switch override with mandatory reason dialog", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
      });

      // Click kill button on GraphRAG
      const killBtn = screen.getByRole("button", { name: /^kill$/i });
      fireEvent.click(killBtn);

      // Modal dialog opens
      await waitFor(() => {
        expect(screen.getByText(/Confirm Emergency Kill Switch Override/i)).toBeInTheDocument();
      });

      const reasonInput = screen.getByPlaceholderText(/Detected NLI accuracy degradation/i);
      fireEvent.change(reasonInput, { target: { value: "Severe hallucination spike in production" } });

      const confirmBtn = screen.getByRole("button", { name: /Activate Kill Switch/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(mockOverrideKillSwitch).toHaveBeenCalledWith(
          "exp-graphrag",
          true,
          "Severe hallucination spike in production"
        );
      });
    });

    it("supports creating a new feature flag through the creation modal", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
      });

      const newFlagBtn = screen.getByRole("button", { name: /New Flag/i });
      fireEvent.click(newFlagBtn);

      await waitFor(() => {
        expect(screen.getByText(/Create New Feature Flag/i)).toBeInTheDocument();
      });

      const keyInput = screen.getByPlaceholderText(/e\.g\. experimental_clinical_reranker/i);
      const nameInput = screen.getByPlaceholderText(/e\.g\. Clinical Evidence Cross-Encoder/i);

      fireEvent.change(keyInput, { target: { value: "deepseek_r1_verifier" } });
      fireEvent.change(nameInput, { target: { value: "DeepSeek R1 Verification Gate" } });

      const submitBtn = screen.getByRole("button", { name: /Create Flag/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockCreateExperiment).toHaveBeenCalledWith(
          expect.objectContaining({
            key: "deepseek_r1_verifier",
            name: "DeepSeek R1 Verification Gate",
          })
        );
      });
    });

    it("filters feature flags by search query and category", async () => {
      render(<AdminExperimentsPage />);

      await waitFor(() => {
        expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
        expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
      });

      // Filter by category
      const categorySelect = screen.getByLabelText(/Filter Category/i);
      fireEvent.change(categorySelect, { target: { value: "safety_invariant" } });

      expect(screen.queryByText("rag_graphrag_pipeline")).not.toBeInTheDocument();
      expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
    });
  });

  describe("Section 12.8: /admin/feedback Clinical Feedback Triage Queue", () => {
    it("renders AdminShell with Clinical Feedback Triage Queue archetype and live TRIAGE-Q badge", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(mockListClinicalFeedback).toHaveBeenCalled();
        expect(screen.getByText("#FB-901")).toBeInTheDocument();
      });

      expect(screen.getByRole("heading", { level: 1, name: /Clinical Feedback Triage Queue/i })).toBeInTheDocument();
      expect(screen.getByText("TRIAGE-Q")).toBeInTheDocument();

      // Top KPIs
      expect(screen.getByText("Total Feedback")).toBeInTheDocument();
      expect(screen.getByText("Avg Accuracy Rating")).toBeInTheDocument();
      expect(screen.getByText(/Critical Unresolved/i)).toBeInTheDocument();
      expect(screen.getByText("Resolution Rate")).toBeInTheDocument();
    });

    it("renders Accuracy Rating Breakdown and Clinical Risk Category distribution panels", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("Accuracy Rating Breakdown")).toBeInTheDocument();
      });

      expect(screen.getByText("Clinical Risk Category Breakdown")).toBeInTheDocument();

      // Verify distribution rows
      expect(screen.getByText(/5 stars \(Accurate\)/i)).toBeInTheDocument();
      expect(screen.getByText(/1 star \(Critical Hazard\)/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Dosage & Drug Interaction/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Contraindication & Red Flag/i).length).toBeGreaterThan(0);
    });

    it("filters feedback stream items by status pills and search query", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-901")).toBeInTheDocument();
      });

      // Filter by Resolved
      const resolvedBtn = screen.getByRole("button", { name: /Resolved/i });
      fireEvent.click(resolvedBtn);

      await waitFor(() => {
        expect(screen.queryByText("#FB-901")).not.toBeInTheDocument(); // was new
        expect(screen.getByText("#FB-903")).toBeInTheDocument(); // resolved
        expect(screen.getByText("#FB-904")).toBeInTheDocument(); // resolved
      });

      // Search by keyword
      const searchInput = screen.getByPlaceholderText(/Search query, notes, ID.../i);
      fireEvent.change(searchInput, { target: { value: "Levothyroxine" } });

      await waitFor(() => {
        expect(screen.getByText("#FB-903")).toBeInTheDocument();
        expect(screen.queryByText("#FB-904")).not.toBeInTheDocument();
      });
    });

    it("opens the Resolution Inspector Drawer with full clinical context and allows resolving", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-901")).toBeInTheDocument();
      });

      // Open inspector for FB-901
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByText(/1\. Feedback & Submitter Metadata/i)).toBeInTheDocument();
        expect(screen.getByText(/2\. Clinical Query & CLARA Output/i)).toBeInTheDocument();
        expect(screen.getByText(/3\. Clinician Observation & Proposal/i)).toBeInTheDocument();
        expect(screen.getByText(/4\. Triage Resolution & Workflow/i)).toBeInTheDocument();
      });

      // Verify clinical query and comment are displayed
      expect(screen.getAllByText(/Bệnh nhân suy thận eGFR 25 mL\/min/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Chống chỉ định tuyệt đối Metformin/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Ngừng ngay Metformin/i)).toBeInTheDocument();

      // Update resolution note
      const notesTextarea = screen.getByLabelText(/Resolution Notes & Corrective Actions/i);
      fireEvent.change(notesTextarea, {
        target: { value: "Updated FIDES renal rule bound: blocks Metformin when eGFR < 30." },
      });

      // Save changes
      const saveBtn = screen.getByRole("button", { name: /Save Changes/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateFeedbackTriage).toHaveBeenCalledWith(
          "FB-901",
          expect.objectContaining({
            resolution_note: "Updated FIDES renal rule bound: blocks Metformin when eGFR < 30.",
          })
        );
      });
    });

    it("exports clinical feedback item to Golden RAG Benchmark", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-901")).toBeInTheDocument();
      });

      // Open inspector for FB-901
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Export RAG Golden/i })).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /Export RAG Golden/i });
      fireEvent.click(exportBtn);

      await waitFor(() => {
        expect(mockExportFeedbackToBenchmark).toHaveBeenCalledWith("FB-901");
      });

      expect(screen.getByText(/Exported feedback #FB-901 to RAG Golden Benchmark/i)).toBeInTheDocument();
    });
  });
});
