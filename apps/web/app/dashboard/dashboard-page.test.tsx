import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "./page";

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
    requestCount: 50,
    errorCount: 0,
    avgLatencyMs: 90,
    errorRatePct: 0,
  },
  cabinet: {
    itemTotal: 8,
    expiredTotal: 0,
    expiringSoonTotal: 1,
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
    recentQueries: [{ id: "q1", query: "Phác đồ ĐTĐ tuýp 2 suy thận", createdAt: 1724400000000 }],
  },
  alerts: [
    {
      id: "alert-warn",
      severity: "warning" as const,
      message: "Cần kiểm tra tương tác thuốc trong tủ.",
      href: "/medicines",
    },
  ],
  tasks: [
    {
      id: "task-1",
      title: "Rà soát thuốc sắp hết hạn",
      detail: "Có 1 thuốc sắp hết hạn cần kiểm tra lại đơn.",
      tone: "warn" as const,
      href: "/medicines",
      count: 1,
    },
  ],
};

const mockCouncilCase = {
  id: 105,
  title: "Hội chẩn suy tim phân suất tống máu giảm",
  status: "waiting_review",
  intake_mode: "structured",
  transcript: "",
  created_at: "2026-08-23T09:00:00.000Z",
  updated_at: "2026-08-23T11:00:00.000Z",
};

vi.mock("@/lib/system", () => ({
  getSystemDashboard: vi.fn(async () => mockSystemDashboard),
  normalizeSystemDashboard: vi.fn((data) => data),
}));

vi.mock("@/lib/council", () => ({
  getActiveCouncilCaseId: vi.fn(() => 105),
  getLatestCouncilCase: vi.fn(async () => mockCouncilCase),
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "doctor",
}));

describe("DashboardPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Clinician Command Center banner for doctor role", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Trung tâm Lâm sàng & Hội chẩn/i).length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText(/DrugBank v5.1.10 Verified/i)).toBeInTheDocument();
  });

  it("renders Quick Case Resumption card with status chip and last updated time", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Ca lâm sàng đang thực hiện")).toBeInTheDocument();
    });

    expect(screen.getByText("#105")).toBeInTheDocument();
    expect(screen.getByText("Cần rà soát")).toBeInTheDocument();
    expect(screen.getByText("Hội chẩn suy tim phân suất tống máu giảm")).toBeInTheDocument();
    expect(screen.getByText(/Lần cập nhật cuối:/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tiếp tục ca này/i })).toBeInTheDocument();
  });

  it("renders all 4 Primary Clinical Tools cards", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("4 công cụ lâm sàng cốt lõi")).toBeInTheDocument();
    });

    expect(screen.getByText("Hội chẩn AI (Council)")).toBeInTheDocument();
    expect(screen.getByText("Ghi chép khám (Scribe)")).toBeInTheDocument();
    expect(screen.getByText("Bằng chứng sống (Living Evidence)")).toBeInTheDocument();
    expect(screen.getByText("Tra cứu lâm sàng (Chat)")).toBeInTheDocument();

    expect(screen.getByText("AI Council")).toBeInTheDocument();
    expect(screen.getByText("SOAP Notes")).toBeInTheDocument();
    expect(screen.getByText("Living Evidence")).toBeInTheDocument();
    expect(screen.getByText("Decision Support")).toBeInTheDocument();
  });

  it("renders Real-time server alerts and DrugBank updates section", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Cảnh báo máy chủ & Cập nhật Dược lý")).toBeInTheDocument();
    });

    expect(screen.getByText("Cảnh báo máy chủ & An toàn")).toBeInTheDocument();
    expect(screen.getByText("Cần kiểm tra tương tác thuốc trong tủ.")).toBeInTheDocument();

    expect(screen.getByText("Cơ sở dữ liệu Dược & Tri thức")).toBeInTheDocument();
    expect(screen.getAllByText("Thuốc đang theo dõi").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("Thuốc sắp đến hạn")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders recent queries activity cleanly", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Phác đồ ĐTĐ tuýp 2 suy thận")).toBeInTheDocument();
    });
  });
});
