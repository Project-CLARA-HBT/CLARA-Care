import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminSystemTelemetryPage from "@/app/admin/system/page";
import AdminDsarQueuePage from "@/app/admin/dsar/page";
import CommunityModerationPage from "@/app/admin/community-moderation/page";
import AdminRagEvalPage from "@/app/admin/rag-eval/page";
import AdminRagIngestionPage from "@/app/admin/rag-ingestion/page";
import { SocialUnavailableError } from "@/lib/social";

// ---------------------------------------------------------------------------
// Mocks & Shared State
// ---------------------------------------------------------------------------

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };
const flagState = { dsarEnabled: true };

const mockListAdminDsarQueue = vi.fn();
const mockUpdateDsarStatus = vi.fn();
const mockListReports = vi.fn();
const mockActOnReport = vi.fn();
const mockApiGet = vi.fn();
const mockApiPost = vi.fn();
const mockApiPatch = vi.fn();

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/compliance", () => ({
  isDsarEnabled: () => flagState.dsarEnabled,
  listAdminDsarQueue: () => mockListAdminDsarQueue(),
  updateDsarStatus: (id: number | string, status: string) => mockUpdateDsarStatus(id, status),
}));

vi.mock("@/lib/social", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/social")>();
  return {
    ...actual,
    listReports: () => mockListReports(),
    actOnReport: (id: number, action: "dismiss" | "remove") => mockActOnReport(id, action),
  };
});

vi.mock("@/lib/http-client", () => ({
  default: {
    get: (url: string) => mockApiGet(url),
    post: (url: string, data?: unknown) => mockApiPost(url, data),
    patch: (url: string, data?: unknown) => mockApiPatch(url, data),
  },
}));

// ---------------------------------------------------------------------------
// Setup & Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  flagState.dsarEnabled = true;

  // Mock clipboard
  Object.assign(navigator, {
    clipboard: {
      writeText: vi.fn().mockImplementation(() => Promise.resolve()),
    },
  });

  // Default DSAR queue mock
  mockListAdminDsarQueue.mockResolvedValue({
    enabled: true,
    requests: [
      {
        id: 101,
        kind: "export",
        status: "received",
        created_at: "2026-04-01T10:00:00Z",
        due_at: "2026-04-30T10:00:00Z",
        overdue: false,
      },
      {
        id: 102,
        kind: "delete",
        status: "in_progress",
        created_at: "2026-03-20T08:00:00Z",
        due_at: "2026-03-23T08:00:00Z",
        overdue: true,
      },
    ],
    overdue_count: 1,
  });

  mockUpdateDsarStatus.mockResolvedValue({
    id: 101,
    kind: "export",
    status: "fulfilled",
  });

  // Default Social Reports mock
  mockListReports.mockResolvedValue([
    {
      id: 1,
      target_type: "post",
      target_id: 501,
      reason: "spam",
      status: "open",
      created_at: "2026-04-01T12:00:00Z",
    },
    {
      id: 2,
      target_type: "comment",
      target_id: 602,
      reason: "harassment",
      status: "open",
      created_at: "2026-04-02T14:30:00Z",
    },
  ]);

  mockActOnReport.mockResolvedValue(undefined);

  // Default RAG Ingestion API mocks
  mockApiGet.mockImplementation((url: string) => {
    if (url === "/admin/rag/sources") {
      return Promise.resolve({
        data: {
          sources: [
            {
              id: 1,
              source_key: "duoc_thu_qg",
              display_name: "Dược thư Quốc gia",
              trust_tier: 1,
              enabled: true,
              weight: 1.0,
              fetch_mode: "api",
              last_watermark: "wm-20260401",
              last_run_at: "2026-04-01T10:00:00Z",
            },
            {
              id: 2,
              source_key: "pubmed_vn",
              display_name: "PubMed Vietnam",
              trust_tier: 2,
              enabled: false,
              weight: 0.8,
              fetch_mode: "crawl",
              last_watermark: "wm-20260328",
              last_run_at: null,
            },
          ],
        },
      });
    }
    if (url === "/admin/rag/stats") {
      return Promise.resolve({
        data: {
          documents: 2400,
          chunks: 18500,
          degraded_chunks: 0,
          coverage_pct: 99.2,
          sources_total: 12,
          sources_enabled: 10,
        },
      });
    }
    if (url.startsWith("/admin/rag/eval/results/")) {
      return Promise.resolve({
        data: {
          run_id: "eval-run-900",
          results: [
            {
              qid: "VN-Q01",
              recall_at_k: 0.88,
              ndcg_at_k: 0.84,
              faithfulness: 0.92,
              citation_acc: 0.90,
              latency_ms: 110,
              query_text: "Phác đồ điều trị tăng huyết áp theo Hội Tim mạch VN",
              expected_answer: "Khởi đầu bằng ACEi/ARB hoặc CCB phối hợp",
              generated_answer: "Hướng dẫn khuyến cáo sử dụng ACEi/ARB kết hợp CCB",
            },
            {
              qid: "VN-Q02",
              recall_at_k: 0.35,
              ndcg_at_k: 0.30,
              faithfulness: 0.40,
              citation_acc: 0.45,
              latency_ms: 280,
              query_text: "Liều dùng Levofloxacin trong viêm phổi cộng đồng",
              expected_answer: "500mg uống 1 lần/ngày trong 7-14 ngày",
              generated_answer: "750mg uống 2 lần/ngày (sai liều)",
              failure_reason: "Retrieval missed ground-truth dosage guideline",
            },
          ],
          recall_at_k: 0.615,
          ndcg_at_k: 0.57,
          faithfulness: 0.66,
          citation_acc: 0.675,
        },
      });
    }
    return Promise.resolve({ data: {} });
  });

  mockApiPost.mockImplementation((url: string) => {
    if (url === "/admin/rag/eval/run") {
      return Promise.resolve({
        data: {
          run_id: "eval-run-900",
          status: "completed",
          accepted: true,
        },
      });
    }
    if (url === "/admin/rag/ingestion/run") {
      return Promise.resolve({
        data: {
          job_id: "job-etl-77",
          source_key: "duoc_thu_qg",
          status: "queued",
          accepted: true,
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
});

afterEach(() => {
  vi.clearAllMocks();
  roleState.role = "admin";
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------
// Test Suites: Spec v8 §12.9..12.13 Verification
// ---------------------------------------------------------------------------

describe("Spec v8 Section 12.9..12.13: Admin System & Queues Reconstruct Verification", () => {
  // -------------------------------------------------------------------------
  // 1. Spec v8 Section 12.9: System Telemetry & Health (/admin/system)
  // -------------------------------------------------------------------------
  describe("1. Spec v8 Section 12.9: System Telemetry & Health (/admin/system)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and System Telemetry & Health archetype", async () => {
      render(<AdminSystemTelemetryPage />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "System Telemetry & Health", level: 1 })).toBeInTheDocument();
      });

      const container = document.querySelector('[data-layout-archetype="System Telemetry & Health"]');
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("renders 6 real-time service health cards (API, ML, DB, Redis, OCR, ASR) and KPI summary strip", async () => {
      render(<AdminSystemTelemetryPage />);

      await waitFor(() => {
        // 6 Service Health Cards
        expect(screen.getByText("API Gateway (FastAPI)")).toBeInTheDocument();
        expect(screen.getByText("ML Inference Service")).toBeInTheDocument();
        expect(screen.getByText("Database (PostgreSQL 16)")).toBeInTheDocument();
        expect(screen.getByText("Redis Cache & Flow Queue")).toBeInTheDocument();
        expect(screen.getAllByText("OCR Prescription Vision Sidecar").length).toBeGreaterThan(0);
        expect(screen.getAllByText("ASR Scribe Transcription Sidecar").length).toBeGreaterThan(0);
      });

      // KPI cards
      expect(screen.getByText("Health Status")).toBeInTheDocument();
      expect(screen.getByText("Avg Gateway Latency")).toBeInTheDocument();
      expect(screen.getByText("Error Rate (5xx/4xx)")).toBeInTheDocument();
      expect(screen.getByText("Total Requests")).toBeInTheDocument();
      expect(screen.getByText("Service Uptime")).toBeInTheDocument();
      expect(screen.getByText("Zero-PII Guard")).toBeInTheDocument();
    });

    it("renders latency percentiles matrix table and HTTP status code breakdown", async () => {
      render(<AdminSystemTelemetryPage />);

      await waitFor(() => {
        expect(screen.getByText("Latency Percentiles & SLA Compliance")).toBeInTheDocument();
        expect(screen.getByText("HTTP Status Code Distribution")).toBeInTheDocument();
        expect(screen.getByText("2xx SUCCESS")).toBeInTheDocument();
        expect(screen.getByText("4xx CLIENT")).toBeInTheDocument();
        expect(screen.getByText("5xx SERVER")).toBeInTheDocument();
      });
    });

    it("opens Environment Configuration Inspector with runtime, flags, and security invariants", async () => {
      render(<AdminSystemTelemetryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Inspect environment configuration/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Inspect environment configuration/i }));

      await waitFor(() => {
        expect(screen.getByText("Environment Configuration Inspector")).toBeInTheDocument();
        expect(screen.getByText("1. Runtime & Deployment Architecture")).toBeInTheDocument();
        expect(screen.getByText("2. Feature Flags & AI Gating")).toBeInTheDocument();
        expect(screen.getByText("3. Security & Governance Invariants")).toBeInTheDocument();
        expect(screen.getByText("4. Internal Service Endpoints & Upstream URLs")).toBeInTheDocument();
      });

      // Test JSON view toggle and Copy Manifest
      const jsonBtn = screen.getByRole("button", { name: /JSON View/i });
      fireEvent.click(jsonBtn);

      await waitFor(() => {
        expect(screen.getByText(/CLARA Care System Manifest - Sanitized/i)).toBeInTheDocument();
      });

      const copyBtn = screen.getByRole("button", { name: /Copy Manifest/i });
      fireEvent.click(copyBtn);
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });

    it("blocks non-authorized roles (normal) with 403 Access Denied", async () => {
      roleState.role = "normal";
      render(<AdminSystemTelemetryPage />);

      await waitFor(() => {
        expect(screen.getByText("Access Restricted")).toBeInTheDocument();
      });
      expect(screen.queryByText("API Gateway (FastAPI)")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // 2. Spec v8 Section 12.10: Statutory DSAR Queue (/admin/dsar)
  // -------------------------------------------------------------------------
  describe("2. Spec v8 Section 12.10: Statutory DSAR Queue (/admin/dsar)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and Statutory DSAR Queue archetype", async () => {
      render(<AdminDsarQueuePage />);

      await waitFor(() => {
        expect(screen.getByText("#101")).toBeInTheDocument();
      });

      const container = document.querySelector('[data-layout-archetype="Statutory DSAR Queue"]');
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("renders statutory countdowns, overdue badges, and KPI cards", async () => {
      render(<AdminDsarQueuePage />);

      await waitFor(() => {
        expect(screen.getByText("Total Requests")).toBeInTheDocument();
        expect(screen.getByText("Overdue")).toBeInTheDocument();
        expect(screen.getByText("#101")).toBeInTheDocument();
        expect(screen.getByText("#102")).toBeInTheDocument();
      });

      // Overdue countdown badge on #102
      expect(screen.getAllByText(/Overdue/i).length).toBeGreaterThan(0);
    });

    it("opens request inspector drawer, displays countdown window, and allows status advancement", async () => {
      render(<AdminDsarQueuePage />);

      await waitFor(() => {
        expect(screen.getByText("#101")).toBeInTheDocument();
      });

      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getAllByText(/Statutory Response Window/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/Action Timeline/i)).toBeInTheDocument();
        expect(screen.getByText(/Zero-PII compliant/i)).toBeInTheDocument();
      });

      // Advance status using drawer select
      const statusSelect = screen.getByLabelText(/Update status|Cập nhật trạng thái/i);
      fireEvent.change(statusSelect, { target: { value: "fulfilled" } });

      await waitFor(() => {
        expect(mockUpdateDsarStatus).toHaveBeenCalledWith(101, "fulfilled");
      });
    });

    it("enforces RBAC defense-in-depth by showing forbidden notice to non-admin roles", async () => {
      roleState.role = "doctor";
      render(<AdminDsarQueuePage />);

      await waitFor(() => {
        expect(screen.getByText(/do not have permission/i)).toBeInTheDocument();
      });
      expect(mockListAdminDsarQueue).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // 3. Spec v8 Section 12.11: Community Moderation (/admin/community-moderation)
  // -------------------------------------------------------------------------
  describe("3. Spec v8 Section 12.11: Community Moderation Workbench (/admin/community-moderation)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and Community Moderation Workbench archetype", async () => {
      render(<CommunityModerationPage />);

      await waitFor(() => {
        expect(screen.getByText("Community Moderation")).toBeInTheDocument();
      });

      const container = document.querySelector('[data-layout-archetype="Community Moderation Workbench"]');
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("renders dense reports table, KPIs, and preview inspector drawer", async () => {
      render(<CommunityModerationPage />);

      await waitFor(() => {
        expect(screen.getByText("#1")).toBeInTheDocument();
        expect(screen.getByText("#2")).toBeInTheDocument();
        expect(screen.getByText("Pending Reports")).toBeInTheDocument();
        expect(screen.getByText("Reported Posts")).toBeInTheDocument();
        expect(screen.getByText("High Severity")).toBeInTheDocument();
      });

      // Click inspect button for report #1
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByText(/Reported Content Preview/i)).toBeInTheDocument();
        expect(screen.getByText(/Violation Reason/i)).toBeInTheDocument();
        expect(screen.getByText(/Zero-PII Audit Log/i)).toBeInTheDocument();
      });
    });

    it("opens confirmation modal and executes remove action safely", async () => {
      render(<CommunityModerationPage />);

      await waitFor(() => {
        expect(screen.getByText("#2")).toBeInTheDocument();
      });

      const removeBtns = screen.getAllByRole("button", { name: /Remove/i });
      fireEvent.click(removeBtns[1]); // Remove on item #2

      await waitFor(() => {
        expect(screen.getByText(/Confirm Content Removal/i)).toBeInTheDocument();
      });

      const confirmBtn = screen.getByRole("button", { name: /Confirm Removal/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(mockActOnReport).toHaveBeenCalledWith(2, "remove");
      });
    });

    it("handles feature disabled state gracefully when social platform is turned off", async () => {
      mockListReports.mockRejectedValue(new SocialUnavailableError());

      render(<CommunityModerationPage />);

      await waitFor(() => {
        expect(screen.getByText(/Community platform is currently disabled/i)).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // 4. Spec v8 Section 12.12: RAG Evaluation Benchmark (/admin/rag-eval)
  // -------------------------------------------------------------------------
  describe("4. Spec v8 Section 12.12: RAG Evaluation Benchmark Workbench (/admin/rag-eval)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and RAG Evaluation Workbench archetype", async () => {
      render(<AdminRagEvalPage />);

      await waitFor(() => {
        expect(screen.getByText("RAG Benchmark Controls")).toBeInTheDocument();
      });

      const container = document.querySelector('[data-layout-archetype="RAG Evaluation Workbench"]');
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("runs evaluation benchmark and renders KPI metrics and questions table", async () => {
      mockApiPost.mockResolvedValueOnce({
        data: {
          run_id: "eval-run-101",
          status: "completed",
          accepted: true,
        },
      });
      mockApiGet.mockResolvedValueOnce({
        data: {
          run_id: "eval-run-101",
          results: [
            {
              qid: "VN-Q01",
              recall_at_k: 0.88,
              ndcg_at_k: 0.84,
              faithfulness: 0.92,
              citation_acc: 0.90,
              latency_ms: 110,
              query_text: "Phác đồ điều trị tăng huyết áp theo Hội Tim mạch VN",
            },
            {
              qid: "VN-Q02",
              recall_at_k: 0.35,
              ndcg_at_k: 0.30,
              faithfulness: 0.40,
              citation_acc: 0.45,
              latency_ms: 280,
              query_text: "Liều dùng Levofloxacin trong viêm phổi cộng đồng",
              failure_reason: "Retrieval missed ground-truth dosage guideline",
            },
          ],
          recall_at_k: 0.615,
          ndcg_at_k: 0.57,
          faithfulness: 0.66,
          citation_acc: 0.675,
        },
      });

      render(<AdminRagEvalPage />);

      const runBtn = screen.getByRole("button", { name: /run/i });
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith("/admin/rag/eval/run", { k: 10 });
        expect(mockApiGet).toHaveBeenCalledWith("/admin/rag/eval/results/eval-run-101");
      });

      await waitFor(() => {
        expect(screen.getByText("VN-Q01")).toBeInTheDocument();
        expect(screen.getByText("VN-Q02")).toBeInTheDocument();
        expect(screen.getAllByText(/Recall@10/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/nDCG@10/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Faithfulness/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Citation accuracy/i).length).toBeGreaterThan(0);
      });
    });

    it("opens Question-level Error & Sample Inspector Drawer for failed question diagnostics", async () => {
      mockApiPost.mockResolvedValueOnce({
        data: {
          run_id: "eval-run-101",
          status: "completed",
          accepted: true,
        },
      });
      mockApiGet.mockResolvedValueOnce({
        data: {
          run_id: "eval-run-101",
          results: [
            {
              qid: "VN-Q01",
              recall_at_k: 0.88,
              ndcg_at_k: 0.84,
              faithfulness: 0.92,
              citation_acc: 0.90,
              latency_ms: 110,
              query_text: "Phác đồ điều trị tăng huyết áp theo Hội Tim mạch VN",
            },
            {
              qid: "VN-Q02",
              recall_at_k: 0.35,
              ndcg_at_k: 0.30,
              faithfulness: 0.40,
              citation_acc: 0.45,
              latency_ms: 280,
              query_text: "Liều dùng Levofloxacin trong viêm phổi cộng đồng",
              expected_answer: "500mg uống 1 lần/ngày trong 7-14 ngày",
              generated_answer: "750mg uống 2 lần/ngày (sai liều)",
              failure_reason: "Retrieval missed ground-truth dosage guideline",
            },
          ],
          recall_at_k: 0.615,
          ndcg_at_k: 0.57,
          faithfulness: 0.66,
          citation_acc: 0.675,
        },
      });

      render(<AdminRagEvalPage />);

      const runBtn = screen.getByRole("button", { name: /run/i });
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(screen.getByText("VN-Q02")).toBeInTheDocument();
      });

      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[1]); // inspect VN-Q02

      await waitFor(() => {
        expect(screen.getByText("Question Inspector")).toBeInTheDocument();
        expect(screen.getByText(/Retrieval missed ground-truth dosage guideline/i)).toBeInTheDocument();
        expect(screen.getByText(/Liều dùng Levofloxacin trong viêm phổi cộng đồng/i)).toBeInTheDocument();
        expect(screen.getByText(/Expected Ground Truth/i)).toBeInTheDocument();
        expect(screen.getByText(/Generated Answer/i)).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // 5. Spec v8 Section 12.13: RAG Ingestion & Multi-Stage ETL (/admin/rag-ingestion)
  // -------------------------------------------------------------------------
  describe("5. Spec v8 Section 12.13: RAG Ingestion & Multi-Stage Pipeline (/admin/rag-ingestion)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and RAG Ingestion Monitor archetype", async () => {
      render(<AdminRagIngestionPage />);

      await waitFor(() => {
        expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
      });

      const container = document.querySelector('[data-layout-archetype="RAG Ingestion Monitor"]');
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("renders corpus stats KPIs and dense sources table with trust tier and watermarks", async () => {
      render(<AdminRagIngestionPage />);

      await waitFor(() => {
        expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
        expect(screen.getByText("duoc_thu_qg")).toBeInTheDocument();
        expect(screen.getByText("pubmed_vn")).toBeInTheDocument();
        expect(screen.getByText("wm-20260401")).toBeInTheDocument();
      });
    });

    it("opens multi-stage ETL pipeline inspector (Fetch -> Insert -> Update -> Degraded)", async () => {
      render(<AdminRagIngestionPage />);

      await waitFor(() => {
        expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
      });

      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByText(/ETL Pipeline Stages/i)).toBeInTheDocument();
        expect(screen.getByText("1. Fetch")).toBeInTheDocument();
        expect(screen.getByText("2. Insert")).toBeInTheDocument();
        expect(screen.getByText("3. Update")).toBeInTheDocument();
        expect(screen.getByText("4. Degraded")).toBeInTheDocument();
      });
    });

    it("triggers ETL ingestion run when clicking Run button", async () => {
      render(<AdminRagIngestionPage />);

      await waitFor(() => {
        expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
      });

      const runBtns = screen.getAllByRole("button", { name: /Run ingestion/i });
      fireEvent.click(runBtns[0]);

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith("/admin/rag/ingestion/run", {
          source_key: "duoc_thu_qg",
        });
      });
    });
  });
});
