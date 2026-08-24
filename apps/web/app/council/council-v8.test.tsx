import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CouncilPage from "./page";
import CouncilNewPage from "./new/page";
import CouncilNewIntakePage from "./new/intake/page";
import CouncilNewSpecialistsPage from "./new/specialists/page";
import CouncilNewReviewPage from "./new/review/page";
import CouncilResultPage from "./result/page";
import {
  createCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  listCouncilCases,
  runCouncilCaseById,
  setActiveCouncilCaseId,
  submitCouncilOversight,
  updateCouncilCase,
} from "@/lib/council";
import { trackCouncilViewed } from "@/lib/analytics/events";

const mockReplace = vi.fn();
const mockPush = vi.fn();
const mockRouter = {
  replace: mockReplace,
  push: mockPush,
  pathname: "/council",
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/analytics/events", () => ({
  trackCouncilViewed: vi.fn(),
  trackCouncilRun: vi.fn(),
}));

vi.mock("@/lib/council", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/council")>();
  return {
    ...actual,
    listCouncilCases: vi.fn(),
    getCouncilCase: vi.fn(),
    getLatestCouncilCase: vi.fn(),
    getActiveCouncilCaseId: vi.fn(),
    setActiveCouncilCaseId: vi.fn(),
    clearActiveCouncilCaseId: vi.fn(),
    createCouncilCase: vi.fn(),
    updateCouncilCase: vi.fn(),
    runCouncilCaseIntake: vi.fn(),
    runCouncilCaseById: vi.fn(),
    streamCouncilRun: vi.fn(),
    isCouncilStreamingEnabled: vi.fn(() => false),
    isCouncilOversightEnabled: vi.fn(() => true),
    isCouncilModelDisclosureEnabled: vi.fn(() => true),
    submitCouncilOversight: vi.fn(),
  };
});

const mockCaseAnalyzed = {
  id: 201,
  title: "BN Nam 64T - Đau ngực không ổn định",
  status: "analyzed",
  oversight_state: "normal",
  request: {
    question: "Phác đồ điều trị tối ưu cho bệnh nhân suy tim?",
    symptoms: ["Đau ngực", "Khó thở khi gắng sức"],
    labs: { Creatinine: "1.2 mg/dL", eGFR: "65 mL/min" },
    medications: ["Metformin 1000mg", "Amlodipine 5mg"],
    history: "Tăng huyết áp 10 năm, ĐTĐ type 2",
    specialist_count: 3,
    specialists: ["cardiology", "endocrinology", "pharmacology"],
  },
  result: {
    final_recommendation: "Khuyến nghị phối hợp Empagliflozin 10mg và Sacubitril/Valsartan 50mg.",
    consensus: "Hội đồng đồng thuận cao về việc khởi đầu SGLT2i và ARNI.",
    conflicts: ["Thời điểm ngừng ACEi trước khi chuyển sang ARNI (yêu cầu khoảng chờ 36h)."],
    divergence: ["Liều khởi đầu Sacubitril/Valsartan giữa Tim mạch và Dược lâm sàng."],
    council_consensus: {
      support_ratio: 0.9,
      conflict_count: 1,
    },
    support_ratio: 0.9,
    conflict_count: 1,
    urgency_tier: "urgent",
    escalation_priority: "P2_ELEVATED",
    recommended_sla_minutes: 30,
    specialists: [
      {
        id: "cardiology",
        name: "Tim mạch",
        role: "cardiology",
        stance: "Đồng thuận",
        recommendation: "Khởi đầu sớm Sacubitril/Valsartan 49/51mg bid.",
        findings: ["EF giảm 38%", "NT-proBNP tăng cao"],
      },
      {
        id: "pharmacology",
        name: "Dược lâm sàng",
        role: "pharmacology",
        stance: "Đồng thuận có điều kiện",
        recommendation: "Rà soát nguy cơ hạ huyết áp tư thế khi phối hợp.",
        findings: ["Cần theo dõi sát Creatinine sau 1-2 tuần"],
      },
    ],
    citations: [
      {
        title: "2023 ESC Guidelines for the management of acute and chronic heart failure",
        source: "European Heart Journal",
        snippet: "SGLT2 inhibitors and ARNI are recommended as first-line therapy for HFrEF.",
        url: "https://doi.org/10.1093/eurheartj/ehad195",
      },
    ],
    medication_safety: {
      review_required: true,
      state: "checked",
      warnings: ["Cảnh báo hạ huyết áp khi phối hợp ARNI và thuốc chống tăng huyết áp"],
    },
  },
  created_at: "2026-08-24T08:00:00Z",
  updated_at: "2026-08-24T09:30:00Z",
};

const mockCaseDraft = {
  id: 202,
  title: "BN Nữ 52T - Rối loạn lipid máu",
  status: "intake_ready",
  oversight_state: "normal",
  request: {
    question: "Đánh giá nguy cơ tim mạch và chỉ định Statin",
    symptoms: ["Hồi hộp"],
    labs: { LDL: "190 mg/dL" },
    medications: [],
  },
  created_at: "2026-08-24T10:00:00Z",
  updated_at: "2026-08-24T10:00:00Z",
};

describe("Spec v8 Section 7.6 & 7.7: Council Workflows & Pure 7-Tier Decision Review", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listCouncilCases).mockResolvedValue({
      items: [mockCaseAnalyzed, mockCaseDraft],
      total: 2,
    } as any);
    vi.mocked(getLatestCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
    vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
    vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
    vi.mocked(runCouncilCaseById).mockResolvedValue(mockCaseAnalyzed as any);
  });

  describe("1. /council Case Library Archetype (Spec v8 §7.6)", () => {
    it("renders Case Library with Active Resumable Case Hero and '+ Tạo ca mới' CTA", async () => {
      render(<CouncilPage />);

      await waitFor(() => {
        expect(screen.getByText("Thư viện ca hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "landing" });

      // Active Case HeroObject
      expect(screen.getByText("Ca đang thực hiện")).toBeInTheDocument();
      expect(screen.getByLabelText("Active resumable case")).toBeInTheDocument();
      expect(screen.getAllByText(/BN Nam 64T - Đau ngực không ổn định/i).length).toBeGreaterThanOrEqual(1);

      // Status chip and primary action
      expect(screen.getAllByText("Đã hội chẩn").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Xem kết luận hội chẩn").length).toBeGreaterThanOrEqual(1);

      // '+ Tạo ca mới' CTA button
      const newCaseCtas = screen.getAllByRole("link", { name: /\+ Tạo ca mới/i });
      expect(newCaseCtas.length).toBeGreaterThanOrEqual(1);
      expect(newCaseCtas[0]).toHaveAttribute("href", "/council/new");
    });

    it("renders recent cases list as clean rows with status chips and filters by search", async () => {
      render(<CouncilPage />);

      await waitFor(() => {
        expect(screen.getByText("Danh sách ca gần đây")).toBeInTheDocument();
      });

      // Rows present
      expect(screen.getAllByText(/BN Nam 64T/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/BN Nữ 52T/i).length).toBeGreaterThanOrEqual(1);

      // Search filter
      const searchInput = screen.getByPlaceholderText(/Tìm theo tiêu đề, #ID/i);
      fireEvent.change(searchInput, { target: { value: "lipid" } });

      await waitFor(() => {
        expect(screen.getByText(/BN Nữ 52T - Rối loạn lipid máu/i)).toBeInTheDocument();
      });
    });

    it("filters cases by status tabs (All, Deliberated, In Progress)", async () => {
      render(<CouncilPage />);

      await waitFor(() => {
        expect(screen.getByText("Danh sách ca gần đây")).toBeInTheDocument();
      });

      const deliberatedTab = screen.getByRole("button", { name: "Đã hội chẩn" });
      fireEvent.click(deliberatedTab);

      await waitFor(() => {
        expect(screen.getAllByText(/BN Nam 64T/i).length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("2. /council/new/* Focused Wizard Steps (Spec v8 §7.6)", () => {
    it("Step 1 (/council/new): renders clean entry form without redundant chrome", async () => {
      vi.mocked(createCouncilCase).mockResolvedValue({
        id: 203,
        title: "BN Nam 55T - Đau đầu cấp",
        status: "created",
      } as any);

      render(<CouncilNewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tạo ca trước khi phân tích")).toBeInTheDocument();
      });

      const titleInput = screen.getByLabelText(/Tiêu đề ca bệnh/i);
      fireEvent.change(titleInput, { target: { value: "BN Nam 55T - Đau đầu cấp" } });

      const submitBtn = screen.getByRole("button", { name: /Tạo ca mới/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(createCouncilCase).toHaveBeenCalledWith({
          title: "BN Nam 55T - Đau đầu cấp",
        });
        expect(setActiveCouncilCaseId).toHaveBeenCalledWith(203);
        expect(mockPush).toHaveBeenCalledWith("/council/new/intake?caseId=203");
      });
    });

    it("Step 2 (/council/new/intake): loads and updates clinical context", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(updateCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewIntakePage />);

      await waitFor(() => {
        expect(screen.getByText("Thông tin ban đầu")).toBeInTheDocument();
      });

      const questionInput = screen.getByPlaceholderText(/Nhập câu hỏi hội chẩn/i);
      expect(questionInput).toHaveValue("Phác đồ điều trị tối ưu cho bệnh nhân suy tim?");

      const nextBtn = screen.getByRole("button", { name: /Sang bước 3/i });
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(updateCouncilCase).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith("/council/new/specialists?caseId=201");
      });
    });

    it("Step 3 (/council/new/specialists): manages specialist selection", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(updateCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewSpecialistsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Bước 3 \/ 4 · Hội đồng chuyên khoa/i)).toBeInTheDocument();
      });

      const nextBtn = screen.getByRole("button", { name: /Sang bước 4/i });
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(updateCouncilCase).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith("/council/new/review?caseId=201");
      });
    });

    it("Step 4 (/council/new/review): reviews case facts and triggers council deliberation", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(runCouncilCaseById).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewReviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Rà soát trước khi hội chẩn")).toBeInTheDocument();
      });

      const runBtn = screen.getByRole("button", { name: /Bắt đầu hội chẩn AI/i });
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/council/result?caseId=201");
      });
    });
  });

  describe("3. /council/result Pure 7-Tier Decision Review Hierarchy (Spec v8 §7.7)", () => {
    it("renders all 7 hierarchy tiers in strict sequence without top metric-card clutter", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "result" });

      // Compact Case Header (no 6-card summary clutter)
      expect(screen.getByText("#201")).toBeInTheDocument();
      expect(screen.getByText("BN Nam 64T - Đau ngực không ổn định")).toBeInTheDocument();

      // Tier 1: Red flags & Escalation
      expect(screen.getByText(/1\. Cảnh báo đỏ & Leo thang/i)).toBeInTheDocument();
      expect(screen.getByText(/Cảnh báo an toàn thuốc \(DDI\)/i)).toBeInTheDocument();

      // Tier 2: Recommendation & Summary
      expect(screen.getByText(/2\. Khuyến nghị lâm sàng/i)).toBeInTheDocument();
      expect(screen.getByText(/Khuyến nghị tổng hợp/i)).toBeInTheDocument();
      expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();

      // Canonical sub-view anchors
      expect(screen.getByRole("link", { name: /Phân tích tín hiệu/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Chi tiết chuyên khoa/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Tra cứu trích dẫn/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Tổng hợp nghiên cứu/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Đào sâu ca bệnh/i })).toBeInTheDocument();

      // Tier 3: Consensus percentage & specialist perspectives
      expect(screen.getByText(/3\. Đồng thuận chuyên khoa/i)).toBeInTheDocument();
      expect(screen.getByText(/Đồng thuận:/i)).toHaveTextContent("90%");
      expect(screen.getByText(/Hội đồng đồng thuận cao về việc khởi đầu SGLT2i/i)).toBeInTheDocument();

      // Tier 4: Uncertainty & Divergence
      expect(screen.getByText(/4\. Độ không chắc chắn & Bất đồng/i)).toBeInTheDocument();
      expect(screen.getByText(/Thời điểm ngừng ACEi trước khi chuyển sang ARNI/i)).toBeInTheDocument();

      // Tier 5: Clinician Action (Handoff / Override / Pause / Export)
      expect(screen.getByText(/5\. Hành động của Bác sĩ/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Mời bác sĩ phụ trách xem lại/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Ghi đè quyết định/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Tạm dừng quy trình/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Xuất biên bản/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Mở trong Ghi chép SOAP/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Hội chẩn ca mới/i })).toBeInTheDocument();

      // Tier 6: Evidence & Citations
      expect(screen.getByText(/6\. Bằng chứng & Trích dẫn/i)).toBeInTheDocument();
      expect(screen.getByText(/2023 ESC Guidelines/i)).toBeInTheDocument();

      // Tier 7: Technical Details
      expect(screen.getByText(/7\. Chi tiết kỹ thuật/i)).toBeInTheDocument();
      expect(screen.getByText(/Tín hiệu nguy cơ theo quy tắc \(chỉ theo dõi\)/i)).toBeInTheDocument();
    });

    it("handles clinical oversight action: Pause deliberation workflow", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(submitCouncilOversight).mockResolvedValue({
        ...mockCaseAnalyzed,
        oversight_state: "paused",
      } as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();
      });

      const pauseBtn = screen.getByRole("button", { name: /Tạm dừng quy trình/i });
      fireEvent.click(pauseBtn);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Dữ liệu lâm sàng mới/i)).toBeInTheDocument();
      });

      const reasonTextarea = screen.getByPlaceholderText(/Dữ liệu lâm sàng mới/i);
      fireEvent.change(reasonTextarea, { target: { value: "Cần đợi kết quả xét nghiệm eGFR mới." } });

      const confirmBtn = screen.getByRole("button", { name: /Xác nhận/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(submitCouncilOversight).toHaveBeenCalledWith(201, {
          action: "pause",
          reason: "Cần đợi kết quả xét nghiệm eGFR mới.",
        });
      });
    });

    it("handles clinical oversight action: Specialist Handoff", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(submitCouncilOversight).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();
      });

      const handoffBtn = screen.getByRole("button", { name: /Mời bác sĩ phụ trách xem lại/i });
      fireEvent.click(handoffBtn);

      await waitFor(() => {
        expect(screen.getByText(/Mời chuyên khoa hội chẩn/i)).toBeInTheDocument();
      });

      const sendHandoffBtn = screen.getByRole("button", { name: /Gửi yêu cầu hội chẩn/i });
      fireEvent.click(sendHandoffBtn);

      await waitFor(() => {
        expect(submitCouncilOversight).toHaveBeenCalledWith(201, expect.objectContaining({
          action: "handoff",
        }));
      });
    });

    it("opens citation inspector modal when clicking an evidence source row", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/2023 ESC Guidelines/i)).toBeInTheDocument();
      });

      const citationRow = screen.getByText(/2023 ESC Guidelines/i);
      fireEvent.click(citationRow);

      await waitFor(() => {
        expect(screen.getByText(/Chi tiết nguồn y văn & Phân tích chất lượng/i)).toBeInTheDocument();
        expect(screen.getByText(/Đã kiểm chứng FIDES/i)).toBeInTheDocument();
        expect(screen.getByText(/Tại sao CLARA chọn nguồn này\?/i)).toBeInTheDocument();
        expect(screen.getByText(/Hạn chế & Lưu ý lâm sàng/i)).toBeInTheDocument();
      });
    });

    it("exports clinical council report as markdown download", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /Xuất biên bản/i });
      fireEvent.click(exportBtn);

      await waitFor(() => {
        expect(screen.getByText(/Đã xuất biên bản hội chẩn thành công/i)).toBeInTheDocument();
      });
    });
  });
});
