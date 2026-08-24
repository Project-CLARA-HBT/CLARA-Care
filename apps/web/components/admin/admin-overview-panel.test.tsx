import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminOverviewPanel from "./admin-overview-panel";
import * as adminAuditLib from "@/lib/admin-audit";
import * as systemLib from "@/lib/system";
import * as researchLib from "@/lib/research";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: vi.fn(),
}));

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

vi.mock("@/components/admin/use-control-tower-config", () => ({
  default: vi.fn(),
}));

describe("AdminOverviewPanel Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isSaving: false,
      isDirty: false,
      error: "",
      message: "",
      reload: vi.fn(async () => {}),
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

  it("renders System Overview Headline with FIDES safety indicator and live sync timestamp", async () => {
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByText("TRUNG TÂM CHỈ HUY HỆ THỐNG")).toBeInTheDocument();
    });

    expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
    expect(screen.getByText("FIDES Safety Shield: Hoạt động")).toBeInTheDocument();
    expect(screen.getByText(/Đồng bộ trực tiếp:/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Đồng bộ tức thì/i })).toBeInTheDocument();
  });

  it("renders all 4 Systems Status Stream cards with correct routes and live metrics", async () => {
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByText("4 Phân hệ Trọng yếu (Systems Status Stream)")).toBeInTheDocument();
    });

    // 1. Knowledge Core
    expect(screen.getByText("Knowledge Core")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Quản lý nguồn tri thức/i })).toHaveAttribute(
      "href",
      "/admin/knowledge-sources"
    );
    expect(screen.getByText("2/3 bật")).toBeInTheDocument();

    // 2. Answer Flow
    expect(screen.getByText("Answer Flow")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Cấu hình luồng trả lời/i })).toHaveAttribute(
      "href",
      "/admin/answer-flow"
    );
    expect(screen.getByText("0.35")).toBeInTheDocument();

    // 3. RAG Evaluation
    expect(screen.getByText("RAG Evaluation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Chạy đánh giá RAG/i })).toHaveAttribute(
      "href",
      "/admin/rag-eval"
    );
    expect(screen.getByText("k=10")).toBeInTheDocument();

    // 4. Data Ingestion
    expect(screen.getByText("Data Ingestion")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mở trung tâm nạp dữ liệu/i })).toHaveAttribute(
      "href",
      "/admin/rag-ingestion"
    );
    expect(screen.getByText("Offline Plane")).toBeInTheDocument();
  });

  it("renders Attention / Critical Alerts block when anomalies are detected", async () => {
    // Modify config to have abnormal threshold and 0 enabled sources
    const degradedConfig = {
      ...mockConfig,
      rag_sources: [
        { id: "s1", name: "Bộ Y tế Dược thư", enabled: false, priority: 1, weight: 1.0, category: "guideline" },
      ],
      rag_flow: {
        ...mockConfig.rag_flow,
        low_context_threshold: 0.1, // abnormal threshold (< 0.2)
        rule_verification_enabled: false, // FIDES disabled
      },
    };

    (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      config: degradedConfig,
      isLoading: false,
      isSaving: false,
      isDirty: false,
      error: "",
      message: "",
      reload: vi.fn(),
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
      message: "High latency on upstream",
    } as any);

    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByText("Cảnh báo & Mục cần lưu ý (Attention / Critical Alerts)")).toBeInTheDocument();
    });

    // Alert for degraded API
    expect(screen.getByText("Dịch vụ API Gateway suy giảm")).toBeInTheDocument();

    // Alert for FIDES disabled
    expect(screen.getByText("Chốt chặn An toàn FIDES bị tắt")).toBeInTheDocument();

    // Alert for 0 RAG sources enabled
    expect(screen.getByText("Toàn bộ nguồn RAG đang bị tắt")).toBeInTheDocument();

    // Alert for low-context threshold
    expect(screen.getByText("Ngưỡng low_context_threshold bất thường")).toBeInTheDocument();
  });

  it("renders operational state with zero fabricated alerts when system is healthy", async () => {
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Mọi phân hệ hoạt động bình thường/i)).toBeInTheDocument();
    });
  });

  it("renders Recent Operational Activity audit trail stream from getAdminAuditLog(6)", async () => {
    render(<AdminOverviewPanel />);

    await waitFor(() => {
      expect(screen.getByText("Hoạt động Vận hành Gần đây (Recent Operational Activity)")).toBeInTheDocument();
    });

    // Calls getAdminAuditLog with limit 6
    expect(adminAuditLib.getAdminAuditLog).toHaveBeenCalledWith(6);

    // Verifies real audit records rendering
    expect(screen.getAllByText("admin-sec-01").length).toBe(2);
    expect(screen.getByText("toggle_source_enabled")).toBeInTheDocument();
    expect(screen.getByText("rag_sources:s1")).toBeInTheDocument();
    expect(screen.getAllByText("Thành công").length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText("admin-sec-02")).toBeInTheDocument();
    expect(screen.getByText("update_flow_threshold")).toBeInTheDocument();

    expect(screen.getByText("ingest_corpus_batch")).toBeInTheDocument();
    expect(screen.getByText("Thất bại")).toBeInTheDocument();
  });
});
