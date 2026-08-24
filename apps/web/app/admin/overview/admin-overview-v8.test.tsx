import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminOverviewPage from "@/app/admin/overview/page";
import AdminOverviewPanel from "@/components/admin/admin-overview-panel";
import * as adminAuditLib from "@/lib/admin-audit";
import * as systemLib from "@/lib/system";
import * as researchLib from "@/lib/research";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";

// ---------------------------------------------------------------------------
// Mocks & Setup
// ---------------------------------------------------------------------------

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };
const trackAdminSurfaceViewed = vi.fn();

const mockConfig = {
  rag_sources: [
    { id: "s1", name: "Bộ Y tế Dược thư", enabled: true, priority: 1, weight: 1.0, category: "guideline" },
    { id: "s2", name: "PubMed Vietnam", enabled: true, priority: 2, weight: 0.9, category: "scientific" },
    { id: "s3", name: "DrugBank Global", enabled: false, priority: 3, weight: 0.8, category: "pharmacology" },
  ],
  rag_flow: {
    role_router_enabled: true,
    intent_router_enabled: true,
    rule_verification_enabled: true,
    nli_model_enabled: true,
    rag_reranker_enabled: true,
    rag_nli_enabled: true,
    rag_graphrag_enabled: true,
    verification_enabled: true,
    deepseek_fallback_enabled: false,
    low_context_threshold: 0.35,
    precision_at_k: 10,
    recall_at_k: 10,
    ndcg_at_k: 10,
    scientific_retrieval_enabled: true,
    web_retrieval_enabled: true,
    file_retrieval_enabled: true,
  },
  careguard_runtime: {
    external_ddi_enabled: true,
  },
};

const mockKnowledgeSources = [
  { id: 1, name: "Phác đồ ĐTĐ 2026", is_active: true, documents_count: 5 },
  { id: 2, name: "Kháng sinh đồ Bạch Mai", is_active: true, documents_count: 3 },
];

const mockSourceHubCatalog = [
  { key: "pubmed", label: "PubMed", description: "Y văn quốc tế", supports_live_sync: true },
  { key: "vn_moh", label: "Bộ Y tế", description: "Văn bản quy phạm", supports_live_sync: true },
  { key: "rxnorm", label: "RxNorm", description: "Danh mục chuẩn", supports_live_sync: false },
];

const mockAuditLogs = {
  records: [
    {
      id: 101,
      actor_ref: "admin-sec-01",
      action: "toggle_source_enabled",
      target: "rag_sources:s1",
      outcome: "success",
      meta: { source_id: "s1", enabled: true },
      created_at: "2026-08-24T08:30:00.000Z",
    },
    {
      id: 102,
      actor_ref: "admin-sec-02",
      action: "update_flow_threshold",
      target: "rag_flow:low_context_threshold",
      outcome: "success",
      meta: { old: 0.2, next: 0.35 },
      created_at: "2026-08-24T08:15:00.000Z",
    },
    {
      id: 103,
      actor_ref: "admin-sec-01",
      action: "ingest_corpus_batch",
      target: "kb_registry:vn_moh",
      outcome: "failure",
      meta: { error_code: "timeout" },
      created_at: "2026-08-24T07:45:00.000Z",
    },
    {
      id: 104,
      actor_ref: "admin-sec-03",
      action: "access_security_audit",
      target: "audit_wal:log_01",
      outcome: "denied",
      meta: { reason: "unauthorized" },
      created_at: "2026-08-24T07:10:00.000Z",
    },
  ],
};

const mockApiHealth = {
  status: "ok",
  message: "Service healthy",
};

const mockDependencies = {
  mlReachable: true,
  mlStatus: "reachable",
};

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: (props: { view: string }) => trackAdminSurfaceViewed(props),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/components/admin/use-control-tower-config", () => ({
  default: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe("Spec v8 §7.5 & 11: Admin Overview Rebuild Verification", () => {
  let mockReloadConfig: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    roleState.role = "admin";
    window.localStorage.setItem("clara_ui_language", "vi");
    mockReloadConfig = vi.fn(async () => {});

    (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isSaving: false,
      isDirty: false,
      error: "",
      message: "",
      reload: mockReloadConfig,
      save: vi.fn(async () => true),
      setSourceEnabled: vi.fn(),
      setSourcePriority: vi.fn(),
      setSourceWeight: vi.fn(),
      setSourceCategory: vi.fn(),
      setFlowToggle: vi.fn(),
      setLowContextThreshold: vi.fn(),
      setRetrievalMetricK: vi.fn(),
      flowToggleKeys: [],
    });

    vi.spyOn(researchLib, "listKnowledgeSources").mockResolvedValue(mockKnowledgeSources as any);
    vi.spyOn(researchLib, "listSourceHubCatalog").mockResolvedValue(mockSourceHubCatalog as any);
    vi.spyOn(systemLib, "getApiHealth").mockResolvedValue(mockApiHealth as any);
    vi.spyOn(systemLib, "getSystemDependencies").mockResolvedValue(mockDependencies as any);
    vi.spyOn(adminAuditLib, "getAdminAuditLog").mockResolvedValue(mockAuditLogs as any);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  describe("1. Navigation & Command Strip Adoption (Spec v8 §7.5 & 11.1)", () => {
    it("renders AdminCommandStrip and does NOT render six 90px navigation tiles", async () => {
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();
      });

      // Verify command strip tabs
      expect(screen.getByText("Tổng quan")).toBeInTheDocument();
      expect(screen.getByText("Nguồn tri thức")).toBeInTheDocument();
      expect(screen.getByText("Luồng trả lời")).toBeInTheDocument();
      expect(screen.getByText("Giám sát")).toBeInTheDocument();
      expect(screen.getByText("Phân tích")).toBeInTheDocument();

      // Ensure no legacy navigation cards wall
      expect(screen.queryByTestId("admin-nav-cards-grid")).not.toBeInTheDocument();
    });

    it("renders with ADMIN_COMMAND shell mode and DENSE layout archetype", async () => {
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });

      const workbench = document.querySelector(
        '[data-layout-archetype="Admin Command Workbench"]'
      );
      expect(workbench).toBeInTheDocument();
      expect(workbench).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(workbench).toHaveAttribute("data-density", "DENSE");
    });
  });

  describe("2. Ordered Visual Hierarchy (Spec v8 §7.5: Attention Queue → Status Ledger → Operations → Audit Digest)", () => {
    it("renders 4 sections strictly in the mandated visual order", async () => {
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });

      const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);

      // Verify the 4 ordered headings:
      // 1. Attention Queue
      // 2. System Status Ledger
      // 3. Recent Operations
      // 4. Audit Digest
      expect(headings[0]).toContain("Hàng đợi Cần lưu ý (Attention Queue)");
      expect(headings[1]).toContain("Sổ cái Trạng thái Phân hệ (System Status Ledger)");
      expect(headings[2]).toContain("Hoạt động Vận hành Gần đây (Recent Operations)");
      expect(headings[3]).toContain("Tóm lược Kiểm toán & Tuân thủ (Audit Digest)");
    });

    describe("2.1 Attention Queue (0–5 ordered rows with severity, system, issue, owner/action, timestamp)", () => {
      it("renders 1 compact healthy row when all subsystems are nominal", async () => {
        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText("Hàng đợi Cần lưu ý (Attention Queue)")).toBeInTheDocument();
        });

        expect(screen.getByText("Hoạt động tốt")).toBeInTheDocument();
        expect(screen.getByText("Toàn bộ phân hệ (All Systems)")).toBeInTheDocument();
        expect(screen.getByText(/Mọi phân hệ hoạt động bình thường/i)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Xem chỉ số/i })).toHaveAttribute(
          "href",
          "/admin/observability"
        );
      });

      it("renders ordered anomaly rows sorted by severity (critical > warning > info) up to 5 items", async () => {
        const degradedConfig = {
          ...mockConfig,
          rag_sources: [
            { id: "s1", name: "Bộ Y tế Dược thư", enabled: false, priority: 1, weight: 1.0, category: "guideline" },
            { id: "s2", name: "PubMed Vietnam", enabled: false, priority: 2, weight: 0.9, category: "scientific" },
          ],
          rag_flow: {
            ...mockConfig.rag_flow,
            low_context_threshold: 0.1, // Warning: < 0.2
            rule_verification_enabled: false, // Critical: FIDES disabled
          },
        };

        (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
          config: degradedConfig,
          isLoading: false,
          isSaving: false,
          isDirty: false,
          error: "",
          message: "",
          reload: mockReloadConfig,
          save: vi.fn(),
          setSourceEnabled: vi.fn(),
          setSourcePriority: vi.fn(),
          setSourceWeight: vi.fn(),
          setSourceCategory: vi.fn(),
          setFlowToggle: vi.fn(),
          setLowContextThreshold: vi.fn(),
          setRetrievalMetricK: vi.fn(),
          flowToggleKeys: [],
        });

        vi.spyOn(systemLib, "getApiHealth").mockResolvedValue({
          status: "degraded",
          message: "API Gateway high latency",
        } as any);

        vi.spyOn(systemLib, "getSystemDependencies").mockResolvedValue({
          mlReachable: false,
          mlStatus: "unreachable",
        } as any);

        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText("Hàng đợi Cần lưu ý (Attention Queue)")).toBeInTheDocument();
        });

        // Verify Critical rows appear first
        expect(screen.getByText("API Gateway")).toBeInTheDocument();
        expect(screen.getByText("ML & Guardrails")).toBeInTheDocument();
        expect(screen.getByText("FIDES Shield")).toBeInTheDocument();
        expect(screen.getByText("RAG Sources")).toBeInTheDocument();

        // Verify Warning row
        expect(screen.getByText("Answer Flow Router")).toBeInTheDocument();

        // Verify Action links
        expect(screen.getByText("Bật lại FIDES")).toBeInTheDocument();
        expect(screen.getByText("Bật Nguồn tri thức")).toBeInTheDocument();
        expect(screen.getByText("Điều chỉnh Ngưỡng")).toBeInTheDocument();
        expect(screen.getByText("Kiểm tra Giám sát")).toBeInTheDocument();
        expect(screen.getByText("Mở Observability")).toBeInTheDocument();
      });
    });

    describe("2.2 System Status Ledger (Dense Table of Knowledge Core, Answer Flow, RAG Eval, Data Ingestion)", () => {
      it("renders dense table of 4 subsystems with state, key config, and actions (NO 4 cards)", async () => {
        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText("Sổ cái Trạng thái Phân hệ (System Status Ledger)")).toBeInTheDocument();
        });

        // 1. Knowledge Core
        expect(screen.getByText("Knowledge Core")).toBeInTheDocument();
        expect(screen.getByText("Nguồn Tri thức & Registry")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Quản lý nguồn/i })).toHaveAttribute(
          "href",
          "/admin/knowledge-sources"
        );

        // 2. Answer Flow
        expect(screen.getByText("Answer Flow")).toBeInTheDocument();
        expect(screen.getByText("Điều phối Router & Multi-tier")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Cấu hình luồng/i })).toHaveAttribute(
          "href",
          "/admin/answer-flow"
        );

        // 3. RAG Evaluation
        expect(screen.getByText("RAG Evaluation")).toBeInTheDocument();
        expect(screen.getByText("Đánh giá Golden VN Q&A")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Chạy đánh giá/i })).toHaveAttribute(
          "href",
          "/admin/rag-eval"
        );

        // 4. Data Ingestion
        expect(screen.getByText("Data Ingestion")).toBeInTheDocument();
        expect(screen.getByText("Nạp Dữ liệu & Ingestion Pipeline")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Mở Ingestion/i })).toHaveAttribute(
          "href",
          "/admin/rag-ingestion"
        );
      });
    });

    describe("2.3 Recent Operations (Full-Width Operational History Ledger)", () => {
      it("renders full-width operational history table with audit trail records", async () => {
        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText("Hoạt động Vận hành Gần đây (Recent Operations)")).toBeInTheDocument();
        });

        // Fetches from getAdminAuditLog(8)
        expect(adminAuditLib.getAdminAuditLog).toHaveBeenCalledWith(8);

        // Records verification
        expect(screen.getAllByText("admin-sec-01").length).toBe(2);
        expect(screen.getByText("admin-sec-02")).toBeInTheDocument();
        expect(screen.getByText("admin-sec-03")).toBeInTheDocument();

        expect(screen.getByText("toggle_source_enabled")).toBeInTheDocument();
        expect(screen.getByText("update_flow_threshold")).toBeInTheDocument();
        expect(screen.getByText("ingest_corpus_batch")).toBeInTheDocument();
        expect(screen.getByText("access_security_audit")).toBeInTheDocument();

        // Outcomes
        expect(screen.getAllByText("Thành công").length).toBeGreaterThanOrEqual(2);
        expect(screen.getByText("Thất bại")).toBeInTheDocument();
        expect(screen.getByText("Bị từ chối")).toBeInTheDocument();

        // Full audit log link
        expect(screen.getByRole("link", { name: /Xem toàn bộ nhật ký kiểm toán/i })).toHaveAttribute(
          "href",
          "/admin/audit-log"
        );
      });

      it("renders empty state placeholder when no audit records exist", async () => {
        vi.spyOn(adminAuditLib, "getAdminAuditLog").mockResolvedValue({ records: [] } as any);

        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText(/Chưa có bản ghi hoạt động quản trị nào/i)).toBeInTheDocument();
        });
      });
    });

    describe("2.4 Audit Digest (Compact Compliance Activity List)", () => {
      it("renders compact compliance digest with Zero-PII, Append-Only WAL, and FIDES status", async () => {
        render(<AdminOverviewPanel />);

        await waitFor(() => {
          expect(screen.getByText("Tóm lược Kiểm toán & Tuân thủ (Audit Digest)")).toBeInTheDocument();
        });

        expect(screen.getByText("Zero-PII Invariant")).toBeInTheDocument();
        expect(screen.getByText("Loại trừ PII 100%")).toBeInTheDocument();

        expect(screen.getByText("Append-Only WAL")).toBeInTheDocument();
        expect(screen.getByText("Nhật ký Bất biến")).toBeInTheDocument();

        expect(screen.getByText("FIDES Guardrail")).toBeInTheDocument();
        expect(screen.getByText("Kiểm chứng An toàn")).toBeInTheDocument();

        expect(screen.getByText("Sẵn sàng Kiểm toán")).toBeInTheDocument();
        expect(screen.getByText("4 bản ghi")).toBeInTheDocument();

        expect(
          screen.getByRole("link", { name: /Mở Nhật ký Kiểm toán Đầy đủ \(Immutable Audit Trail\)/i })
        ).toHaveAttribute("href", "/admin/audit-log");
      });
    });
  });

  describe("3. Elimination of Anti-Patterns (No Giant Hero, No Status-Card Wall, No All Tools Card Launcher)", () => {
    it("does NOT render giant hero banner or promo cards", async () => {
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });

      // No giant hero elements
      expect(screen.queryByText("TRUNG TÂM CHỈ HUY HỆ THỐNG")).not.toBeInTheDocument();
      expect(screen.queryByText("4 Phân hệ Trọng yếu")).not.toBeInTheDocument();
    });

    it("does NOT render All Tools Card Launcher in the page body", async () => {
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });

      // Verify All Tools Launcher card grid is completely removed from page body
      expect(screen.queryByText("Trình Khởi chạy Toàn bộ Công cụ (All Tools Launcher)")).not.toBeInTheDocument();
      expect(screen.queryByText("14 Modules")).not.toBeInTheDocument();
      expect(screen.queryByText("Nền tảng & Điều hành")).not.toBeInTheDocument();
      expect(screen.queryByText("Tri thức & Dữ liệu RAG")).not.toBeInTheDocument();
      expect(screen.queryByText("Hệ thống AI & Giám sát")).not.toBeInTheDocument();
      expect(screen.queryByText("Quản trị & Tuân thủ")).not.toBeInTheDocument();
    });
  });

  describe("4. Card Clutter Reduction (>=60% reduction)", () => {
    it("verifies clean, dense layout with minimal nested cards", async () => {
      const { container } = render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });

      // The reconstructed page uses 4 primary structured sections instead of 11+ nested cards
      const sections = container.querySelectorAll("section");
      expect(sections.length).toBe(4);
    });
  });

  describe("5. Telemetry & User Interactions", () => {
    it("tracks admin overview viewed event on mount", async () => {
      render(<AdminOverviewPanel />);

      await waitFor(() => {
        expect(trackAdminSurfaceViewed).toHaveBeenCalledWith({ view: "overview" });
      });
    });

    it("handles sync refresh button click", async () => {
      render(<AdminOverviewPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Đồng bộ tức thì/i })).toBeInTheDocument();
      });

      const refreshBtn = screen.getByRole("button", { name: /Đồng bộ tức thì/i });
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(mockReloadConfig).toHaveBeenCalled();
      });
    });
  });

  describe("6. RBAC Role Gating", () => {
    it("blocks non-admin users with 403 Access Denied", async () => {
      roleState.role = "doctor";
      render(<AdminOverviewPage />);

      expect(screen.getByText(/Từ chối quyền truy cập/i)).toBeInTheDocument();
      expect(screen.queryByText("Tổng quan Điều phối & An toàn Hệ thống")).not.toBeInTheDocument();
    });

    it("permits admin users to access the workbench", async () => {
      roleState.role = "admin";
      render(<AdminOverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
      });
    });
  });
});
