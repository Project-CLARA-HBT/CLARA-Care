import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminKnowledgeSourcesPage from "@/app/admin/knowledge-sources/page";
import * as researchLib from "@/lib/research";
import * as systemLib from "@/lib/system";
import api from "@/lib/http-client";

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

describe("AdminKnowledgeSourcesPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("clara_ui_language", "vi");

    vi.spyOn(researchLib, "listKnowledgeSources").mockResolvedValue([
      {
        id: 1,
        name: "Dược thư Quốc gia Việt Nam",
        description: "Bộ Y tế",
        documents_count: 15,
        is_active: true,
      },
    ]);

    vi.spyOn(researchLib, "listKnowledgeSourceDocuments").mockResolvedValue([
      {
        id: 101,
        source_id: 1,
        filename: "duoc_thu_2025.pdf",
        content_type: "application/pdf",
        preview: "Dược thư Quốc gia",
        size: 1024000,
        token_count: 50000,
        is_active: true,
      },
    ]);

    vi.spyOn(researchLib, "listSourceHubCatalog").mockResolvedValue([
      { key: "pubmed", label: "PubMed", description: "PubMed MEDLINE", supports_live_sync: true },
    ]);

    vi.spyOn(researchLib, "listSourceHubRecords").mockResolvedValue([
      {
        id: "rec-1",
        source: "pubmed",
        title: "Clinical Trial on Type 2 Diabetes",
        snippet: "A study on metformin efficacy",
        url: "https://pubmed.ncbi.nlm.nih.gov/12345",
        published_at: "2026-03-01T00:00:00Z",
        synced_at: "2026-04-01T00:00:00Z",
        metadata: {},
      },
    ]);

    vi.spyOn(systemLib, "getControlTowerConfig").mockResolvedValue({
      rag_sources: [
        { id: "src_1", name: "Dược thư QG", priority: 1, weight: 1.0, enabled: true, category: "pharmacopeia" },
      ],
      rag_flow: {
        rule_verification_enabled: true,
        low_context_threshold: 0.2,
      },
    } as any);

    vi.spyOn(api, "get").mockImplementation((url: string) => {
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
                license_code: "BYT-VN",
                attribution: "Bộ Y tế Việt Nam",
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders AdminShell with knowledge-sources active tab and source management", async () => {
    render(<AdminKnowledgeSourcesPage />);

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("Dược thư Quốc gia Việt Nam").length).toBeGreaterThan(0);
      expect(screen.getByText("duoc_thu_2025.pdf")).toBeInTheDocument();
      expect(screen.getAllByText("Dược thư Quốc gia").length).toBeGreaterThan(0);
    });
  });
});
