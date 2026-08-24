import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminClinicalAnalyticsPage from "@/app/admin/analytics/clinical/page";
import type { ClinicalAnalytics } from "@/lib/analytics-dashboard";

const trackAdminSurfaceViewed = vi.fn();
const mockRole = { role: "admin" };

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: (props: { view: string }) => trackAdminSurfaceViewed(props),
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => mockRole.role,
}));

const sampleAnalytics: ClinicalAnalytics = {
  generated_at: "2026-08-24T00:00:00.000Z",
  range: ["2026-07-25", "2026-08-24"],
  verdicts: {
    verified: 24,
    partially_verified: 6,
    contested: 2,
    unsupported: 1,
    blocked_claims: 5,
  },
  ddi_severity: { low: 10, medium: 8, high: 4, critical: 2 },
  router_confidence: { high: 18, medium: 10, low: 3 },
  fallback_rate_pct: 4.2,
  latency: [{ tier: "tier1", p50_ms: 110, p90_ms: 280, p99_ms: 490 }],
  has_data: true,
};

vi.mock("@/lib/analytics-dashboard", async () => {
  const actual = await vi.importActual<typeof import("@/lib/analytics-dashboard")>(
    "@/lib/analytics-dashboard"
  );
  return {
    ...actual,
    getClinicalAnalytics: vi.fn(async () => sampleAnalytics),
  };
});

describe("AdminClinicalAnalyticsPage (/admin/analytics/clinical - Spec v5 Section 6.64)", () => {
  beforeEach(() => {
    trackAdminSurfaceViewed.mockReset();
    mockRole.role = "admin";
    window.localStorage.setItem("clara_ui_language", "vi");
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders AdminShell with clinical-analytics active tab and ClinicalAnalyticsPanel", async () => {
    render(<AdminClinicalAnalyticsPage />);

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Phân tích lâm sàng")).toBeInTheDocument();
      expect(screen.getByText("Phân bố phán quyết FIDES")).toBeInTheDocument();
    });

    // Detailed pipeline telemetry shown for admin
    expect(screen.getByTestId("clinical-pipeline-telemetry")).toBeInTheDocument();
    expect(screen.getByText("Độ trễ theo tier (percentile)")).toBeInTheDocument();
    expect(screen.getByText("Độ tin cậy của Router")).toBeInTheDocument();
  });
});
