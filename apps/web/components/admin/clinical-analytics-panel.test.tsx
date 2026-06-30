import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import type { ClinicalAnalytics } from "@/lib/analytics-dashboard";
import type { UserRole } from "@/lib/auth-store";

/**
 * Feature: product-polish-analytics — task 9.6 (Integrate Admin surfaces).
 *
 * Verifies that on the new Clinical_Analytics dashboard:
 *  - a named Admin product event is emitted on open (Req 9.1); and
 *  - the detailed pipeline-health telemetry (per-tier latency percentiles and
 *    router confidence) is wrapped in the role-gated TelemetryPanel so it is
 *    visible ONLY to Admin_Users (Req 4.3, Property 11).
 *
 * The data fetch and role lookup are mocked so the panel can render its
 * populated state synchronously without a real API/session.
 */

const trackAdminSurfaceViewed = vi.fn();
let mockRole: UserRole = "admin";

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: (props: { view: string }) => trackAdminSurfaceViewed(props)
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => mockRole
}));

const sampleAnalytics: ClinicalAnalytics = {
  generated_at: "2024-05-01T00:00:00.000Z",
  range: ["2024-04-01", "2024-05-01"],
  verdicts: {
    verified: 12,
    partially_verified: 3,
    contested: 1,
    unsupported: 2,
    blocked_claims: 4
  },
  ddi_severity: { low: 5, medium: 4, high: 2, critical: 1 },
  router_confidence: { high: 9, medium: 5, low: 2 },
  fallback_rate_pct: 7.5,
  latency: [{ tier: "tier1", p50_ms: 120, p90_ms: 320, p99_ms: 540 }],
  has_data: true
};

vi.mock("@/lib/analytics-dashboard", async () => {
  const actual = await vi.importActual<typeof import("@/lib/analytics-dashboard")>(
    "@/lib/analytics-dashboard"
  );
  return {
    ...actual,
    getClinicalAnalytics: vi.fn(async () => sampleAnalytics)
  };
});

import ClinicalAnalyticsPanel from "@/components/admin/clinical-analytics-panel";

beforeEach(() => {
  trackAdminSurfaceViewed.mockReset();
  mockRole = "admin";
});

afterEach(() => {
  cleanup();
});

describe("ClinicalAnalyticsPanel (Feature: product-polish-analytics, task 9.6)", () => {
  it("emits the named clinical-analytics Admin event on open (Req 9.1)", async () => {
    render(<ClinicalAnalyticsPanel />);
    await waitFor(() => {
      expect(trackAdminSurfaceViewed).toHaveBeenCalledWith({ view: "clinical_analytics" });
    });
  });

  it("shows the detailed pipeline telemetry to an Admin_User (Req 4.3)", async () => {
    mockRole = "admin";
    render(<ClinicalAnalyticsPanel />);

    expect(await screen.findByTestId("clinical-pipeline-telemetry")).toBeTruthy();
    // The latency-percentile section (raw pipeline telemetry) is rendered.
    expect(screen.getByText("Độ trễ theo tier (percentile)")).toBeTruthy();
    expect(screen.getByText("Độ tin cậy của Router")).toBeTruthy();
  });

  it("hides the detailed pipeline telemetry from a non-admin role (Req 4.3)", async () => {
    mockRole = "normal";
    render(<ClinicalAnalyticsPanel />);

    // Wait for the populated state (the clinical summary still renders).
    expect(await screen.findByText("Phân bố phán quyết FIDES")).toBeTruthy();
    // The raw pipeline-health telemetry is gated away for non-admins.
    expect(screen.queryByTestId("clinical-pipeline-telemetry")).toBeNull();
    expect(screen.queryByText("Độ trễ theo tier (percentile)")).toBeNull();
  });
});
