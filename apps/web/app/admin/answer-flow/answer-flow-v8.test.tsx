import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminAnswerFlowPage from "@/app/admin/answer-flow/page";
import AdminAnswerFlowPanel from "@/components/admin/admin-answer-flow-panel";
import * as systemLib from "@/lib/system";
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
  ],
  rag_flow: {
    role_router_enabled: true,
    intent_router_enabled: true,
    rule_verification_enabled: true,
    nli_model_enabled: true,
    rag_reranker_enabled: true,
    rag_nli_enabled: true,
    rag_graphrag_enabled: true,
    scientific_retrieval_enabled: true,
    web_retrieval_enabled: true,
    file_retrieval_enabled: true,
    verification_enabled: true,
    deepseek_fallback_enabled: false,
    low_context_threshold: 0.35,
    precision_at_k: 10,
    recall_at_k: 10,
    ndcg_at_k: 10,
  },
  careguard_runtime: {
    external_ddi_enabled: true,
  },
};

const FLOW_KEYS = [
  "role_router_enabled",
  "intent_router_enabled",
  "rule_verification_enabled",
  "nli_model_enabled",
  "rag_reranker_enabled",
  "rag_nli_enabled",
  "rag_graphrag_enabled",
  "scientific_retrieval_enabled",
  "web_retrieval_enabled",
  "file_retrieval_enabled",
] as const;

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

describe("Spec v8 Section 12.2 / 12.3: Admin Answer Flow Rebuild Verification", () => {
  let mockReload: ReturnType<typeof vi.fn>;
  let mockSave: ReturnType<typeof vi.fn>;
  let mockSetFlowToggle: ReturnType<typeof vi.fn>;
  let mockSetLowContextThreshold: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    roleState.role = "admin";
    window.localStorage.setItem("clara_ui_language", "vi");

    mockReload = vi.fn(async () => {});
    mockSave = vi.fn(async () => true);
    mockSetFlowToggle = vi.fn();
    mockSetLowContextThreshold = vi.fn();

    (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isSaving: false,
      isDirty: false,
      error: "",
      message: "",
      reload: mockReload,
      save: mockSave,
      setSourceEnabled: vi.fn(),
      setSourcePriority: vi.fn(),
      setSourceWeight: vi.fn(),
      setSourceCategory: vi.fn(),
      setFlowToggle: mockSetFlowToggle,
      setLowContextThreshold: mockSetLowContextThreshold,
      setRetrievalMetricK: vi.fn(),
      flowToggleKeys: [...FLOW_KEYS],
    });

    vi.spyOn(systemLib, "getSystemFlowEvents").mockResolvedValue({
      items: [],
      latestSequence: 0,
      total: 0,
    } as any);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  describe("1. AdminCommandStrip Adoption & Shell Integration", () => {
    it("renders AdminCommandStrip with answer-flow active tab and top-local navigation", async () => {
      render(<AdminAnswerFlowPage />);

      await waitFor(() => {
        expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();
      });

      // Verify command strip tabs
      expect(screen.getByText("Tổng quan")).toBeInTheDocument();
      expect(screen.getByText("Nguồn tri thức")).toBeInTheDocument();
      expect(screen.getByText("Luồng trả lời")).toBeInTheDocument();
      expect(screen.getByText("Giám sát")).toBeInTheDocument();
      expect(screen.getByText("Phân tích")).toBeInTheDocument();
      expect(screen.getByText("Thêm")).toBeInTheDocument();
    });

    it("renders with CommandCenterLayout in admin workspace with DENSE layout mode", async () => {
      render(<AdminAnswerFlowPage />);

      const commandCenter = document.querySelector('[data-archetype="command-center"]');
      expect(commandCenter).toBeInTheDocument();
      expect(commandCenter).toHaveAttribute("data-workspace", "admin");

      await waitFor(() => {
        expect(screen.getByText("Luồng Suy luận & Điều phối Trả lời")).toBeInTheDocument();
      });
    });

    it("blocks non-admin users with 403 Access Denied alert", async () => {
      roleState.role = "doctor";
      render(<AdminAnswerFlowPage />);

      expect(screen.getByText(/Từ chối quyền truy cập/i)).toBeInTheDocument();
      expect(screen.queryByText("Luồng Suy luận & Điều phối Trả lời")).not.toBeInTheDocument();
    });
  });

  describe("2. Flow Flag Controls & Low Context Threshold Slider", () => {
    it("renders all 10 flow toggle flags with active counts and health tone", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Bảng Điều khiển Cờ Luồng & Ngưỡng Ngữ cảnh (Flow Flags & Threshold Tuning)")).toBeInTheDocument();
      });

      // Status bar metrics
      expect(screen.getByText("Flow 10/10")).toBeInTheDocument();
      expect(screen.getByText("Health: ổn định")).toBeInTheDocument();
      expect(screen.getByText("low_context_threshold: 0.35")).toBeInTheDocument();
      expect(screen.getByText("Generation fail-closed")).toBeInTheDocument();

      // Groups
      expect(screen.getByText("Phân tầng & Điều hướng (Routing)")).toBeInTheDocument();
      expect(screen.getByText("Truy xuất Bằng chứng (Multi-source Retrieval)")).toBeInTheDocument();
      expect(screen.getByText("Kiểm chứng Bằng chứng & Cổng An toàn (Verification & FIDES Guard)")).toBeInTheDocument();

      // Flag items (checking occurrences across visualizer/panel)
      expect(screen.getAllByText("Role Router").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Intent Router").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Scientific Retrieval").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Web Retrieval").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("File Retrieval").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Evidence Reranker").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("GraphRAG").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Rule Verification").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("NLI Model").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("RAG NLI").length).toBeGreaterThanOrEqual(1);
    });

    it("triggers setFlowToggle when clicking a flow flag toggle button", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Toggle Role Router" })).toBeInTheDocument();
      });

      const roleRouterToggle = screen.getByRole("button", { name: "Toggle Role Router" });
      fireEvent.click(roleRouterToggle);

      expect(mockSetFlowToggle).toHaveBeenCalledWith("role_router_enabled", false);
    });

    it("renders low context threshold slider and number input, and updates value", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByLabelText("Low Context Threshold")).toBeInTheDocument();
      });

      const slider = screen.getByLabelText("Low Context Threshold");
      expect(slider).toHaveValue("0.35");

      fireEvent.change(slider, { target: { value: "0.45" } });
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.45);

      const numberInput = screen.getByLabelText("Low Context Threshold Number");
      fireEvent.change(numberInput, { target: { value: "0.2" } });
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.2);
    });

    it("supports quick threshold presets (Strict 0.15, Standard 0.30, Permissive 0.50)", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Nghiêm ngặt (0.15)" })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Nghiêm ngặt (0.15)" }));
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.15);

      fireEvent.click(screen.getByRole("button", { name: "Chuẩn (0.30)" }));
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.3);

      fireEvent.click(screen.getByRole("button", { name: "Mở rộng (0.50)" }));
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.5);
    });

    it("displays degraded health label when fewer flow flags are enabled", async () => {
      const degradedConfig = {
        ...mockConfig,
        rag_flow: {
          ...mockConfig.rag_flow,
          role_router_enabled: false,
          intent_router_enabled: false,
          scientific_retrieval_enabled: false,
          web_retrieval_enabled: false,
          file_retrieval_enabled: false,
          rag_reranker_enabled: false,
          rag_graphrag_enabled: false,
        },
      };

      (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        config: degradedConfig,
        isLoading: false,
        isSaving: false,
        isDirty: false,
        error: "",
        message: "",
        reload: mockReload,
        save: mockSave,
        setFlowToggle: mockSetFlowToggle,
        setLowContextThreshold: mockSetLowContextThreshold,
        flowToggleKeys: [...FLOW_KEYS],
      });

      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Health: cần kiểm tra")).toBeInTheDocument();
      });
    });
  });

  describe("3. Flow Topology Visualization & Interactive Node Inspector", () => {
    it("renders pipeline topology canvas and interactive node inspector with default node", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Sơ đồ Topology Pipeline & Stage Inspector")).toBeInTheDocument();
      });

      // Default node inspector should show Role Router
      expect(screen.getByText("Node Inspector")).toBeInTheDocument();
      expect(screen.getAllByText("Role Router").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("normal / researcher / doctor / admin").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Ánh xạ role vào policy/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Ghi chú Rủi ro & Bị chặn")).toBeInTheDocument();
    });

    it("switches node inspector when selecting a node shortcut", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Intent Router" })).toBeInTheDocument();
      });

      const intentRouterBtn = screen.getByRole("button", { name: "Intent Router" });
      fireEvent.click(intentRouterBtn);

      await waitFor(() => {
        expect(screen.getAllByText("Intent Router").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("quick / evidence / deep").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/Nhận diện intent và chọn profile retrieval/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it("renders verification node specific threshold tuning when verification stage is selected", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "verification + contradiction_miner" })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "verification + contradiction_miner" }));

      await waitFor(() => {
        expect(screen.getByText("Điều chỉnh Ngưỡng Kiểm chứng")).toBeInTheDocument();
        expect(screen.getByLabelText("Inspector Low Context Threshold Slider")).toBeInTheDocument();
      });

      const inspectorSlider = screen.getByLabelText("Inspector Low Context Threshold Slider");
      fireEvent.change(inspectorSlider, { target: { value: "0.4" } });
      expect(mockSetLowContextThreshold).toHaveBeenCalledWith(0.4);
    });

    it("toggles node status from within the inspector", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Cờ kích hoạt node")).toBeInTheDocument();
      });

      // Role Router has ON button in inspector
      const onBtn = screen.getAllByRole("button", { name: "ON" })[0];
      fireEvent.click(onBtn);

      expect(mockSetFlowToggle).toHaveBeenCalled();
    });
  });

  describe("4. Runtime Inference Debugger", () => {
    it("renders runtime inference debugger with simulation controls", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Debugger Luồng Trả lời Theo Thời gian Thực")).toBeInTheDocument();
      });

      expect(screen.getByLabelText("Debug Simulation Low Context Score")).toBeInTheDocument();
      expect(screen.getAllByText("quick-web").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("evidence-heavy").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("low-context").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("upload-first").length).toBeGreaterThanOrEqual(1);
    });

    it("updates simulation score when dragging debug low-context slider", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByLabelText("Debug Simulation Low Context Score")).toBeInTheDocument();
      });

      const debugSlider = screen.getByLabelText("Debug Simulation Low Context Score");
      fireEvent.change(debugSlider, { target: { value: "0.6" } });

      expect(debugSlider).toHaveValue("0.6");
    });
  });

  describe("5. Telemetry & Ancillary Panes", () => {
    it("tracks admin answer flow viewed event on mount", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(trackAdminSurfaceViewed).toHaveBeenCalledWith({ view: "answer_flow" });
      });
    });

    it("renders Council Multi-Agent Flow and Flow Signal Blocks", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByText("Council Flow")).toBeInTheDocument();
        expect(screen.getByText("Flow Signal Blocks")).toBeInTheDocument();
      });
    });
  });

  describe("6. Save and Reload Actions", () => {
    it("handles reload button click", async () => {
      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Tải lại/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Tải lại/i }));
      expect(mockReload).toHaveBeenCalled();
    });

    it("enables save button and executes save when config is dirty", async () => {
      (useControlTowerConfig as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        config: mockConfig,
        isLoading: false,
        isSaving: false,
        isDirty: true,
        error: "",
        message: "",
        reload: mockReload,
        save: mockSave,
        setFlowToggle: mockSetFlowToggle,
        setLowContextThreshold: mockSetLowContextThreshold,
        flowToggleKeys: [...FLOW_KEYS],
      });

      render(<AdminAnswerFlowPanel />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Lưu Cấu hình/i })).not.toBeDisabled();
      });

      fireEvent.click(screen.getByRole("button", { name: /Lưu Cấu hình/i }));
      expect(mockSave).toHaveBeenCalled();
    });
  });
});
