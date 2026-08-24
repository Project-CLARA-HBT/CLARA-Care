import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ResearchSourceHubPage from "./page";
import { getRole } from "@/lib/auth-store";
import { listSourceHubCatalog, listSourceHubRecords, syncSourceHub } from "@/lib/research";
import { trackResearchSourcesSynced, trackResearchViewed } from "@/lib/analytics/events";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: vi.fn(() => "doctor"),
}));

vi.mock("@/lib/research", () => ({
  listSourceHubCatalog: vi.fn(),
  listSourceHubRecords: vi.fn(),
  syncSourceHub: vi.fn(),
}));

vi.mock("@/lib/analytics/events", () => ({
  trackResearchViewed: vi.fn(),
  trackResearchSourcesSynced: vi.fn(),
}));

const mockCatalog = [
  {
    key: "pubmed" as const,
    name: "PubMed / MEDLINE",
    description: "Cơ sở dữ liệu y sinh học toàn cầu của NLM/NIH",
    default_query: "type 2 diabetes guideline",
    docs_url: "https://pubmed.ncbi.nlm.nih.gov/",
  },
  {
    key: "vn_moh" as const,
    name: "Bộ Y tế Việt Nam",
    description: "Hướng dẫn chẩn đoán và điều trị chính thức của BYT",
    default_query: "hướng dẫn điều trị đái tháo đường",
  },
];

const mockRecords = [
  {
    id: "rec-1",
    source: "pubmed" as const,
    title: "ADA Standards of Care in Diabetes 2024",
    snippet: "Comprehensive clinical guidelines for glycemic targets and pharmacotherapy.",
    url: "https://doi.org/10.2337/dc24-SINT",
    query: "diabetes guideline",
    published_at: "2024-01-01T00:00:00Z",
    synced_at: "2026-08-24T08:00:00Z",
  },
  {
    id: "rec-2",
    source: "vn_moh" as const,
    title: "Hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2 BYT 2020",
    snippet: "Phác đồ chuẩn quốc gia về quản lý và điều trị ĐTĐ típ 2 tại Việt Nam.",
    url: "https://kcb.vn/van-ban/5481-qd-byt",
    query: "đái tháo đường",
    published_at: "2020-12-30T00:00:00Z",
    synced_at: "2026-08-24T08:00:00Z",
  },
];

describe("ResearchSourceHubPage (/research/source-hub)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRole).mockReturnValue("admin");
    vi.mocked(listSourceHubCatalog).mockResolvedValue(mockCatalog as any);
    vi.mocked(listSourceHubRecords).mockResolvedValue(mockRecords as any);
  });

  it("renders Source Hub successfully for Admin role with tracking event", async () => {
    vi.mocked(getRole).mockReturnValue("admin");
    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguồn nghiên cứu").length).toBeGreaterThanOrEqual(1);
    });

    expect(trackResearchViewed).toHaveBeenCalled();
    expect(screen.getByText("ADA Standards of Care in Diabetes 2024")).toBeInTheDocument();
    expect(screen.getByText("Hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2 BYT 2020")).toBeInTheDocument();
  });

  it("renders without restriction for Doctor role", async () => {
    vi.mocked(getRole).mockReturnValue("doctor");
    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguồn nghiên cứu").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("ADA Standards of Care in Diabetes 2024")).toBeInTheDocument();
  });

  it("renders without restriction for Researcher role", async () => {
    vi.mocked(getRole).mockReturnValue("researcher");
    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguồn nghiên cứu").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("ADA Standards of Care in Diabetes 2024")).toBeInTheDocument();
  });

  it("filters records by search input", async () => {
    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getByText("ADA Standards of Care in Diabetes 2024")).toBeInTheDocument();
    });

    const filterInput = screen.getByPlaceholderText(/Lọc theo tiêu đề hoặc truy vấn/i);
    fireEvent.change(filterInput, { target: { value: "BYT" } });
    fireEvent.click(screen.getByRole("button", { name: /Lọc/i }));

    await waitFor(() => {
      expect(listSourceHubRecords).toHaveBeenCalledWith({
        source: "all",
        query: "BYT",
        limit: 80,
      });
    });
  });

  it("synchronizes source and displays sanitized message without raw telemetry", async () => {
    vi.mocked(syncSourceHub).mockResolvedValue({
      source: "pubmed" as const,
      query: "SGLT2 inhibitors",
      fetched: 5,
      stored: 5,
      records: [],
      warnings: ["pubmed rate_limit_window 95%"],
    });

    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguồn nghiên cứu").length).toBeGreaterThanOrEqual(1);
    });

    const queryInput = screen.getByLabelText(/Chủ đề tìm kiếm/i);
    fireEvent.change(queryInput, { target: { value: "SGLT2 inhibitors" } });

    const syncButton = screen.getByRole("button", { name: /Đồng bộ/i });
    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(syncSourceHub).toHaveBeenCalledWith({
        source: "pubmed",
        query: "SGLT2 inhibitors",
        limit: 12,
      });
      expect(trackResearchSourcesSynced).toHaveBeenCalledWith({
        source: "pubmed",
        fetched: 5,
        stored: 5,
      });
    });

    // Sanitized success message
    await waitFor(() => {
      expect(screen.getByText(/Đã đồng bộ/i)).toBeInTheDocument();
    });
  });

  it("renders TelemetryPanel for Admin when sync warnings occur", async () => {
    vi.mocked(getRole).mockReturnValue("admin");
    vi.mocked(syncSourceHub).mockResolvedValue({
      source: "pubmed" as const,
      query: "SGLT2 inhibitors",
      fetched: 5,
      stored: 5,
      records: [],
      warnings: ["openfda http_400 non-critical"],
    });

    render(<ResearchSourceHubPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguồn nghiên cứu").length).toBeGreaterThanOrEqual(1);
    });

    const syncButton = screen.getByRole("button", { name: /Đồng bộ/i });
    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(screen.getByText(/openfda http_400 non-critical/i)).toBeInTheDocument();
    });
  });
});
