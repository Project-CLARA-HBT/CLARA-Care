import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ResearchOverviewLaunchpad from "./research-overview-launchpad";
import { getSystemDashboard } from "@/lib/system";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

const mockSystemDashboard = {
  generatedAt: "2026-08-23T10:45:00.000Z",
  user: { role: "researcher", subject: "researcher@clara.care" },
  runtime: {
    apiStatus: "ok",
    mlStatus: "ok",
    mlReachable: true,
    requestCount: 120,
    errorCount: 0,
    avgLatencyMs: 85,
    errorRatePct: 0,
  },
  cabinet: {
    itemTotal: 4,
    expiredTotal: 0,
    expiringSoonTotal: 0,
    missingDosageTotal: 0,
  },
  sources: {
    enabled: 12,
    total: 13,
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
    recentQueries: [
      { id: "q1", query: "Hiệu quả SGLT2i trên bệnh thận mạn", createdAt: 1724400000000 },
      { id: "q2", query: "So sánh GLP-1 RA và DPP-4i", createdAt: 1724390000000 },
    ],
  },
  alerts: [
    {
      id: "alert-res-1",
      severity: "warning" as const,
      message: "Có 2 nguồn PubMed mới cần đồng bộ.",
      href: "/research/source-hub",
    },
  ],
  tasks: [],
};

vi.mock("@/lib/system", () => ({
  getSystemDashboard: vi.fn(async () => mockSystemDashboard),
  normalizeSystemDashboard: vi.fn((data) => data),
}));

describe("ResearchOverviewLaunchpad Component (Spec v8 §7.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSystemDashboard).mockResolvedValue(mockSystemDashboard);
  });

  it("renders contextual header without giant welcome banner", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Nhà nghiên cứu Y học")).toBeInTheDocument();
    });

    expect(screen.getByText("GLHS Knowledge Graph & Living Evidence")).toBeInTheDocument();
  });

  it("renders active research inquiry as primary next action", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Câu hỏi nghiên cứu gần nhất")).toBeInTheDocument();
    });

    expect(screen.getByText("Hiệu quả SGLT2i trên bệnh thận mạn")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tiếp tục nghiên cứu/i })).toHaveAttribute("href", "/evidence");
  });

  it("renders Attention Queue when source alerts exist", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Hàng đợi cần chú ý & Cảnh báo nguồn")).toBeInTheDocument();
    });

    expect(screen.getByText("Có 2 nguồn PubMed mới cần đồng bộ.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Xử lý ngay/i })).toHaveAttribute("href", "/research/source-hub");
  });

  it("renders routine research rows without 4 monolithic card blocks", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Bằng chứng sống (Living Evidence)")).toBeInTheDocument();
    });

    expect(screen.getByText("Kho nguồn nghiên cứu (Source Hub)")).toBeInTheDocument();
    expect(screen.getByText("Giám sát biến động y văn")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Tra cứu y khoa \(Chat\)/i })).toHaveAttribute("href", "/chat");
  });

  it("renders error state when dashboard data fails to load", async () => {
    vi.mocked(getSystemDashboard).mockRejectedValueOnce(new Error("Network failure"));

    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Chưa tải được tổng quan hoặc máy chủ ngoại tuyến")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Thử lại/i })).toBeInTheDocument();
  });
});
