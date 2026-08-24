import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CouncilPage from "./page";
import CouncilNewPage from "./new/page";
import CouncilNewIntakePage from "./new/intake/page";
import CouncilNewSpecialistsPage from "./new/specialists/page";
import CouncilNewReviewPage from "./new/review/page";
import CouncilResultPage from "./result/page";
import CouncilAnalyzePage from "./analyze/page";
import CouncilCitationsPage from "./citations/page";
import CouncilDeepdivePage from "./deepdive/page";
import CouncilDetailsPage from "./details/page";
import CouncilResearchPage from "./research/page";
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
import { trackCouncilViewed, trackCouncilRun } from "@/lib/analytics/events";

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
    symptoms: ["Đau ngực"],
    labs: { Creatinine: "1.2 mg/dL" },
    medications: ["Metformin 1000mg"],
    history: "Tăng huyết áp",
    specialist_count: 3,
    specialists: ["cardiology", "endocrinology", "pharmacology"],
  },
  result: {
    final_recommendation: "Khuyến nghị phối hợp Empagliflozin 10mg và Sacubitril/Valsartan.",
    consensus: "Hội đồng đồng thuận cao.",
    conflicts: [],
    divergence: [],
    support_ratio: 0.9,
    conflict_count: 0,
    specialists: [
      { id: "cardiology", name: "Tim mạch", role: "cardiology", stance: "Đồng thuận" },
    ],
    citations: [],
  },
  created_at: "2026-08-24T08:00:00Z",
  updated_at: "2026-08-24T09:30:00Z",
};

const mockCaseDraft = {
  id: 202,
  title: "BN Nữ 52T - Rối loạn lipid máu",
  status: "intake_ready",
  request: {
    question: "",
    symptoms: [],
    labs: {},
    medications: [],
  },
  created_at: "2026-08-24T10:00:00Z",
  updated_at: "2026-08-24T10:00:00Z",
};

describe("Council Workflows (/council, /council/new/*, /council/result)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listCouncilCases).mockResolvedValue({
      items: [mockCaseAnalyzed, mockCaseDraft],
      total: 2,
    } as any);
    vi.mocked(getLatestCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
    vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
    vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
  });

  describe("1. /council Case Library", () => {
    it("renders case library and active resumable case for Clinical/Admin users", async () => {
      render(<CouncilPage />);

      await waitFor(() => {
        expect(screen.getByText("Thư viện ca hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "landing" });
      expect(screen.getByText("Ca đang thực hiện")).toBeInTheDocument();
      expect(screen.getAllByText(/BN Nam 64T - Đau ngực không ổn định/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Xem kết luận hội chẩn").length).toBeGreaterThanOrEqual(1);
    });

    it("filters cases by search query", async () => {
      render(<CouncilPage />);

      await waitFor(() => {
        expect(screen.getByText("Thư viện ca hội chẩn")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Tìm theo tiêu đề, #ID/i);
      fireEvent.change(searchInput, { target: { value: "Rối loạn lipid" } });

      await waitFor(() => {
        expect(screen.getByText(/BN Nữ 52T - Rối loạn lipid máu/i)).toBeInTheDocument();
      });
    });
  });

  describe("2. /council/new Step 1", () => {
    it("creates a new council case and navigates to intake step", async () => {
      vi.mocked(createCouncilCase).mockResolvedValue({
        id: 203,
        title: "BN Nam 70T - Tăng huyết áp kháng trị",
        status: "created",
      } as any);

      render(<CouncilNewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tạo ca trước khi phân tích")).toBeInTheDocument();
      });

      const titleInput = screen.getByLabelText(/Tiêu đề ca bệnh/i);
      fireEvent.change(titleInput, { target: { value: "BN Nam 70T - Tăng huyết áp kháng trị" } });

      const createBtn = screen.getByRole("button", { name: /Tạo ca mới/i });
      fireEvent.click(createBtn);

      await waitFor(() => {
        expect(createCouncilCase).toHaveBeenCalledWith({
          title: "BN Nam 70T - Tăng huyết áp kháng trị",
        });
        expect(setActiveCouncilCaseId).toHaveBeenCalledWith(203);
        expect(mockPush).toHaveBeenCalledWith("/council/new/intake?caseId=203");
      });
    });
  });

  describe("3. /council/new/intake Step 2", () => {
    it("loads intake draft and saves structured clinical input", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(updateCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewIntakePage />);

      await waitFor(() => {
        expect(screen.getByText("Thông tin ban đầu")).toBeInTheDocument();
      });

      const nextBtn = screen.getByRole("button", { name: /Sang bước 3/i });
      await waitFor(() => {
        expect(nextBtn).not.toBeDisabled();
      });
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(updateCouncilCase).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith("/council/new/specialists?caseId=201");
      });
    });
  });

  describe("4. /council/new/specialists Step 3", () => {
    it("selects specialists and advances to review", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(updateCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewSpecialistsPage />);

      await waitFor(() => {
        expect(screen.getAllByText("Chọn chuyên khoa").length).toBeGreaterThanOrEqual(1);
      });

      const nextBtn = screen.getByRole("button", { name: /Sang bước 4/i });
      await waitFor(() => {
        expect(nextBtn).not.toBeDisabled();
      });
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(updateCouncilCase).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith("/council/new/review?caseId=201");
      });
    });
  });

  describe("5. /council/new/review Step 4", () => {
    it("reviews preflight and runs council deliberation", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(runCouncilCaseById).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilNewReviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Rà soát trước khi chạy")).toBeInTheDocument();
      });

      const runBtn = screen.getByRole("button", { name: /Bắt đầu hội chẩn AI/i });
      await waitFor(() => {
        expect(runBtn).not.toBeDisabled();
      });
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(runCouncilCaseById).toHaveBeenCalledWith(201, expect.any(Object));
        expect(trackCouncilRun).toHaveBeenCalledWith({ specialistCount: 3 });
        expect(mockPush).toHaveBeenCalledWith("/council/result?caseId=201");
      });
    });
  });

  describe("6. /council/result Deliberation Result & Oversight", () => {
    it("renders deliberation result, final recommendations, and allows clinical oversight", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);
      vi.mocked(submitCouncilOversight).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResultPage />);

      await waitFor(() => {
        expect(screen.getByText(/Khuyến nghị phối hợp Empagliflozin 10mg/i)).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "result" });

      // Clinical oversight action: override / pause
      const pauseBtn = screen.getByRole("button", { name: /Tạm dừng quy trình/i });
      fireEvent.click(pauseBtn);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Xác nhận/i })).toBeInTheDocument();
      });
    });
  });

  describe("7. /council/analyze Signal Analysis Detail", () => {
    it("renders signal analysis with key signals and risk drivers", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilAnalyzePage />);

      await waitFor(() => {
        expect(screen.getByText("Bối cảnh quyết định hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "analyze" });
      expect(screen.getByText("Phân tích tín hiệu")).toBeInTheDocument();
    });
  });

  describe("8. /council/citations Citation Details", () => {
    it("renders citation focus view with literature links", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilCitationsPage />);

      await waitFor(() => {
        expect(screen.getByText("Bối cảnh quyết định hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "citations" });
      expect(screen.getByText("Tra cứu trích dẫn")).toBeInTheDocument();
    });
  });

  describe("9. /council/deepdive Expert Deep Dive", () => {
    it("renders deepdive breakdown sections", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilDeepdivePage />);

      await waitFor(() => {
        expect(screen.getByText("Bối cảnh quyết định hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "deepdive" });
      expect(screen.getByText("Đào sâu ca bệnh")).toBeInTheDocument();
    });
  });

  describe("10. /council/details Technical Specialist Logs", () => {
    it("renders specialist detailed deliberation logs", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilDetailsPage />);

      await waitFor(() => {
        expect(screen.getByText("Bối cảnh quyết định hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "details" });
      expect(screen.getByText("Chi tiết chuyên khoa")).toBeInTheDocument();
    });
  });

  describe("11. /council/research Evidence Synthesis", () => {
    it("renders research synthesis and highlights", async () => {
      vi.mocked(getActiveCouncilCaseId).mockReturnValue(201);
      vi.mocked(getCouncilCase).mockResolvedValue(mockCaseAnalyzed as any);

      render(<CouncilResearchPage />);

      await waitFor(() => {
        expect(screen.getByText("Bối cảnh quyết định hội chẩn")).toBeInTheDocument();
      });

      expect(trackCouncilViewed).toHaveBeenCalledWith({ view: "research" });
      expect(screen.getByText("Tổng hợp nghiên cứu")).toBeInTheDocument();
    });
  });
});
