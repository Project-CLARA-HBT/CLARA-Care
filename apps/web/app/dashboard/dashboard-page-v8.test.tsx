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
  tasks: [],
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

describe("DashboardPage Spec v8 §7.1 Role Adapter Architecture", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRole).mockReturnValue("doctor");
    vi.mocked(getSystemDashboard).mockResolvedValue(mockSystemDashboard);
  });

  it("1. admin role immediately redirects to canonical /admin/overview without rendering duplicate cards", async () => {
    vi.mocked(getRole).mockReturnValue("admin");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/admin/overview");
    });
  });

  it("2. normal role immediately redirects to /today", async () => {
    vi.mocked(getRole).mockReturnValue("normal");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/today");
    });
  });

  it("3. doctor role renders ClinicalOverview with next action first (no greeting hero, no 4 core cards)", async () => {
    vi.mocked(getRole).mockReturnValue("doctor");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Ca lâm sàng đang thực hiện")).toBeInTheDocument();
    });

    // Primary Next Action is first
    expect(screen.getByText("#105")).toBeInTheDocument();
    expect(screen.getByText("Hội chẩn suy tim phân suất tống máu giảm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tiếp tục ca này/i })).toHaveAttribute("href", "/council/new/intake?caseId=105");

    // Attention Queue appears above routine work when issues require action
    expect(screen.getByText("Hàng đợi cần chú ý & Cảnh báo an toàn")).toBeInTheDocument();
    expect(screen.getByText("Cần kiểm tra tương tác thuốc trong tủ.")).toBeInTheDocument();

    // No giant welcome greeting or monolithic tool cards
    expect(screen.queryByText(/Xin chào/i)).not.toBeInTheDocument();
    expect(screen.queryByText("4 công cụ lâm sàng cốt lõi")).not.toBeInTheDocument();

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("4. researcher role renders ResearchOverview with active question and source surveillance", async () => {
    vi.mocked(getRole).mockReturnValue("researcher");

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Tra cứu y khoa/i).length).toBeGreaterThanOrEqual(1);
    });

    // Active research inquiry first
    expect(screen.getByText("Câu hỏi nghiên cứu gần nhất")).toBeInTheDocument();
    expect(screen.getByText("Phác đồ ĐTĐ tuýp 2 suy thận")).toBeInTheDocument();

    // Routine Work & Links
    expect(screen.getByText("Bằng chứng sống (Living Evidence)")).toBeInTheDocument();
    expect(screen.getByText("Kho nguồn nghiên cứu (Source Hub)")).toBeInTheDocument();
    expect(screen.getByText("Giám sát biến động y văn")).toBeInTheDocument();

    // No giant welcome greeting
    expect(screen.queryByText(/Xin chào/i)).not.toBeInTheDocument();
    expect(screen.queryByText("4 công cụ nghiên cứu & y văn cốt lõi")).not.toBeInTheDocument();

    expect(mockReplace).not.toHaveBeenCalled();
  });
});
