import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminAnswerFlowPage from "@/app/admin/answer-flow/page";
import * as systemLib from "@/lib/system";

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

describe("AdminAnswerFlowPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("clara_ui_language", "vi");

    vi.spyOn(systemLib, "getControlTowerConfig").mockResolvedValue({
      rag_sources: [],
      rag_flow: {
        role_router_enabled: true,
        intent_router_enabled: true,
        rule_verification_enabled: true,
        nli_model_enabled: true,
        rag_reranker_enabled: true,
        rag_nli_enabled: true,
        rag_graphrag_enabled: true,
        scientific_retrieval_enabled: true,
        web_retrieval_enabled: false,
        file_retrieval_enabled: false,
        low_context_threshold: 0.2,
      },
    } as any);

    vi.spyOn(systemLib, "getSystemFlowEvents").mockResolvedValue({
      events: [],
      total: 0,
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders AdminShell with answer-flow active tab and Flow control components", async () => {
    render(<AdminAnswerFlowPage />);

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Node Inspector")).toBeInTheDocument();
      expect(screen.getByText("Council Flow")).toBeInTheDocument();
      expect(screen.getByText("Flow Signal Blocks")).toBeInTheDocument();
    });
  });
});
