import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminObservabilityPage from "@/app/admin/observability/page";
import * as systemLib from "@/lib/system";

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

describe("AdminObservabilityPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("clara_ui_language", "vi");

    vi.spyOn(systemLib, "getApiHealth").mockResolvedValue({
      status: "ok",
      message: "API Gateway nominal",
    } as any);

    vi.spyOn(systemLib, "getSystemMetrics").mockResolvedValue({
      request_count: 1500,
      error_count: 2,
      avg_latency_ms: 120,
      route_percentiles: [
        { route: "POST /chat", p50_ms: 100, p90_ms: 250, p99_ms: 450 },
      ],
    } as any);

    vi.spyOn(systemLib, "getSystemDependencies").mockResolvedValue({
      status: "ok",
      dependencies: {
        ml: { reachable: true, status: "healthy" },
      },
    } as any);

    vi.spyOn(systemLib, "getControlTowerConfig").mockResolvedValue({
      rag_sources: [
        { id: "src-1", name: "Source 1", enabled: true, priority: 1, weight: 1.0, category: "guideline" },
      ],
      rag_flow: {
        role_router_enabled: true,
        low_context_threshold: 0.2,
      },
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders AdminShell with observability active tab and live signal dashboard", async () => {
    render(<AdminObservabilityPage />);

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Sức khỏe API")).toBeInTheDocument();
      expect(screen.getByText("Trạng thái ML")).toBeInTheDocument();
      expect(screen.getByText("Request / Lỗi")).toBeInTheDocument();
      expect(screen.getByText("Radar điều khiển")).toBeInTheDocument();
    });
  });
});
