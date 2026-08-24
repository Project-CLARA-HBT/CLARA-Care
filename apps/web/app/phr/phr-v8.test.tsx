import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  pathname: "/phr",
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
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: mocks.routerPush, refresh: vi.fn() }),
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

import PhrPage from "./page";
import PhrSectionPage from "./[section]/page";

const baseRecord = {
  full_name: "Nguyễn An",
  date_of_birth: "1990-01-02",
  gender: "female",
  blood_type: "O",
  height_cm: 165,
  weight_kg: 55,
  phone: "0901234567",
  address: "123 Lê Lợi, TP.HCM",
  contact_email: "an@example.com",
  emergency_contact_name: "Nguyễn Bình",
  emergency_contact_phone: "0987654321",
  emergency_contact_relationship: "Anh trai",
  emergency_contact_note: "",
  insurance_provider: "BHYT Quốc Gia",
  insurance_id: "GD1234567890",
  insurance_expiry: "2028-12-31",
  notes: "Tiền sử khỏe mạnh.",
  allergy_status: "unknown" as const,
  allergies: [],
  conditions: [],
  medications: [],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-10T12:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.pathname = "/phr";
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
      height_cm: 165,
      weight_kg: 55,
      bmi: 20.2,
      information_source: "self-declared",
    },
    {
      observed_on: "2026-07-20",
      height_cm: 165,
      weight_kg: 56,
      bmi: 20.6,
      information_source: "self-declared",
    },
  ]);
  mocks.updatePhrRecord.mockImplementation(async (payload) => payload);
});

afterEach(cleanup);

describe("Spec v8 Section 7.10 /phr and /phr/[section] Architecture", () => {
  describe("1. /phr Workbench Canvas & Local ContextRail", () => {
    it("renders ContextRail local navigation rail with section badges", async () => {
      mocks.pathname = "/phr";
      render(<PhrPage />);

      expect(await screen.findByRole("navigation", { name: "Thanh điều hướng hồ sơ sức khỏe" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^Tổng quan/ })).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: /Thông tin cơ bản/ })[0]).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: /Chỉ số cơ thể/ })[0]).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: /Dị ứng/ })[0]).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: /Bệnh nền/ })[0]).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: /Thuốc đang dùng/ })[0]).toBeInTheDocument();
    });

    it("renders top summary canvas with record summary and USCDI v1 completeness meter", async () => {
      mocks.pathname = "/phr";
      render(<PhrPage />);

      expect(await screen.findByText("Đã hoàn thiện 3/6 mục")).toBeInTheDocument();
      expect(screen.getByText("Nhóm máu O")).toBeInTheDocument();
      expect(screen.getByText(/Mức độ hoàn thiện hồ sơ \(USCDI v1\)/)).toBeInTheDocument();
      expect(screen.getByText("75% hoàn thiện")).toBeInTheDocument();
    });

    it("displays non-diagnostic medical disclaimer on summary canvas", async () => {
      mocks.pathname = "/phr";
      render(<PhrPage />);

      const notes = await screen.findAllByRole("note");
      expect(notes.length).toBeGreaterThanOrEqual(1);
      for (const note of notes) {
        expect(note.textContent).toMatch(/không thay thế/i);
      }
    });

    it("renders section rows leading to full-screen editors", async () => {
      mocks.pathname = "/phr";
      render(<PhrPage />);

      await waitFor(() => {
        expect(screen.getAllByRole("link", { name: /Thông tin cơ bản/ })[0]).toHaveAttribute("href", "/phr/identity");
      });
      expect(screen.getAllByRole("link", { name: /Chỉ số cơ thể/ })[0]).toHaveAttribute("href", "/phr/body");
      expect(screen.getAllByRole("link", { name: /Dị ứng/ })[0]).toHaveAttribute("href", "/phr/allergies");
      expect(screen.getAllByRole("link", { name: /Bệnh nền/ })[0]).toHaveAttribute("href", "/phr/conditions");
      expect(screen.getAllByRole("link", { name: /Thuốc đang dùng/ })[0]).toHaveAttribute("href", "/phr/medications");
    });

    it("enforces opaque data surfaces and no blurred cards", async () => {
      mocks.pathname = "/phr";
      const { container } = render(<PhrPage />);

      await waitFor(() => {
        expect(screen.getByText("Đã hoàn thiện 3/6 mục")).toBeInTheDocument();
      });

      expect(container.querySelectorAll(".chrome-panel").length).toBe(0);
      expect(container.querySelectorAll(".backdrop-blur-sm, .backdrop-blur-md, .backdrop-blur-lg").length).toBe(0);
      expect(container.innerHTML).not.toContain("backdrop-blur");
    });
  });

  describe("2. /phr/[section] Full-screen Section Editors in FOCUS Shell", () => {
    it("enforces FOCUS shell mode on mount", async () => {
      mocks.section = "demographics";
      mocks.pathname = "/phr/demographics";
      render(<PhrSectionPage />);

      await waitFor(() => {
        expect(mocks.setMode).toHaveBeenCalledWith("focus");
      });
    });

    it("renders demographics full-screen section editor", async () => {
      mocks.section = "demographics";
      mocks.pathname = "/phr/demographics";
      render(<PhrSectionPage />);

      expect(await screen.findByLabelText("Họ và tên")).toHaveValue("Nguyễn An");
      expect(screen.getByLabelText("Ngày sinh")).toHaveValue("1990-01-02");
      expect(screen.getByLabelText("Giới tính")).toHaveValue("female");
      expect(screen.getByLabelText("Nhóm máu")).toHaveValue("O");
      expect(screen.getByLabelText("Số điện thoại")).toHaveValue("0901234567");
      expect(screen.getByLabelText("Email")).toHaveValue("an@example.com");
      expect(screen.getByLabelText("Địa chỉ")).toHaveValue("123 Lê Lợi, TP.HCM");
      expect(screen.getByLabelText("Người liên hệ khẩn cấp")).toHaveValue("Nguyễn Bình");
    });

    it("renders allergies full-screen section editor with add and empty state actions", async () => {
      mocks.section = "allergies";
      mocks.pathname = "/phr/allergies";
      render(<PhrSectionPage />);

      expect(await screen.findByText(/Chưa có dị ứng nào trong hồ sơ/)).toBeInTheDocument();
      const addBtn = screen.getAllByRole("button", { name: "Thêm" })[0];
      fireEvent.click(addBtn);

      expect(screen.getByPlaceholderText("Tác nhân")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Phản ứng")).toBeInTheDocument();
    });

    it("renders conditions full-screen section editor", async () => {
      mocks.section = "conditions";
      mocks.pathname = "/phr/conditions";
      mocks.getPhrRecord.mockResolvedValue({
        ...baseRecord,
        conditions: [
          {
            id: "c1",
            name: "Tăng huyết áp",
            status: "active",
            diagnosed_on: "2024-05-01",
            note: "Uống thuốc hàng ngày",
            information_source: "self-declared",
            verification_status: "confirmed",
          },
        ],
      });

      render(<PhrSectionPage />);

      expect(await screen.findByDisplayValue("Tăng huyết áp")).toBeInTheDocument();
      expect(screen.getByDisplayValue("active")).toBeInTheDocument();
      expect(screen.getByText("Nguồn: Tự khai báo")).toBeInTheDocument();
    });

    it("renders medications full-screen section editor with current vs past separation", async () => {
      mocks.section = "medications";
      mocks.pathname = "/phr/medications";
      mocks.getPhrRecord.mockResolvedValue({
        ...baseRecord,
        medications: [
          {
            id: "m1",
            name: "Amlodipine 5mg",
            dose: "1 viên",
            frequency: "1 lần/sáng",
            started_on: "2024-05-02",
            is_current: true,
            note: "Uống sau ăn",
            information_source: "self-declared",
            verification_status: "confirmed",
          },
          {
            id: "m2",
            name: "Panadol Extra",
            dose: "1 viên",
            frequency: "Khi sốt",
            started_on: "2024-01-01",
            is_current: false,
            note: "Đã ngừng",
          },
        ],
      });

      render(<PhrSectionPage />);

      expect(await screen.findByDisplayValue("Amlodipine 5mg")).toBeInTheDocument();
      expect(screen.queryByDisplayValue("Panadol Extra")).not.toBeInTheDocument();
      expect(screen.getByText("Thuốc đã ngừng dùng (1)")).toBeInTheDocument();
    });

    it("renders measurements full-screen section editor with BMI trend", async () => {
      mocks.section = "measurements";
      mocks.pathname = "/phr/measurements";
      render(<PhrSectionPage />);

      expect(await screen.findByLabelText("Chiều cao (cm)")).toHaveValue("165");
      expect(screen.getByLabelText("Cân nặng (kg)")).toHaveValue("55");
      expect(screen.getByRole("img", { name: "Xu hướng BMI theo lần đo" })).toBeInTheDocument();
    });

    it("renders documents full-screen section editor with OCR scanner modal trigger", async () => {
      mocks.section = "documents";
      mocks.pathname = "/phr/documents";
      render(<PhrSectionPage />);

      expect(await screen.findByRole("heading", { name: "Quét tài liệu" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Quét đơn thuốc (OCR)" })).toBeInTheDocument();
    });

    it("ensures section editor uses opaque surface with no blurred panels", async () => {
      mocks.section = "demographics";
      mocks.pathname = "/phr/demographics";
      const { container } = render(<PhrSectionPage />);

      await waitFor(() => {
        expect(screen.getByLabelText("Họ và tên")).toBeInTheDocument();
      });

      expect(container.querySelectorAll(".chrome-panel").length).toBe(0);
      expect(container.querySelectorAll(".backdrop-blur-sm, .backdrop-blur-md, .backdrop-blur-lg").length).toBe(0);
      expect(container.innerHTML).not.toContain("backdrop-blur");
    });
  });
});
