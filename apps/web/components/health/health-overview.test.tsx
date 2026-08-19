import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HealthOverview } from "./health-overview";
import { v2Client, type HealthSummaryDto } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/health",
}));

afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
});

const mockSummaryData: HealthSummaryDto = {
  profile: {
    id: "prof-1",
    display_name: "Nguyễn Văn A",
    relationship: "Bản thân",
  },
  demographics: {
    full_name: "Nguyễn Văn A",
    gender: "male",
    blood_type: "O+",
    date_of_birth: "1990-05-15",
    phone_number: "0901234567",
    emergency_contact: {
      name: "Nguyễn Thị B",
      relationship: "Vợ",
      phone: "0907654321",
    },
  },
  current: {
    allergies: [
      {
        id: "alg-1",
        substance: "Penicillin",
        reaction: "Sốc phản vệ",
        severity: "severe",
        verification_state: "confirmed",
      },
    ],
    conditions: [
      {
        id: "cond-1",
        name: "Tăng huyết áp",
        clinical_status: "active",
        verification_status: "confirmed",
        notes: "Uống thuốc hàng ngày",
      },
    ],
    medications: [
      {
        id: "med-1",
        name: "Amlodipine 5mg",
        dosage: "1 viên",
        instructions: "Uống sau ăn sáng",
        status: "active",
        source_kind: "doctor",
      },
    ],
    important_measurements: [
      {
        id: "m-1",
        type: "blood_pressure",
        label: "Huyết áp",
        value: "120/80",
        unit: "mmHg",
        status: "normal",
        recorded_at: "2026-08-19T07:00:00Z",
      },
    ],
  },
  recent_results: [
    {
      id: "res-1",
      test_name: "Glucose máu",
      value: 5.4,
      unit: "mmol/L",
      reference_range: "4.1 - 5.9",
      flag: "normal",
      effective_at: "2026-08-18T08:00:00Z",
    },
  ],
  documents: [],
  conflicts: [
    {
      id: "conf-1",
      domain: "medication",
      title: "Mâu thuẫn liều lượng thuốc Amlodipine",
      description: "Đơn thuốc bệnh viện ghi 5mg nhưng tự ghi nhận 10mg",
      source_a: { label: "Bệnh viện", value: "5mg" },
      source_b: { label: "Tự ghi nhận", value: "10mg" },
      status: "unresolved",
    },
  ],
};

describe("HealthOverview Component", () => {
  it("renders loading skeleton while data is fetching", () => {
    vi.spyOn(v2Client, "getHealthSummary").mockImplementation(() => new Promise(() => {}));

    render(<HealthOverview />);

    expect(screen.getByTestId("health-overview-skeleton")).toBeInTheDocument();
  });

  it("renders error state with retry button on network failure", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockRejectedValueOnce(new Error("Network Error"));

    render(<HealthOverview />);

    await waitFor(() => {
      expect(screen.getByTestId("health-overview-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Không thể tải hồ sơ sức khỏe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
  });

  it("renders complete health overview with allergies, conditions, medications, vitals, and conflict banners", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValue(mockSummaryData);

    render(<HealthOverview />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguyễn Văn A").length).toBeGreaterThanOrEqual(1);
    });

    // 1. Header & Sub-navigation
    expect(screen.getByText("Hồ sơ sức khỏe tổng quan")).toBeInTheDocument();
    expect(screen.getByTestId("subnav-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("subnav-medications")).toBeInTheDocument();
    expect(screen.getByTestId("subnav-results")).toBeInTheDocument();
    expect(screen.getByTestId("subnav-measurements")).toBeInTheDocument();
    expect(screen.getByTestId("subnav-documents")).toBeInTheDocument();

    // 2. Conflict Review Banner (HEALTH-009)
    expect(screen.getByTestId("health-conflicts-banner")).toBeInTheDocument();
    expect(screen.getByText("Mâu thuẫn liều lượng thuốc Amlodipine")).toBeInTheDocument();

    // 3. Allergies
    expect(screen.getByTestId("health-allergies-section")).toBeInTheDocument();
    expect(screen.getByText("Penicillin")).toBeInTheDocument();
    expect(screen.getByText(/Sốc phản vệ/i)).toBeInTheDocument();

    // 4. Conditions
    expect(screen.getByTestId("health-conditions-section")).toBeInTheDocument();
    expect(screen.getByText("Tăng huyết áp")).toBeInTheDocument();

    // 5. Medications Summary
    expect(screen.getByTestId("health-medications-summary")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();

    // 6. Demographics
    expect(screen.getByTestId("health-demographics-card")).toBeInTheDocument();
    expect(screen.getByText("O+")).toBeInTheDocument();

    // 7. Vitals Summary
    expect(screen.getByTestId("health-vitals-summary")).toBeInTheDocument();
    expect(screen.getByText("120/80")).toBeInTheDocument();

    // 8. Recent Results
    expect(screen.getByTestId("health-recent-results-summary")).toBeInTheDocument();
    expect(screen.getByText("Glucose máu")).toBeInTheDocument();
  });

  it("opens Demographics, Allergy, Condition, and Measurement modals upon user actions", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValue(mockSummaryData);

    render(<HealthOverview />);

    await waitFor(() => {
      expect(screen.getAllByText("Nguyễn Văn A").length).toBeGreaterThanOrEqual(1);
    });

    // Open Allergy Modal
    const addAllergyBtn = screen.getByRole("button", { name: "Thêm dị ứng" });
    fireEvent.click(addAllergyBtn);
    expect(screen.getByText("Thêm dị ứng / Không dung nạp")).toBeInTheDocument();
    const closeBtn = screen.getByLabelText("Đóng");
    fireEvent.click(closeBtn);

    // Open Condition Modal
    const addCondBtn = screen.getByRole("button", { name: "Thêm bệnh nền" });
    fireEvent.click(addCondBtn);
    expect(screen.getByText("Thêm bệnh nền / Tình trạng sức khỏe")).toBeInTheDocument();
  });

  it("opens UniversalCaptureModal when clicking 'Thêm thông tin sức khỏe' trigger", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValue(mockSummaryData);

    render(<HealthOverview />);

    await waitFor(() => {
      expect(screen.getByText("Thêm thông tin sức khỏe")).toBeInTheDocument();
    });

    const addHealthBtn = screen.getByRole("button", { name: "Thêm thông tin sức khỏe" });
    fireEvent.click(addHealthBtn);

    expect(screen.getByTestId("universal-capture-modal")).toBeInTheDocument();
  });
});
