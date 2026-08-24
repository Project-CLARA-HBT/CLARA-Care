import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mockGetApiHealth = vi.fn();
const mockGetSystemMetrics = vi.fn();
const mockGetSystemDependencies = vi.fn();
const roleState = { role: "admin" as "normal" | "researcher" | "doctor" | "admin" };

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/system", () => ({
  getApiHealth: () => mockGetApiHealth(),
  getSystemMetrics: () => mockGetSystemMetrics(),
  getSystemDependencies: () => mockGetSystemDependencies(),
  normalizeApiHealth: (data: unknown) => {
    const d = data as { status?: string; message?: string };
    return { status: d?.status ?? "ok", message: d?.message ?? "Nominal" };
  },
  normalizeSystemMetrics: (data: unknown) => {
    const d = data as {
      requests_total?: number;
      error_total?: number;
      avg_latency_ms?: number;
      percentiles?: Record<string, unknown>;
    };
    return {
      requestCount: d?.requests_total ?? 21500,
      errorCount: d?.error_total ?? 16,
      avgLatencyMs: d?.avg_latency_ms ?? 24.5,
      routePercentiles: [
        { route: "POST /api/v1/chat", p50Ms: 140, p90Ms: 280, p99Ms: 650 },
        { route: "POST /api/v1/careguard/cabinet/auto-ddi-check", p50Ms: 60, p90Ms: 120, p99Ms: 290 },
      ],
    };
  },
  normalizeSystemDependencies: (data: unknown) => {
    const d = data as { ml_reachable?: boolean; ml_status?: string };
    return {
      mlReachable: d?.ml_reachable ?? true,
      mlStatus: d?.ml_status ?? "reachable",
    };
  },
}));

import AdminSystemTelemetryPage from "@/app/admin/system/page";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockGetApiHealth.mockResolvedValue({ status: "ok", message: "All systems nominal" });
  mockGetSystemMetrics.mockResolvedValue({
    requests_total: 25400,
    error_total: 18,
    avg_latency_ms: 22.4,
  });
  mockGetSystemDependencies.mockResolvedValue({
    ml_reachable: true,
    ml_status: "reachable",
  });

  // Mock clipboard
  Object.assign(navigator, {
    clipboard: {
      writeText: vi.fn().mockImplementation(() => Promise.resolve()),
    },
  });
});

afterEach(() => {
  vi.clearAllMocks();
  roleState.role = "admin";
  window.localStorage.clear();
});

describe("AdminSystemTelemetryPage (Spec v5 Section 6.63)", () => {
  it("renders AdminCommandStrip, archetype title, and live KPI summary cards", async () => {
    render(<AdminSystemTelemetryPage />);

    // Admin Command Strip is present
    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    // Archetype and header
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "System Telemetry & Health", level: 1 })).toBeInTheDocument();
      expect(screen.getByText("ALL SYSTEMS NOMINAL")).toBeInTheDocument();
    });

    // KPI cards
    expect(screen.getByText("Health Status")).toBeInTheDocument();
    expect(screen.getByText("Avg Gateway Latency")).toBeInTheDocument();
    expect(screen.getByText("Error Rate (5xx/4xx)")).toBeInTheDocument();
    expect(screen.getByText("Total Requests")).toBeInTheDocument();
    expect(screen.getByText("Zero-PII Guard")).toBeInTheDocument();
  });

  it("renders all 6 real-time service health cards (API, ML, Database, Redis, OCR, ASR)", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      // 1. API Gateway
      expect(screen.getByText("API Gateway (FastAPI)")).toBeInTheDocument();
      // 2. ML Inference Service
      expect(screen.getByText("ML Inference Service")).toBeInTheDocument();
      // 3. PostgreSQL Database
      expect(screen.getByText("Database (PostgreSQL 16)")).toBeInTheDocument();
      // 4. Redis In-Memory Store
      expect(screen.getByText("Redis Cache & Flow Queue")).toBeInTheDocument();
      // 5. OCR Sidecar
      expect(screen.getAllByText("OCR Prescription Vision Sidecar").length).toBeGreaterThan(0);
      // 6. ASR Sidecar
      expect(screen.getAllByText("ASR Scribe Transcription Sidecar").length).toBeGreaterThan(0);
    });

    // Each service has ports and endpoints displayed
    expect(screen.getByText(/Port 8000/i)).toBeInTheDocument();
    expect(screen.getByText(/Port 8010/i)).toBeInTheDocument();
    expect(screen.getByText(/Port 5432/i)).toBeInTheDocument();
    expect(screen.getByText(/Port 6379/i)).toBeInTheDocument();
    expect(screen.getByText(/Port 8020/i)).toBeInTheDocument();
    expect(screen.getByText(/Port 8030/i)).toBeInTheDocument();
  });

  it("renders latency percentiles matrix table and SLA compliance badges", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByText("Latency Percentiles & SLA Compliance")).toBeInTheDocument();
      expect(screen.getByText("API Gateway & Security")).toBeInTheDocument();
      expect(screen.getByText("ML Inference & RAG Engine")).toBeInTheDocument();
      expect(screen.getByText("PostgreSQL Relational Ledger")).toBeInTheDocument();
      expect(screen.getByText("Redis Cache & Event Stream")).toBeInTheDocument();
      expect(screen.getByText("OCR Vision Prescription Sidecar")).toBeInTheDocument();
      expect(screen.getAllByText("ASR Scribe Transcription Sidecar").length).toBeGreaterThan(0);
    });

    // SLA Met badges
    expect(screen.getAllByText("SLA Met").length).toBeGreaterThan(0);

    // Route breakdown table
    expect(screen.getByText("Core API Route Latency Distribution")).toBeInTheDocument();
    expect(screen.getByText("/api/v1/chat")).toBeInTheDocument();
    expect(screen.getByText("/api/v1/careguard/cabinet/auto-ddi-check")).toBeInTheDocument();
  });

  it("renders HTTP status code distribution (2xx, 3xx, 4xx, 5xx) and error categories", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByText("HTTP Status Code Distribution")).toBeInTheDocument();
      expect(screen.getByText("2xx SUCCESS")).toBeInTheDocument();
      expect(screen.getByText("3xx REDIRECT")).toBeInTheDocument();
      expect(screen.getByText("4xx CLIENT")).toBeInTheDocument();
      expect(screen.getByText("5xx SERVER")).toBeInTheDocument();
    });

    // Error causes
    expect(screen.getByText("Error Categories & Root Causes")).toBeInTheDocument();
    expect(screen.getByText(/Rate Limit Exceeded/i)).toBeInTheDocument();
    expect(screen.getByText(/Validation Error/i)).toBeInTheDocument();
    expect(screen.getByText(/Token Expired/i)).toBeInTheDocument();
  });

  it("opens Environment Configuration Inspector, toggles JSON view, and copies manifest", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Inspect environment configuration/i })).toBeInTheDocument();
    });

    // Click "Inspect Env" button
    fireEvent.click(screen.getByRole("button", { name: /Inspect environment configuration/i }));

    await waitFor(() => {
      expect(screen.getByText("Environment Configuration Inspector")).toBeInTheDocument();
      expect(screen.getByText("1. Runtime & Deployment Architecture")).toBeInTheDocument();
      expect(screen.getByText("2. Feature Flags & AI Gating")).toBeInTheDocument();
      expect(screen.getByText("3. Security & Governance Invariants")).toBeInTheDocument();
      expect(screen.getByText("4. Internal Service Endpoints & Upstream URLs")).toBeInTheDocument();
    });

    // Toggle JSON View
    const jsonBtn = screen.getByRole("button", { name: /JSON View/i });
    fireEvent.click(jsonBtn);

    await waitFor(() => {
      expect(screen.getByText(/CLARA Care System Manifest - Sanitized/i)).toBeInTheDocument();
    });

    // Copy manifest button
    const copyBtn = screen.getByRole("button", { name: /Copy Manifest/i });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalled();
  });

  it("opens Service Diagnostic Inspector when clicking on a service card", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByText("Database (PostgreSQL 16)")).toBeInTheDocument();
    });

    // Click Database card
    fireEvent.click(screen.getByText("Database (PostgreSQL 16)"));

    await waitFor(() => {
      expect(screen.getByText("Service Overview & Health")).toBeInTheDocument();
      expect(screen.getByText("Runtime & Protocol Diagnostics")).toBeInTheDocument();
      expect(screen.getByText("PostgreSQL Native Wire Protocol")).toBeInTheDocument();
      expect(screen.getByText("18 / 100 active connections")).toBeInTheDocument();
    });
  });

  it("filters services by search query and tier tabs", async () => {
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByText("API Gateway (FastAPI)")).toBeInTheDocument();
      expect(screen.getByText("Redis Cache & Flow Queue")).toBeInTheDocument();
    });

    // Filter by search query
    const searchInput = screen.getByLabelText(/Filter services by name or endpoint/i);
    fireEvent.change(searchInput, { target: { value: "Redis" } });

    await waitFor(() => {
      expect(screen.getByText("Redis Cache & Flow Queue")).toBeInTheDocument();
      expect(screen.queryByText("API Gateway (FastAPI)")).not.toBeInTheDocument();
    });

    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });

    // Filter by tier tab "ML"
    const mlTab = screen.getByRole("button", { name: "ML" });
    fireEvent.click(mlTab);

    await waitFor(() => {
      expect(screen.getByText("ML Inference Service")).toBeInTheDocument();
      expect(screen.queryByText("Database (PostgreSQL 16)")).not.toBeInTheDocument();
    });
  });

  it("enforces RBAC defense-in-depth by blocking non-authorized roles", async () => {
    roleState.role = "normal";
    render(<AdminSystemTelemetryPage />);

    await waitFor(() => {
      expect(screen.getByText("Access Restricted")).toBeInTheDocument();
      expect(screen.getByText(/You do not have permission to view administrative system telemetry/i)).toBeInTheDocument();
    });

    // Should not render service cards for non-authorized user
    expect(screen.queryByText("Database (PostgreSQL 16)")).not.toBeInTheDocument();
  });
});
