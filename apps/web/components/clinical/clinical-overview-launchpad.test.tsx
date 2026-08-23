import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ClinicalOverviewLaunchpad from "./clinical-overview-launchpad";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

const mockSystemDashboard = {
  generatedAt: "2026-08-23T10:45:00.000Z",
  user: { role: "doctor", subject: "BS. Nguyễn Văn A" },
  runtime: {
    apiStatus: "ok",
    mlStatus: "ok",
    mlReachable: true,
    requestCount: 42,
    errorCount: 0,
    avgLatencyMs: 85,
    errorRatePct: 0,
  },
  cabinet: {
    itemTotal: 12,
    expiredTotal: 0,
    expiringSoonTotal: 2,
    missingDosageTotal: 0,
  },
  sources: {
    enabled: 10,
    total: 12,
    lowContextThreshold: 0.6,
    flowFlags: {
      roleRouter: true,
      intentRouter: true,
      ruleVerification: true,
      nliModel: true,
      ragNli: true,
      ragReranker: true,
      ragGraphRag: true,
      deepseekFallback: true,
      scientificRetrieval: true,
      webRetrieval: true,
      fileRetrieval: true,
    },
    flowEnabledCount: 11,
  },
  research: {
    recentQueries: [{ id: "q1", query: "Tương tác Metformin và SGLT2i", createdAt: 1724400000000 }],
  },
  alerts: [
    {
      id: "alt-1",
      severity: "warning" as const,
      message: "Có 2 thuốc sắp đến hạn kiểm tra liều dùng.",
      href: "/medicines",
    },
  ],
  tasks: [],
};

const mockCouncilCase = {
  id: 104,
  title: "Đánh giá chức năng thận và phác đồ ĐTĐ tuýp 2",
  status: "waiting_review",
  intake_mode: "transcript",
  transcript: "Bệnh nhân nam 62 tuổi có tiền sử ĐTĐ tuýp 2 kèm suy thận nhẹ...",
  created_at: "2026-08-23T08:30:00.000Z",
  updated_at: "2026-08-23T10:30:00.000Z",
};

vi.mock("@/lib/system", () => ({
  getSystemDashboard: vi.fn(async () => mockSystemDashboard),
  normalizeSystemDashboard: vi.fn((data) => data),
}));

vi.mock("@/lib/council", () => ({
  getActiveCouncilCaseId: vi.fn(() => 104),
  getLatestCouncilCase: vi.fn(async () => mockCouncilCase),
}));

describe("ClinicalOverviewLaunchpad Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Clinician Command Center hero banner and title", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Trung tâm Lâm sàng & Hội chẩn")).toBeInTheDocument();
    });

    expect(screen.getByText(/KHÔNG GIAN LÂM SÀNG • COMMAND CENTER/i)).toBeInTheDocument();
    expect(screen.getByText(/DrugBank v5.1.10 Verified/i)).toBeInTheDocument();
  });

  it("renders Quick Case Resumption with case status chips and last updated time", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Ca lâm sàng đang thực hiện")).toBeInTheDocument();
    });

    expect(screen.getByText("#104")).toBeInTheDocument();
    expect(screen.getByText("Cần rà soát")).toBeInTheDocument();
    expect(screen.getByText("Đánh giá chức năng thận và phác đồ ĐTĐ tuýp 2")).toBeInTheDocument();
    expect(screen.getByText(/Lần cập nhật cuối:/i)).toBeInTheDocument();
    const resumeLinks = screen.getAllByRole("link", { name: /Tiếp tục ca này/i });
    expect(resumeLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("renders all 4 Primary Clinical Tool cards with appropriate links and badges", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("4 công cụ lâm sàng cốt lõi")).toBeInTheDocument();
    });

    expect(screen.getByText("Hội chẩn AI")).toBeInTheDocument();
    expect(screen.getAllByText("Ghi chép SOAP").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Bằng chứng")).toBeInTheDocument();
    expect(screen.getByText("Tra cứu lâm sàng")).toBeInTheDocument();

    expect(screen.getByText("AI Council")).toBeInTheDocument();
    expect(screen.getByText("SOAP Notes")).toBeInTheDocument();
    expect(screen.getByText("Living Evidence")).toBeInTheDocument();
    expect(screen.getByText("Decision Support")).toBeInTheDocument();

    // Check highlights
    expect(screen.getByText("Triage đa chuyên khoa")).toBeInTheDocument();
    expect(screen.getByText("Bệnh án SOAP chuẩn")).toBeInTheDocument();
    expect(screen.getByText("Đồ thị tri thức GLHS")).toBeInTheDocument();
    expect(screen.getByText("Chỉnh liều eGFR")).toBeInTheDocument();
  });

  it("renders Real-time server alerts and DrugBank updates section", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Cảnh báo máy chủ & Cập nhật Dược lý")).toBeInTheDocument();
    });

    expect(screen.getByText("Cảnh báo an toàn lâm sàng")).toBeInTheDocument();
    expect(screen.getByText("Có 2 thuốc sắp đến hạn kiểm tra liều dùng.")).toBeInTheDocument();

    expect(screen.getByText("Cơ sở dữ liệu Dược & Tri thức")).toBeInTheDocument();
    expect(screen.getByText("Thuốc đang theo dõi")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Thuốc sắp đến hạn")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /Kiểm tra tương tác DrugBank/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tủ thuốc lâm sàng/i })).toBeInTheDocument();
  });
});
