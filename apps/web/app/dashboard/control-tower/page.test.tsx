import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ControlTowerPage from "./page";
import { getControlTowerConfig, updateControlTowerConfig } from "@/lib/system";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/system", () => ({
  getControlTowerConfig: vi.fn(),
  updateControlTowerConfig: vi.fn(),
}));

const mockConfig = {
  rag_sources: [
    {
      id: "pubmed",
      name: "PubMed Central",
      category: "medical_literature",
      priority: 1,
      weight: 1.0,
      enabled: true,
    },
    {
      id: "dav_gov_vn",
      name: "Cục Quản lý Dược (DAV)",
      category: "national_formulary",
      priority: 2,
      weight: 1.0,
      enabled: true,
    },
  ],
  rag_flow: {
    role_router_enabled: true,
    intent_router_enabled: true,
    rule_verification_enabled: true,
    nli_model_enabled: true,
    rag_nli_enabled: true,
    rag_reranker_enabled: true,
    rag_graphrag_enabled: true,
    verification_enabled: true,
    deepseek_fallback_enabled: false,
    low_context_threshold: 0.25,
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

describe("ControlTowerPage (/dashboard/control-tower)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getControlTowerConfig).mockResolvedValue(mockConfig);
    vi.mocked(updateControlTowerConfig).mockResolvedValue(mockConfig);
  });

  it("loads and displays RAG sources, metrics, and flow orchestration controls", async () => {
    render(<ControlTowerPage />);

    await waitFor(() => {
      expect(screen.getByText("Control Tower")).toBeInTheDocument();
      expect(screen.getByText("RAG Source & Flow Orchestration Plane")).toBeInTheDocument();
    });

    // Sources table
    expect(screen.getByText("PubMed Central")).toBeInTheDocument();
    expect(screen.getByText("Cục Quản lý Dược (DAV)")).toBeInTheDocument();

    // KPI cards
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getAllByText("Enabled").length).toBeGreaterThanOrEqual(1);

    // Guardrail and flow flags
    expect(screen.getByText("Low-context guardrail")).toBeInTheDocument();
    expect(screen.getByText("Role Router")).toBeInTheDocument();
    expect(screen.getByText("Intent Router")).toBeInTheDocument();
    expect(screen.getByText("Rule Verification")).toBeInTheDocument();
  });

  it("allows toggling sources and saving updated configuration", async () => {
    render(<ControlTowerPage />);

    await waitFor(() => {
      expect(screen.getByText("PubMed Central")).toBeInTheDocument();
    });

    // Change priority for pubmed
    const priorityInput = screen.getByLabelText(/Priority cho PubMed Central/i);
    fireEvent.change(priorityInput, { target: { value: "5" } });

    // Save config
    const saveButton = screen.getByRole("button", { name: /Lưu cấu hình/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(updateControlTowerConfig).toHaveBeenCalledWith(expect.objectContaining({
        rag_sources: expect.arrayContaining([
          expect.objectContaining({ id: "pubmed", priority: 5 }),
        ]),
      }));
      expect(screen.getByText("Đã lưu cấu hình nguồn RAG và flow trả lời.")).toBeInTheDocument();
    });
  });

  it("toggles flow flags and updates thresholds", async () => {
    render(<ControlTowerPage />);

    await waitFor(() => {
      expect(screen.getByText("Role Router")).toBeInTheDocument();
    });

    // Change threshold
    const thresholdInput = screen.getByLabelText(/Threshold \(0 - 1\)/i);
    fireEvent.change(thresholdInput, { target: { value: "0.4" } });

    // Save config
    const saveButton = screen.getByRole("button", { name: /Lưu cấu hình/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(updateControlTowerConfig).toHaveBeenCalledWith(expect.objectContaining({
        rag_flow: expect.objectContaining({
          low_context_threshold: 0.4,
        }),
      }));
    });
  });
});
