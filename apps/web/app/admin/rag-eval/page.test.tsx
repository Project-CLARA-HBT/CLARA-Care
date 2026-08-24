import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockApiGet = vi.fn();
const mockApiPost = vi.fn();

vi.mock("@/lib/http-client", () => ({
  default: {
    get: (url: string) => mockApiGet(url),
    post: (url: string, data?: unknown) => mockApiPost(url, data),
  },
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

import AdminRagEvalPage from "@/app/admin/rag-eval/page";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AdminRagEvalPage (Spec v5 Section 6.68)", () => {
  it("renders AdminShell, run controls, and runs evaluation to populate tables", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        run_id: "eval-run-101",
        status: "completed",
        accepted: true,
      },
    });

    mockApiGet.mockResolvedValue({
      data: {
        run_id: "eval-run-101",
        results: [
          {
            qid: "VN-Q01",
            recall_at_k: 0.85,
            ndcg_at_k: 0.82,
            faithfulness: 0.95,
            citation_acc: 0.90,
            latency_ms: 120,
            query_text: "Triệu chứng sốt xuất huyết Dengue",
          },
          {
            qid: "VN-Q02",
            recall_at_k: 0.40,
            ndcg_at_k: 0.35,
            faithfulness: 0.45,
            citation_acc: 0.50,
            latency_ms: 250,
            query_text: "Liều dùng Paracetamol ở trẻ em",
            failure_reason: "Retrieval missed ground truth in top 10",
          },
        ],
        recall_at_k: 0.625,
        ndcg_at_k: 0.585,
        faithfulness: 0.70,
        citation_acc: 0.70,
      },
    });

    render(<AdminRagEvalPage />);

    // Click run evaluation button
    const runBtn = screen.getByRole("button", { name: /run/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith("/admin/rag/eval/run", { k: 10 });
      expect(mockApiGet).toHaveBeenCalledWith("/admin/rag/eval/results/eval-run-101");
    });

    // Check KPI cards rendered
    await waitFor(() => {
      expect(screen.getByText("VN-Q01")).toBeInTheDocument();
      expect(screen.getByText("VN-Q02")).toBeInTheDocument();
    });

    // Inspect question drawer
    const inspectBtns = screen.getAllByRole("button", { name: /inspect/i });
    fireEvent.click(inspectBtns[1]); // inspect VN-Q02

    await waitFor(() => {
      expect(screen.getByText("Question Inspector")).toBeInTheDocument();
      expect(screen.getByText(/Retrieval missed ground truth in top 10/i)).toBeInTheDocument();
      expect(screen.getByText(/Liều dùng Paracetamol ở trẻ em/i)).toBeInTheDocument();
    });
  });
});
