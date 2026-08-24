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

describe("ClinicalOverviewLaunchpad Component (Spec v8 §7.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders contextual header with verified indicator without giant welcome banner", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Trung tâm Lâm sàng & Hội chẩn")).toBeInTheDocument();
    });

    expect(screen.getByText("Bác sĩ Lâm sàng")).toBeInTheDocument();
    expect(screen.getByText(/DrugBank v5.1.10 Verified/i)).toBeInTheDocument();
    expect(screen.queryByText(/KHÔNG GIAN LÂM SÀNG • COMMAND CENTER/i)).not.toBeInTheDocument();
  });

  it("renders Priority Active Case as first actionable object", async () => {
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

  it("renders Attention Queue above routine work when issues require action", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Hàng đợi cần chú ý & Cảnh báo an toàn")).toBeInTheDocument();
    });

    expect(screen.getByText("Có 2 thuốc sắp đến hạn kiểm tra liều dùng.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Xử lý ngay/i })).toHaveAttribute("href", "/medicines");
  });

  it("renders operational clinical rows without 4 monolithic card blocks", async () => {
    render(<ClinicalOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Ghi chép SOAP")).toBeInTheDocument();
    });

    expect(screen.getByText("Bằng chứng")).toBeInTheDocument();
    expect(screen.getByText("Tủ thuốc & Dược lý")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tra cứu phác đồ/i })).toHaveAttribute("href", "/evidence");
    expect(screen.getByRole("link", { name: /Kiểm tra tương tác DrugBank/i })).toHaveAttribute("href", "/medicines");
  });
});
