import { forwardRef, type ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  section: "demographics",
  setMode: vi.fn(),
  getPhrRecord: vi.fn(),
  getPhrCapabilities: vi.fn(),
  getPhrCompleteness: vi.fn(),
  getPhrBodyMeasurements: vi.fn(),
  createPhrBodyMeasurement: vi.fn(),
  updatePhrRecord: vi.fn(),
  routerPush: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ section: mocks.section }),
  usePathname: () => `/phr/${mocks.section}`,
  useRouter: () => ({ push: mocks.routerPush }),
}));

vi.mock("next/link", async () => {
  const React = await import("react");
  const LinkMock = React.forwardRef(function LinkMock(
    { href, children, ...props }: { href: string; children: React.ReactNode },
    ref: React.Ref<HTMLAnchorElement>,
  ) {
    return (
      <a href={href} ref={ref} {...props}>
        {children}
      </a>
    );
  });
  return { default: LinkMock };
});

vi.mock("@/components/shell/shell-mode-provider", () => ({
  useShellMode: () => ({
    mode: "focus",
    setMode: mocks.setMode,
    morphState: "COMPACT",
    setMorphState: vi.fn(),
    orbState: "idle",
    setOrbState: vi.fn(),
  }),
}));

vi.mock("@/lib/phr", () => ({
  DEFAULT_PHR_CAPABILITIES: {
    enhanced: true,
    consent_enforcement: false,
    reconciliation: false,
    allergy_aware_ddi: false,
    ocr_import: true,
    observations: true,
    export: true,
    sharing: true,
    reminders: true,
    completeness_meter: true,
  },
  getPhrRecord: mocks.getPhrRecord,
  getPhrCapabilities: mocks.getPhrCapabilities,
  getPhrCompleteness: mocks.getPhrCompleteness,
  getPhrBodyMeasurements: mocks.getPhrBodyMeasurements,
  createPhrBodyMeasurement: mocks.createPhrBodyMeasurement,
  updatePhrRecord: mocks.updatePhrRecord,
  getPhrEmergencyCard: vi.fn().mockResolvedValue({
    allergies: [],
    current_medications: [],
    conditions: [],
    blood_type: "O",
    emergency_contact_name: "Nguyễn Văn B",
    emergency_contact_phone: "0901234567",
  }),
  PHR_EMERGENCY_CARD_FIELDS: [
    "allergies",
    "current_medications",
    "conditions",
    "blood_type",
    "emergency_contact",
  ],
  PHR_EXPORT_RESOURCES: [
    "all",
    "patient",
    "allergy",
    "condition",
    "medication",
    "observation",
  ],
  listPhrReminders: vi.fn().mockResolvedValue([]),
  createPhrReminder: vi.fn().mockResolvedValue({}),
  exportPhrFhir: vi.fn().mockResolvedValue(new Blob(["{}"], { type: "application/json" })),
  listPhrShares: vi.fn().mockResolvedValue([]),
  createPhrShare: vi.fn().mockResolvedValue({ share_url: "https://example.com/share/token123" }),
}));

import PhrSectionPage from "./[section]/page";

const baseRecord = {
  full_name: "Trần Thị B",
  date_of_birth: "1992-05-15",
  gender: "female",
  blood_type: "A",
  height_cm: 160,
  weight_kg: 50,
  phone: "0912345678",
  contact_email: "tranb@example.com",
  address: "123 Đường Lê Lợi, TP.HCM",
  emergency_contact_name: "Trần Văn C",
  emergency_contact_phone: "0987654321",
  emergency_contact_relationship: "Anh trai",
  emergency_contact_note: "Gọi sau 18h",
  insurance_provider: "BHYT Quốc Gia",
  insurance_id: "GD4797931852",
  insurance_expiry: "2028-12-31",
  allergy_status: "unknown" as const,
  notes: "Bệnh nhân có tiền sử đau dạ dày nhẹ.",
  allergies: [],
  conditions: [],
  medications: [],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-10T12:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.section = "demographics";
  mocks.getPhrRecord.mockResolvedValue(baseRecord);
  mocks.getPhrCapabilities.mockResolvedValue({
    enhanced: true,
    consent_enforcement: false,
    reconciliation: false,
    allergy_aware_ddi: false,
    ocr_import: true,
    observations: true,
    export: true,
    sharing: true,
    reminders: true,
    completeness_meter: true,
  });
  mocks.getPhrCompleteness.mockResolvedValue({
    score: 0.75,
    present: ["patient_demographics", "medications"],
    missing: ["allergies", "problems"],
  });
  mocks.getPhrBodyMeasurements.mockResolvedValue([
    {
      observed_on: "2026-08-05",
      height_cm: 160,
      weight_kg: 50,
      bmi: 19.5,
      information_source: "self-declared",
    },
    {
      observed_on: "2026-07-20",
      height_cm: 160,
      weight_kg: 52,
      bmi: 20.3,
      information_source: "self-declared",
    },
  ]);
  mocks.updatePhrRecord.mockImplementation(async (payload) => payload);
});

afterEach(cleanup);

describe("Record Section Editor Archetype (Spec v5 Section 6.26)", () => {
  it("enforces FOCUS shell mode on mount", async () => {
    render(<PhrSectionPage />);
    await waitFor(() => {
      expect(mocks.setMode).toHaveBeenCalledWith("focus");
    });
  });

  it("renders demographics section with all identity and contact fields", async () => {
    mocks.section = "demographics";
    render(<PhrSectionPage />);

    expect(await screen.findByLabelText("Họ và tên")).toHaveValue("Trần Thị B");
    expect(screen.getByLabelText("Ngày sinh")).toHaveValue("1992-05-15");
    expect(screen.getByLabelText("Giới tính")).toHaveValue("female");
    expect(screen.getByLabelText("Nhóm máu")).toHaveValue("A");
    expect(screen.getByLabelText("Số điện thoại")).toHaveValue("0912345678");
    expect(screen.getByLabelText("Email")).toHaveValue("tranb@example.com");
    expect(screen.getByLabelText("Địa chỉ")).toHaveValue("123 Đường Lê Lợi, TP.HCM");
    expect(screen.getByLabelText("Người liên hệ khẩn cấp")).toHaveValue("Trần Văn C");
    expect(screen.getByLabelText("Mã bảo hiểm")).toHaveValue("GD4797931852");
    expect(screen.getByLabelText("Ghi chú tổng quan")).toHaveValue("Bệnh nhân có tiền sử đau dạ dày nhẹ.");
  });

  it("renders measurements section with BMI trend and historical records", async () => {
    mocks.section = "measurements";
    render(<PhrSectionPage />);

    expect(await screen.findByLabelText("Chiều cao (cm)")).toHaveValue("160");
    expect(screen.getByLabelText("Cân nặng (kg)")).toHaveValue("50");
    expect(screen.getAllByText("BMI 19.5")[0]).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Xu hướng BMI theo lần đo" })).toBeInTheDocument();
    expect(screen.getByText("160 cm · 50 kg")).toBeInTheDocument();
    expect(screen.getByText("160 cm · 52 kg")).toBeInTheDocument();
  });

  it("allows saving a new body measurement entry", async () => {
    mocks.section = "measurements";
    mocks.createPhrBodyMeasurement.mockResolvedValue({
      observed_on: "2026-08-24",
      height_cm: 160,
      weight_kg: 51,
      bmi: 19.9,
      information_source: "self-declared",
    });

    render(<PhrSectionPage />);

    const saveBtn = await screen.findByRole("button", { name: "Lưu lần đo hôm nay" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mocks.createPhrBodyMeasurement).toHaveBeenCalledWith(
        expect.objectContaining({
          height_cm: 160,
          weight_kg: 50,
        }),
      );
    });
  });

  it("renders allergies section with empty state and adds a new allergy", async () => {
    mocks.section = "allergies";
    render(<PhrSectionPage />);

    expect(await screen.findByText(/Chưa có dị ứng nào trong hồ sơ/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tôi chưa từng ghi nhận dị ứng" })).toBeInTheDocument();

    const addBtn = screen.getAllByRole("button", { name: "Thêm" })[0];
    fireEvent.click(addBtn);

    expect(screen.getByPlaceholderText("Tác nhân")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Phản ứng")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Mức độ")).toBeInTheDocument();
  });

  it("persists explicit no-known-allergy declaration", async () => {
    mocks.section = "allergies";
    render(<PhrSectionPage />);

    const noKnownBtn = await screen.findByRole("button", {
      name: "Tôi chưa từng ghi nhận dị ứng",
    });
    fireEvent.click(noKnownBtn);

    await waitFor(() => {
      expect(mocks.updatePhrRecord).toHaveBeenCalledWith(
        expect.objectContaining({
          allergy_status: "none_known",
          allergies: [],
        }),
      );
    });
  });

  it("renders conditions section and supports adding/editing conditions", async () => {
    mocks.section = "conditions";
    mocks.getPhrRecord.mockResolvedValue({
      ...baseRecord,
      conditions: [
        {
          id: "cond-1",
          name: "Viêm dạ dày",
          status: "active",
          diagnosed_on: "2025-03-10",
          note: "Uống thuốc theo đợt",
          information_source: "self-declared",
          verification_status: "confirmed",
        },
      ],
    });

    render(<PhrSectionPage />);

    expect(await screen.findByDisplayValue("Viêm dạ dày")).toBeInTheDocument();
    expect(screen.getByDisplayValue("active")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2025-03-10")).toBeInTheDocument();
    expect(screen.getByText("Nguồn: Tự khai báo")).toBeInTheDocument();
    expect(screen.getAllByText("Xác minh: Đã xác minh").length).toBeGreaterThanOrEqual(1);

    const addBtn = screen.getByRole("button", { name: "Thêm" });
    fireEvent.click(addBtn);

    expect(screen.getAllByPlaceholderText("Tên bệnh").length).toBe(2);
  });

  it("renders medications section with current vs past meds separation and resume action", async () => {
    mocks.section = "medications";
    mocks.getPhrRecord.mockResolvedValue({
      ...baseRecord,
      medications: [
        {
          id: "med-1",
          name: "Omeprazole 20mg",
          dose: "1 viên",
          frequency: "1 lần/ngày",
          started_on: "2026-01-01",
          is_current: true,
          note: "Uống trước ăn sáng",
          information_source: "self-declared",
          verification_status: "confirmed",
        },
        {
          id: "med-2",
          name: "Paracetamol 500mg",
          dose: "1 viên",
          frequency: "Khi đau đầu",
          started_on: "2025-10-01",
          is_current: false,
          note: "Đã ngừng",
        },
      ],
    });

    render(<PhrSectionPage />);

    expect(await screen.findByDisplayValue("Omeprazole 20mg")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Paracetamol 500mg")).not.toBeInTheDocument();
    expect(screen.getByText("Thuốc đã ngừng dùng (1)")).toBeInTheDocument();

    const resumeBtn = screen.getByRole("button", { name: "Đánh dấu đang dùng" });
    fireEvent.click(resumeBtn);

    expect(screen.getByDisplayValue("Paracetamol 500mg")).toBeInTheDocument();
  });

  it("renders documents section with OCR review modal trigger", async () => {
    mocks.section = "documents";
    render(<PhrSectionPage />);

    expect(await screen.findByRole("heading", { name: "Quét tài liệu" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quét đơn thuốc (OCR)" })).toBeInTheDocument();
  });

  it("allows removing allergy and condition entries", async () => {
    mocks.section = "allergies";
    mocks.getPhrRecord.mockResolvedValue({
      ...baseRecord,
      allergies: [
        {
          id: "allergy-1",
          name: "Penicillin",
          reaction: "Phát ban",
          severity: "moderate",
          note: "Dị ứng từ nhỏ",
          information_source: "self-declared",
          verification_status: "confirmed",
        },
      ],
    });

    render(<PhrSectionPage />);

    expect(await screen.findByDisplayValue("Penicillin")).toBeInTheDocument();
    const removeBtn = screen.getByRole("button", { name: "Xóa" });
    fireEvent.click(removeBtn);

    expect(screen.queryByDisplayValue("Penicillin")).not.toBeInTheDocument();
  });

  it("renders provenance and verification badges on coded medication items", async () => {
    mocks.section = "medications";
    mocks.getPhrRecord.mockResolvedValue({
      ...baseRecord,
      medications: [
        {
          id: "med-1",
          name: "Metformin 500mg",
          dose: "2 viên",
          frequency: "2 lần/ngày",
          started_on: "2025-06-01",
          is_current: true,
          note: "Uống sau bữa ăn",
          information_source: "ocr",
          verification_status: "confirmed",
        },
      ],
    });

    render(<PhrSectionPage />);

    expect(await screen.findByDisplayValue("Metformin 500mg")).toBeInTheDocument();
    expect(screen.getByText("Nguồn: Nhập từ quét tài liệu")).toBeInTheDocument();
    expect(screen.getAllByText("Xác minh: Đã xác minh").length).toBeGreaterThanOrEqual(1);

    const removeBtn = screen.getByRole("button", { name: "Xóa" });
    fireEvent.click(removeBtn);

    expect(screen.queryByDisplayValue("Metformin 500mg")).not.toBeInTheDocument();
  });

  it("handles record save error gracefully", async () => {
    mocks.section = "demographics";
    mocks.updatePhrRecord.mockRejectedValue(new Error("Network write failure"));

    render(<PhrSectionPage />);

    const nameInput = await screen.findByLabelText("Họ và tên");
    fireEvent.change(nameInput, { target: { value: "Trần Thị C" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu hồ sơ" });
    fireEvent.click(saveBtn);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("renders save action and shows success notice upon save", async () => {
    mocks.section = "demographics";
    render(<PhrSectionPage />);

    const nameInput = await screen.findByLabelText("Họ và tên");
    fireEvent.change(nameInput, { target: { value: "Trần Thị Bích" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu hồ sơ" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mocks.updatePhrRecord).toHaveBeenCalledWith(
        expect.objectContaining({
          full_name: "Trần Thị Bích",
        }),
      );
    });

    expect(await screen.findByText("Đã lưu hồ sơ sức khỏe.")).toBeInTheDocument();
  });

  it("handles cancel action by navigating back to /phr", async () => {
    mocks.section = "demographics";
    render(<PhrSectionPage />);

    const cancelBtn = await screen.findByRole("button", { name: "Hủy thay đổi" });
    fireEvent.click(cancelBtn);

    expect(mocks.routerPush).toHaveBeenCalledWith("/phr");
  });

  it("renders status section with USCDI completeness meter", async () => {
    mocks.section = "status";
    render(<PhrSectionPage />);

    expect(await screen.findByRole("heading", { name: "Mức độ hoàn thiện hồ sơ" })).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Thông tin cơ bản")).toBeInTheDocument();
  });

  it("handles unknown/invalid section gracefully with fallback", async () => {
    mocks.section = "invalid-section-xyz";
    render(<PhrSectionPage />);

    expect(await screen.findByText("Không tìm thấy mục hồ sơ")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Về hồ sơ sức khỏe" })).toHaveAttribute(
      "href",
      "/phr",
    );
  });
});
