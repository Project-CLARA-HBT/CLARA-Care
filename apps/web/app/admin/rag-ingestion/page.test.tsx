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

import AdminRagIngestionPage from "@/app/admin/rag-ingestion/page";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AdminRagIngestionPage (Spec v5 Section 6.69)", () => {
  it("renders dense table of sources and opens ETL stage inspector", async () => {
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
            ],
          },
        });
      }
      if (url === "/admin/rag/stats") {
        return Promise.resolve({
          data: {
            documents: 1500,
            chunks: 12000,
            degraded_chunks: 0,
            coverage_pct: 98.5,
            sources_total: 10,
            sources_enabled: 8,
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(<AdminRagIngestionPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
      expect(screen.getByText("duoc_thu_qg")).toBeInTheDocument();
    });

    // Inspect stage drawer
    const inspectBtn = screen.getByRole("button", { name: /inspect/i });
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      expect(screen.getByText(/ETL Pipeline Stages/i)).toBeInTheDocument();
      expect(screen.getByText("1. Fetch")).toBeInTheDocument();
      expect(screen.getByText("2. Insert")).toBeInTheDocument();
    });
  });
});
