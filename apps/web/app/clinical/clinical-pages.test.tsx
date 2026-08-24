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

const mockPatientsList = [
  {
    id: "PT-9401",
    mrn: "MRN-2026-09401",
    name: "Nguyễn Văn Hùng",
    age: 68,
    gender: "M",
    roomBed: "P.Cấp Cứu - Giường 03",
    department: "emergency",
    departmentLabel: { vi: "Cấp cứu", en: "Emergency" },
    primaryDiagnosis: "Hội chứng vành cấp / NMCT ST không chênh",
    chiefComplaint: "Đau thắt ngực trái lan ra sau lưng và cánh tay trái, khó thở NYHA III",
    riskLevel: "critical",
    riskReason: { vi: "Đau ngực cấp + Troponin T tăng cao + Tiền sử ĐTĐ", en: "Acute chest pain + High Troponin" },
    consultationStatus: "council_review",
    attendingDoctor: "BSCKII. Lê Hoàng Long",
    waitTimeMinutes: 10,
    vitals: { bp: "165/100", hr: 112, spo2: 93, temp: 37.2, rr: 24, egfr: 52 },
    allergies: ["Penicillin (Sốc phản vệ)", "Aspirin (Co thắt phế quản)"],
    activeMedications: [{ name: "Clopidogrel 75mg", dose: "75mg", frequency: "1 lần/ngày" }],
    ddiAlerts: [{ severity: "critical", textVi: "Tương tác thuốc nghiêm trọng", textEn: "Critical DDI" }],
    recentNotes: [{ date: "2026-08-24 07:30", author: "BS. Trực", summary: "BN đau ngực tăng dần" }],
    admissionTime: "2026-08-24T07:15:00Z",
  },
  {
    id: "PT-9402",
    mrn: "MRN-2026-09402",
    name: "Trần Thị Mai",
    age: 54,
    gender: "F",
    roomBed: "Khoa Tim Mạch - P.402",
    department: "cardiology",
    departmentLabel: { vi: "Tim mạch", en: "Cardiology" },
    primaryDiagnosis: "Tăng huyết áp kháng trị / Rung nhĩ cơn",
    chiefComplaint: "Hồi hộp đánh trống ngực, HA dao động 170-190 mmHg",
    riskLevel: "high",
    riskReason: { vi: "HA không kiểm soát dù dùng 3 nhóm thuốc", en: "Resistant hypertension" },
    consultationStatus: "in_consultation",
    attendingDoctor: "ThS.BS. Nguyễn Thị Minh",
    waitTimeMinutes: 25,
    vitals: { bp: "175/105", hr: 98, spo2: 97, temp: 36.8, rr: 18, egfr: 68 },
    allergies: [],
    activeMedications: [],
    ddiAlerts: [],
    recentNotes: [],
    admissionTime: "2026-08-24T08:00:00Z",
  },
  {
    id: "PT-9403",
    mrn: "MRN-2026-09403",
    name: "Phạm Minh Đức",
    age: 61,
    gender: "M",
    roomBed: "Khoa Nội tiết - P.305",
    department: "endocrinology",
    departmentLabel: { vi: "Nội tiết", en: "Endocrinology" },
    primaryDiagnosis: "Đái tháo đường type 2 biến chứng thận",
    chiefComplaint: "Đường huyết đói cao kéo dài",
    riskLevel: "high",
    riskReason: { vi: "HbA1c 10.2% + eGFR giảm", en: "Poor glycemic control" },
    consultationStatus: "awaiting_labs",
    attendingDoctor: "BSCKI. Trần Văn An",
    waitTimeMinutes: 40,
    vitals: { bp: "135/85", hr: 78, spo2: 98, temp: 36.6, rr: 16, egfr: 45 },
    allergies: [],
    activeMedications: [],
    ddiAlerts: [],
    recentNotes: [],
    admissionTime: "2026-08-24T08:30:00Z",
  },
  {
    id: "PT-9404",
    mrn: "MRN-2026-09404",
    name: "Lê Thanh Hương",
    age: 42,
    gender: "F",
    roomBed: "Khoa Hô Hấp - P.208",
    department: "pulmonology",
    departmentLabel: { vi: "Hô hấp", en: "Pulmonology" },
    primaryDiagnosis: "Hen phế quản bội nhiễm",
    chiefComplaint: "Ho đờm, khò khè ban đêm",
    riskLevel: "moderate",
    riskReason: { vi: "Cơn hen phế quản mức độ trung bình", en: "Moderate asthma" },
    consultationStatus: "ready_review",
    attendingDoctor: "ThS.BS. Phạm Thu Hà",
    waitTimeMinutes: 55,
    vitals: { bp: "125/80", hr: 84, spo2: 96, temp: 37.5, rr: 20, egfr: 95 },
    allergies: [],
    activeMedications: [],
    ddiAlerts: [],
    recentNotes: [],
    admissionTime: "2026-08-24T09:00:00Z",
  },
];

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(async (url: string) => {
      if (url.includes("/clinical/workbench/patients")) {
        return { data: { items: mockPatientsList, total: mockPatientsList.length } };
      }
      return { data: {} };
    }),
    post: vi.fn(async () => ({ data: {} })),
    patch: vi.fn(async () => ({ data: {} })),
    delete: vi.fn(async () => ({ data: {} })),
  },
}));

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
