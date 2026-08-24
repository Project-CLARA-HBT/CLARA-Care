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
  tasks: [
    {
      id: "task-res-1",
      title: "Rà soát tài liệu mới từ Bộ Y tế",
      detail: "Cập nhật quyết định 2026 về phác đồ đái tháo đường.",
      tone: "warn" as const,
      href: "/evidence",
      count: 1,
    },
  ],
};

vi.mock("@/lib/system", () => ({
  getSystemDashboard: vi.fn(async () => mockSystemDashboard),
  normalizeSystemDashboard: vi.fn((data) => data),
}));

describe("ResearchOverviewLaunchpad Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSystemDashboard).mockResolvedValue(mockSystemDashboard);
  });

  it("renders Research Command Center banner with status and source metrics", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Trung tâm Nghiên cứu & Bằng chứng Y học")).toBeInTheDocument();
    });

    expect(screen.getByText("GLHS Knowledge Graph & Living Evidence")).toBeInTheDocument();
    expect(screen.getByText(/12 nguồn tri thức sẵn sàng/i)).toBeInTheDocument();
  });

  it("renders all 4 core research tool cards with highlights", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("4 công cụ nghiên cứu & y văn cốt lõi")).toBeInTheDocument();
    });

    expect(screen.getByText("Bằng chứng sống (Living Evidence)")).toBeInTheDocument();
    expect(screen.getByText("Tra cứu y khoa (AI Chat)")).toBeInTheDocument();
    expect(screen.getByText("Kho nguồn nghiên cứu (Source Hub)")).toBeInTheDocument();
    expect(screen.getByText("Giám sát biến động y văn")).toBeInTheDocument();

    expect(screen.getByText("Living Evidence")).toBeInTheDocument();
    expect(screen.getByText("Research Chat")).toBeInTheDocument();
    expect(screen.getByText("Corpus Ingestion")).toBeInTheDocument();
    expect(screen.getByText("Surveillance")).toBeInTheDocument();

    expect(screen.getByText("Phác đồ Bộ Y tế & Quốc tế")).toBeInTheDocument();
    expect(screen.getByText("Truy xuất có viện dẫn nguồn")).toBeInTheDocument();
  });

  it("renders recent research queries and task action cleanly", async () => {
    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Hiệu quả SGLT2i trên bệnh thận mạn")).toBeInTheDocument();
      expect(screen.getByText("So sánh GLP-1 RA và DPP-4i")).toBeInTheDocument();
    });

    expect(screen.getByText("Rà soát tài liệu mới từ Bộ Y tế")).toBeInTheDocument();
    expect(screen.getByText("Có 2 nguồn PubMed mới cần đồng bộ.")).toBeInTheDocument();
  });

  it("renders error state when dashboard data fails to load", async () => {
    vi.mocked(getSystemDashboard).mockRejectedValueOnce(new Error("Network failure"));

    render(<ResearchOverviewLaunchpad />);

    await waitFor(() => {
      expect(screen.getByText("Chưa tải được tổng quan")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Thử lại/i })).toBeInTheDocument();
  });
});
