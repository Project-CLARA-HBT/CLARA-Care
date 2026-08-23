import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HealthPage from "./page";
import HealthTimelinePage from "./timeline/page";
import ConsumerMedicationsPage from "./medications/page";
import ResultsPage from "./results/page";
import MeasurementsPage from "./measurements/page";
import DocumentsPage from "./documents/page";
import { v2Client } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/health",
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const mockSummary = {
  profile: { id: "p-1", display_name: "Nguyễn Văn A" },
  demographics: { full_name: "Nguyễn Văn A", blood_type: "O+" },
  current: {
    allergies: [{ id: "a1", substance: "Penicillin", severity: "mild" }],
    conditions: [{ id: "c1", name: "Tăng huyết áp", clinical_status: "active" }],
    medications: [{ id: "m1", name: "Amlodipine", status: "active" }],
    important_measurements: [
      { id: "v1", type: "blood_pressure", label: "Huyết áp", value: "120/80", unit: "mmHg", recorded_at: "2026-08-19" },
    ],
  },
  recent_results: [
    { id: "r1", test_name: "Glucose máu", value: 5.4, unit: "mmol/L", reference_range: "4.1 - 5.9", flag: "normal", effective_at: "2026-08-19" },
  ],
  documents: [
    { id: "d1", title: "Đơn thuốc ngoại trú", kind: "prescription", recorded_at: "2026-08-19", source_name: "Bệnh viện Bạch Mai" },
  ],
  conflicts: [],
};

const mockTimeline = {
  items: [
    { id: "t1", title: "Kê đơn Amlodipine", kind: "medication", effective_at: "2026-08-19", state: "confirmed" },
  ],
  next_cursor: null,
};

describe("Health Canonical Route Pages", () => {
  it("renders /health (Health Overview Page)", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValueOnce(mockSummary as any);

    render(<HealthPage />);

    await waitFor(() => {
      expect(screen.getByTestId("health-overview")).toBeInTheDocument();
    });

    expect(screen.getByText("Hồ sơ sức khỏe tổng quan")).toBeInTheDocument();
    expect(screen.getByText("Penicillin")).toBeInTheDocument();
    expect(screen.getByText("Tăng huyết áp")).toBeInTheDocument();
  });

  it("renders /health/timeline (Timeline Page)", async () => {
    vi.spyOn(v2Client, "getHealthTimeline").mockResolvedValueOnce(mockTimeline as any);

    render(<HealthTimelinePage />);

    await waitFor(() => {
      expect(screen.getByTestId("timeline-view")).toBeInTheDocument();
    });

    expect(screen.getByText("Dòng thời gian sức khỏe")).toBeInTheDocument();
    expect(screen.getByText("Kê đơn Amlodipine")).toBeInTheDocument();
  });

  it("renders /health/medications (Medication Hub Page)", async () => {
    render(<ConsumerMedicationsPage />);

    expect(screen.getByTestId("consumer-medications-page")).toBeInTheDocument();
    expect(screen.getByText("Thuốc & Tủ thuốc")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Đơn thuốc & Phác đồ/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Tủ thuốc gia đình/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /An toàn & Tương tác/i })).toBeInTheDocument();
  });

  it("renders /health/results (Results & Trend Charts Page)", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValueOnce(mockSummary as any);

    render(<ResultsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("health-results-page")).toBeInTheDocument();
    });

    expect(screen.getByText("Kết quả xét nghiệm & Chẩn đoán")).toBeInTheDocument();
    expect(await screen.findByText("Glucose máu")).toBeInTheDocument();
    expect(screen.getByText(/Tham chiếu: 4.1 - 5.9/i)).toBeInTheDocument();
  });

  it("renders /health/measurements (Measurements & Vital Signs Page)", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValueOnce(mockSummary as any);

    render(<MeasurementsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("health-measurements-page")).toBeInTheDocument();
    });

    expect(screen.getByText("Chỉ số sức khỏe & Sinh hiệu")).toBeInTheDocument();
    expect(screen.getByText("120/80")).toBeInTheDocument();
  });

  it("renders /health/documents (Documents & Provenance Library Page)", async () => {
    vi.spyOn(v2Client, "getHealthSummary").mockResolvedValueOnce(mockSummary as any);

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("health-documents-page")).toBeInTheDocument();
    });

    expect(screen.getByText("Tài liệu & Hồ sơ y tế")).toBeInTheDocument();
    expect(screen.getByText("Đơn thuốc ngoại trú")).toBeInTheDocument();
  });
});
