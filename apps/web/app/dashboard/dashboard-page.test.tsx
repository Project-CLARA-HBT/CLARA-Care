import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "./page";
import { getRole } from "@/lib/auth-store";
import { getSystemDashboard } from "@/lib/system";

const mockReplace = vi.fn();
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
    push: mockPush,
    pathname: "/dashboard",
  }),
}));

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
  getRole: vi.fn(() => "doctor"),
}));

describe("DashboardPage Role-Adaptive Home (Spec v5 Section 6.55)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRole).mockReturnValue("doctor");
    vi.mocked(getSystemDashboard).mockResolvedValue(mockSystemDashboard);
  });

  it("redirects admin role immediately to /admin/overview", async () => {
    vi.mocked(getRole).mockReturnValue("admin");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/admin/overview");
    });
  });

  it("redirects normal role immediately to /today", async () => {
    vi.mocked(getRole).mockReturnValue("normal");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/today");
    });
  });

  it("renders Clinical Overview Launchpad for doctor role", async () => {
    vi.mocked(getRole).mockReturnValue("doctor");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Trung tâm Lâm sàng & Hội chẩn/i).length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText(/DrugBank v5.1.10 Verified/i)).toBeInTheDocument();
    expect(screen.getByText("Ca lâm sàng đang thực hiện")).toBeInTheDocument();
    expect(screen.getByText("#105")).toBeInTheDocument();
    expect(screen.getByText("Hội chẩn suy tim phân suất tống máu giảm")).toBeInTheDocument();
    expect(screen.getByText("Tiếp tục ca này")).toBeInTheDocument();

    // Operational Rows
    expect(screen.getByText("Ghi chép SOAP")).toBeInTheDocument();
    expect(screen.getByText("Bằng chứng")).toBeInTheDocument();
    expect(screen.getByText("Tủ thuốc & Dược lý")).toBeInTheDocument();
    expect(screen.getByText("Tra cứu lâm sàng →")).toBeInTheDocument();

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("renders Research Overview Launchpad for researcher role", async () => {
    vi.mocked(getRole).mockReturnValue("researcher");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Tra cứu y khoa/i).length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("GLHS Knowledge Graph & Living Evidence")).toBeInTheDocument();
    expect(screen.getByText("Câu hỏi nghiên cứu gần nhất")).toBeInTheDocument();

    // Routine Work & Links
    expect(screen.getByText("Bằng chứng sống (Living Evidence)")).toBeInTheDocument();
    expect(screen.getByText("Kho nguồn nghiên cứu (Source Hub)")).toBeInTheDocument();
    expect(screen.getByText("Giám sát biến động y văn")).toBeInTheDocument();

    // Links to /evidence and /chat
    expect(screen.getByRole("link", { name: /Tra cứu y khoa \(Chat\)/i })).toHaveAttribute("href", "/chat");
    expect(screen.getAllByRole("link", { name: /Bằng chứng sống/i })[0]).toHaveAttribute("href", "/evidence");

    // Recent queries
    expect(screen.getByText("Phác đồ ĐTĐ tuýp 2 suy thận")).toBeInTheDocument();

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("does not render generic monolithic card dashboard fallback", async () => {
    vi.mocked(getRole).mockReturnValue("doctor");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Trung tâm Lâm sàng & Hội chẩn/i).length).toBeGreaterThanOrEqual(1);
    });

    // Verify monolithic legacy widgets are not present
    expect(screen.queryByText("TRUNG TÂM ĐIỀU HÀNH & QUẢN TRỊ HỆ THỐNG")).not.toBeInTheDocument();
    expect(screen.queryByText("4 Phân hệ Trọng yếu Sẵn sàng")).not.toBeInTheDocument();
  });
});
