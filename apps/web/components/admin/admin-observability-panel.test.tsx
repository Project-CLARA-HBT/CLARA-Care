import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import type {
  ApiHealthRawResponse,
  ControlTowerConfig,
  SystemDependenciesRawResponse,
  SystemMetricsRawResponse
} from "@/lib/system";

/**
 * Feature: clara-admin-observability — task 5.5 (Complete the Observability
 * dashboard async states).
 *
 * Verifies the Observability panel:
 *  - renders the populated state and surfaces the additive per-route latency
 *    percentiles (p50/p90/p99) from the `/system/metrics` `percentiles` map
 *    (Req 5.2, 5.6);
 *  - degrades gracefully to the average-only baseline when the percentiles key
 *    is absent (flag off) (Req 5.6); and
 *  - renders the error state with a sanitized message that never leaks an
 *    upstream stack trace (Req 5.6, via `sanitizeUpstreamError`).
 *
 * The four data fetches are mocked (the real normalizers are kept) and the
 * canvas/SVG chart primitives are stubbed so the panel renders synchronously
 * without a real API/session or a charting runtime.
 */

const trackAdminSurfaceViewed = vi.fn();

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: (props: { view: string }) => trackAdminSurfaceViewed(props)
}));

// Stub the futuristic chart primitives — they are irrelevant to the async-state
// + percentile logic under test and pull in a canvas/SVG runtime.
vi.mock("@/components/dashboard/futuristic-charts", () => ({
  ConduitFlowLine: () => <div data-testid="chart-conduit" />,
  MatrixHeatmapMini: () => <div data-testid="chart-matrix" />,
  NeonAreaChart: () => <div data-testid="chart-area" />,
  RadarPulseChart: () => <div data-testid="chart-radar" />,
  SegmentRingGauge: () => <div data-testid="chart-gauge" />
}));

const getApiHealth = vi.fn<[], Promise<ApiHealthRawResponse>>();
const getSystemMetrics = vi.fn<[], Promise<SystemMetricsRawResponse>>();
const getSystemDependencies = vi.fn<[], Promise<SystemDependenciesRawResponse>>();
const getControlTowerConfig = vi.fn<[], Promise<ControlTowerConfig>>();

vi.mock("@/lib/system", async () => {
  const actual = await vi.importActual<typeof import("@/lib/system")>("@/lib/system");
  return {
    ...actual,
    getApiHealth: () => getApiHealth(),
    getSystemMetrics: () => getSystemMetrics(),
    getSystemDependencies: () => getSystemDependencies(),
    getControlTowerConfig: () => getControlTowerConfig(),
    acknowledgeObservabilityAlert: vi.fn(async () => ({
      acknowledged: true,
      alert: { alert_id: "x" }
    }))
  };
});

import AdminObservabilityPanel from "@/components/admin/admin-observability-panel";

const sampleHealth: ApiHealthRawResponse = { status: "ok", message: "All systems nominal" };
const sampleDependencies: SystemDependenciesRawResponse = {
  ml_reachable: true,
  ml_status: "reachable"
};

function makeConfig(): ControlTowerConfig {
  return {
    rag_sources: [
      { id: "s1", name: "PubMed", enabled: true, priority: 1, weight: 1, category: "scientific" }
    ],
    rag_flow: {
      role_router_enabled: true,
      intent_router_enabled: true,
      rule_verification_enabled: true,
      nli_model_enabled: true,
      rag_reranker_enabled: true,
      rag_nli_enabled: true,
      rag_graphrag_enabled: true,
      deepseek_fallback_enabled: false,
      low_context_threshold: 0.2,
      scientific_retrieval_enabled: true,
      web_retrieval_enabled: false,
      file_retrieval_enabled: false,
      llm_provider: "deepseek",
      llm_base_url: "",
      llm_model: "",
      llm_api_key: ""
    },
    careguard_runtime: { external_ddi_enabled: false }
  };
}

beforeEach(() => {
  trackAdminSurfaceViewed.mockReset();
  getApiHealth.mockReset();
  getSystemMetrics.mockReset();
  getSystemDependencies.mockReset();
  getControlTowerConfig.mockReset();

  getApiHealth.mockResolvedValue(sampleHealth);
  getSystemDependencies.mockResolvedValue(sampleDependencies);
  getControlTowerConfig.mockResolvedValue(makeConfig());
});

afterEach(() => {
  cleanup();
});

describe("AdminObservabilityPanel (Feature: clara-admin-observability, task 5.5)", () => {
  it("surfaces per-route p50/p90/p99 percentiles when the metrics payload includes them (Req 5.2, 5.6)", async () => {
    getSystemMetrics.mockResolvedValue({
      request_count: 1200,
      error_count: 4,
      avg_latency_ms: 180,
      percentiles: {
        "GET /system/metrics": { p50_ms: 12, p90_ms: 34, p99_ms: 90 }
      }
    });

    render(<AdminObservabilityPanel />);

    // Populated state + percentiles table rendered.
    expect(await screen.findByText("Độ trễ theo tuyến (p50 / p90 / p99)")).toBeTruthy();
    expect(screen.getByText("Đang bật")).toBeTruthy();
    expect(screen.getByText("GET /system/metrics")).toBeTruthy();
    // p50/p90/p99 values are formatted (vi-VN, ms suffix).
    expect(screen.getByText("12ms")).toBeTruthy();
    expect(screen.getByText("34ms")).toBeTruthy();
    expect(screen.getByText("90ms")).toBeTruthy();
  });

  it("degrades to the average-only baseline when the percentiles key is absent (Req 5.6)", async () => {
    getSystemMetrics.mockResolvedValue({
      request_count: 1200,
      error_count: 4,
      avg_latency_ms: 180
      // no `percentiles` key — flag off
    });

    render(<AdminObservabilityPanel />);

    expect(await screen.findByText("Chưa bật")).toBeTruthy();
    expect(
      screen.getByText(/Phân vị độ trễ theo tuyến chưa được bật/)
    ).toBeTruthy();
  });

  it("renders the error state with a sanitized message and no upstream stack trace (Req 5.6)", async () => {
    getSystemMetrics.mockRejectedValue(
      new Error(
        'Traceback (most recent call last): File "/srv/clara_api/main.py", line 42, in handler raise RuntimeError("boom") at http://internal-ml:9000'
      )
    );

    render(<AdminObservabilityPanel />);

    expect(await screen.findByText("Không tải được dữ liệu quan trắc")).toBeTruthy();
    // The calm fallback copy is shown instead of the raw technical error.
    expect(screen.getByText("Hệ thống đang bận, vui lòng thử lại.")).toBeTruthy();
    // The raw stack trace / internal URL must never reach the DOM.
    expect(screen.queryByText(/Traceback/)).toBeNull();
    expect(screen.queryByText(/internal-ml/)).toBeNull();
  });
});
