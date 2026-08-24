import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import EcosystemCenterPage from "./page";
import { getSystemEcosystem, normalizeSystemEcosystem } from "@/lib/system";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/system", () => ({
  getSystemEcosystem: vi.fn(),
  normalizeSystemEcosystem: vi.fn((data) => data),
  isAccessDeniedError: vi.fn((err: any) => err?.status === 403),
}));

const mockEcosystem = {
  generatedAt: "2026-08-24T12:00:00Z",
  summary: {
    partnersTotal: 6,
    partnersDown: 0,
    trustLowCount: 0,
    criticalAlertCount: 0,
  },
  partnerHealth: [
    {
      partner: "Bệnh viện Chợ Rẫy",
      status: "healthy",
      latencyMs: 45,
      errorRatePct: 0.05,
      lastCheck: "2026-08-24T11:55:00Z",
    },
    {
      partner: "Bệnh viện Đại học Y Dược",
      status: "healthy",
      latencyMs: 38,
      errorRatePct: 0.02,
      lastCheck: "2026-08-24T11:55:00Z",
    },
  ],
  dataTrustScores: [
    {
      source: "Dược thư Quốc gia Việt Nam",
      trustScore: 98,
      freshnessHours: 12,
      driftRisk: "low",
      lastRefresh: "2026-08-24T06:00:00Z",
    },
    {
      source: "DrugBank Global",
      trustScore: 95,
      freshnessHours: 24,
      driftRisk: "low",
      lastRefresh: "2026-08-24T00:00:00Z",
    },
  ],
  federationAlerts: [
    {
      id: "ALT-2026-001",
      severity: "info",
      source: "Health Data Exchange Hub",
      message: "Hoàn tất đồng bộ danh mục ICD-10 và ATC mới nhất từ Bộ Y tế.",
      acknowledged: true,
      createdAt: "2026-08-24T08:00:00Z",
    },
  ],
};

describe("EcosystemCenterPage (/dashboard/ecosystem)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSystemEcosystem).mockResolvedValue(mockEcosystem);
  });

  it("loads and renders ecosystem summary cards and partner health status", async () => {
    render(<EcosystemCenterPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Bệnh viện Chợ Rẫy").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Bệnh viện Đại học Y Dược").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText("Dược thư Quốc gia Việt Nam").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("DrugBank Global").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Hoàn tất đồng bộ danh mục ICD-10 và ATC mới nhất từ Bộ Y tế.")).toBeInTheDocument();
  });

  it("refreshes snapshot when refresh button is clicked", async () => {
    render(<EcosystemCenterPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Bệnh viện Chợ Rẫy").length).toBeGreaterThanOrEqual(1);
    });

    const refreshButton = screen.getByRole("button", { name: /Làm mới ảnh chụp/i });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(getSystemEcosystem).toHaveBeenCalledTimes(2);
    });
  });
});
