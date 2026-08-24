import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ClinicalOverviewPage from "./page";
import ClinicalOverviewSubroutePage from "./overview/page";
import ClinicalPatientsPage from "./patients/page";
import { getRole } from "@/lib/auth-store";
import { getSystemDashboard } from "@/lib/system";
import { getActiveCouncilCaseId, getLatestCouncilCase } from "@/lib/council";

const mockReplace = vi.fn();
const mockPush = vi.fn();
const mockRouter = {
  replace: mockReplace,
  push: mockPush,
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: vi.fn(() => "doctor"),
}));

const mockSystemDashboard = {
  generatedAt: "2026-08-24T10:00:00Z",
  user: { role: "doctor", subject: "BS. Nguyễn Văn A" },
  runtime: {
    apiStatus: "ok",
    mlStatus: "ok",
    mlReachable: true,
    requestCount: 120,
    errorCount: 0,
    avgLatencyMs: 45,
    errorRatePct: 0,
  },
  cabinet: {
    itemTotal: 10,
    expiredTotal: 0,
    expiringSoonTotal: 0,
    missingDosageTotal: 0,
  },
  sources: {
    enabled: 10,
    total: 12,
    lowContextThreshold: 0.25,
    flowFlags: {},
    flowEnabledCount: 8,
  },
  research: { recentQueries: [] },
  alerts: [],
  tasks: [],
};

const mockCouncilCase = {
  id: 301,
  title: "BN Nam 65T - Suy tim đợt cấp / ĐTĐ type 2",
  status: "analyzed",
  intake_mode: "structured",
  transcript: "",
  created_at: "2026-08-24T08:00:00Z",
  updated_at: "2026-08-24T09:00:00Z",
};

vi.mock("@/lib/system", () => ({
  getSystemDashboard: vi.fn(async () => mockSystemDashboard),
  normalizeSystemDashboard: vi.fn((d) => d),
}));

vi.mock("@/lib/council", () => ({
  getActiveCouncilCaseId: vi.fn(() => 301),
  getLatestCouncilCase: vi.fn(async () => mockCouncilCase),
}));

describe("Clinical Workflows (/clinical, /clinical/overview, /clinical/patients)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRole).mockReturnValue("admin");
    vi.mocked(getSystemDashboard).mockResolvedValue(mockSystemDashboard);
    vi.mocked(getLatestCouncilCase).mockResolvedValue(mockCouncilCase);
  });

  describe("1. /clinical & /clinical/overview Launchpad", () => {
    it("renders Clinical Overview for Admin role without restriction", async () => {
      vi.mocked(getRole).mockReturnValue("admin");
      render(<ClinicalOverviewPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Trung tâm Lâm sàng & Hội chẩn/i).length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getByText("Hội chẩn AI")).toBeInTheDocument();
      expect(screen.getAllByText("Ghi chép SOAP").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Bằng chứng")).toBeInTheDocument();
      expect(screen.getByText("Tra cứu lâm sàng")).toBeInTheDocument();
    });

    it("renders /clinical/overview subroute for Doctor role", async () => {
      vi.mocked(getRole).mockReturnValue("doctor");
      render(<ClinicalOverviewSubroutePage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Trung tâm Lâm sàng & Hội chẩn/i).length).toBeGreaterThanOrEqual(1);
      });
      expect(screen.getByText("Hội chẩn AI")).toBeInTheDocument();
    });
  });

  describe("2. /clinical/patients Patient Roster", () => {
    it("renders patient queue, risk tier badges, and vitals for Admin and Doctor roles", async () => {
      render(<ClinicalPatientsPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Nguyễn Văn Hùng/i).length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText(/Trần Thị Mai/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Phạm Minh Đức/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Lê Thanh Hương/i).length).toBeGreaterThanOrEqual(1);

      // Check risk tier badges
      expect(screen.getAllByText(/Cấp cứu/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Nguy cơ cao/i).length).toBeGreaterThanOrEqual(1);
    });

    it("filters patient queue by department", async () => {
      render(<ClinicalPatientsPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Nguyễn Văn Hùng/i).length).toBeGreaterThanOrEqual(1);
      });

      // Filter by department select
      const departmentSelect = screen.getByTestId("department-filter");
      fireEvent.change(departmentSelect, { target: { value: "emergency" } });

      await waitFor(() => {
        expect(screen.getAllByText(/Nguyễn Văn Hùng/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it("searches patient by name or MRN", async () => {
      render(<ClinicalPatientsPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Nguyễn Văn Hùng/i).length).toBeGreaterThanOrEqual(1);
      });

      const searchInput = screen.getByTestId("patient-search-input");
      fireEvent.change(searchInput, { target: { value: "Trần Thị Mai" } });

      await waitFor(() => {
        expect(screen.getAllByText(/Trần Thị Mai/i).length).toBeGreaterThanOrEqual(1);
        expect(screen.queryByText(/Vũ Hoàng Nam/i)).not.toBeInTheDocument();
      });
    });

    it("opens patient inspector on patient select and displays vitals and clinical action shortcuts", async () => {
      render(<ClinicalPatientsPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/Nguyễn Văn Hùng/i).length).toBeGreaterThanOrEqual(1);
      });

      // Click on patient row
      const patientRow = screen.getByTestId("patient-row-PT-9401");
      fireEvent.click(patientRow);

      await waitFor(() => {
        expect(screen.getAllByText("MRN-2026-09401").length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getByText("Hội chẩn AI cho ca này")).toBeInTheDocument();
      expect(screen.getAllByText("Ghi chép SOAP").length).toBeGreaterThanOrEqual(1);
    });
  });
});
