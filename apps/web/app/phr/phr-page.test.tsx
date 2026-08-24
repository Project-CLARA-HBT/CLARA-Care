import { forwardRef, type ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  pathname: "/phr",
  getPhrRecord: vi.fn(),
  getPhrCapabilities: vi.fn(),
  getPhrCompleteness: vi.fn(),
  getPhrBodyMeasurements: vi.fn(),
  createPhrBodyMeasurement: vi.fn(),
  updatePhrRecord: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
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

vi.mock("@/lib/phr", () => ({
  DEFAULT_PHR_CAPABILITIES: {
    enhanced: false,
    consent_enforcement: false,
    reconciliation: false,
    allergy_aware_ddi: false,
    ocr_import: false,
    observations: false,
    export: false,
    sharing: false,
    reminders: false,
    completeness_meter: false,
  },
  getPhrRecord: mocks.getPhrRecord,
  getPhrCapabilities: mocks.getPhrCapabilities,
  getPhrCompleteness: mocks.getPhrCompleteness,
  getPhrBodyMeasurements: mocks.getPhrBodyMeasurements,
  createPhrBodyMeasurement: mocks.createPhrBodyMeasurement,
  updatePhrRecord: mocks.updatePhrRecord,
}));

import PhrPage from "./page";

const record = {
  full_name: "Nguyễn An",
  date_of_birth: "1990-01-02",
  gender: "female",
  blood_type: "O",
  height_cm: 165,
  weight_kg: 55,
  phone: "",
  address: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  insurance_id: "",
  notes: "",
  contact_email: "",
  emergency_contact_relationship: "",
  emergency_contact_note: "",
  insurance_provider: "",
  insurance_expiry: null,
  allergy_status: "unknown",
  allergies: [],
  conditions: [],
  medications: [],
  created_at: null,
  updated_at: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.pathname = "/phr";
  mocks.getPhrRecord.mockResolvedValue(record);
  mocks.getPhrCapabilities.mockResolvedValue({
    enhanced: false,
    consent_enforcement: false,
    reconciliation: false,
    allergy_aware_ddi: false,
    ocr_import: false,
    observations: false,
    export: false,
    sharing: false,
    reminders: false,
    completeness_meter: false,
  });
  mocks.getPhrCompleteness.mockResolvedValue({ score: 0, present: [], missing: [] });
  mocks.getPhrBodyMeasurements.mockResolvedValue([]);
});

afterEach(cleanup);

describe("PHR focused hub", () => {
  it("keeps the root as a hub of one-concept routes", async () => {
    const { container } = render(<PhrPage />);

    await waitFor(() => {
      expect(screen.getAllByRole("link", { name: /Thông tin cơ bản/ })[0]).toHaveAttribute("href", "/phr/identity");
    });
    expect(screen.getAllByRole("link", { name: /Chỉ số cơ thể/ })[0]).toHaveAttribute("href", "/phr/body");
    expect(screen.getAllByRole("link", { name: /Dị ứng/ })[0]).toHaveAttribute("href", "/phr/allergies");
    expect(screen.queryByLabelText("Họ và tên")).not.toBeInTheDocument();
    expect(mocks.getPhrRecord).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("progressbar", { name: "Tiến độ hoàn thiện hồ sơ" })[0]).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getAllByRole("progressbar", { name: "Tiến độ hoàn thiện hồ sơ" })[1]).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getAllByRole("link", { name: /Tiếp tục hoàn thiện/ })[0]).toHaveAttribute("href", "/phr/conditions");
    expect(screen.getAllByRole("link", { name: /Tiếp tục hoàn thiện/ })[1]).toHaveAttribute("href", "/phr/contact");
    expect(container.querySelectorAll("svg[data-icon]").length).toBeGreaterThanOrEqual(7);
    expect(container.querySelector(".material-symbols-rounded")).not.toBeInTheDocument();
    for (const leakedGlyph of [
      "badge",
      "accessibility_new",
      "contact_phone",
      "warning",
      "clinical_notes",
      "medication",
    ]) {
      expect(container).not.toHaveTextContent(leakedGlyph);
    }
  });

  it("shows only body measurements on the focused body route", async () => {
    mocks.pathname = "/phr/body";
    render(<PhrPage />);

    expect(await screen.findByLabelText("Chiều cao (cm)")).toHaveValue("165");
    expect(screen.getByLabelText("Cân nặng (kg)")).toHaveValue("55");
    expect(screen.queryByLabelText("Họ và tên")).not.toBeInTheDocument();
    expect(screen.queryByText("Dị ứng")).not.toBeInTheDocument();
  });

  it("renders a BMI visualization only from two or more recorded measurements", async () => {
    mocks.pathname = "/phr/body";
    mocks.getPhrCapabilities.mockResolvedValue({
      enhanced: true, consent_enforcement: false, reconciliation: false,
      allergy_aware_ddi: false, ocr_import: false, observations: true,
      export: false, sharing: false, reminders: false, completeness_meter: false,
    });
    mocks.getPhrBodyMeasurements.mockResolvedValue([
      { observed_on: "2026-08-02", height_cm: 165, weight_kg: 60, bmi: 22, information_source: "self-declared" },
      { observed_on: "2026-08-01", height_cm: 165, weight_kg: 61, bmi: 22.4, information_source: "self-declared" },
    ]);
    render(<PhrPage />);

    expect(await screen.findByRole("img", { name: "Xu hướng BMI theo lần đo" })).toBeInTheDocument();
    expect(screen.getAllByText("BMI 22")).toHaveLength(2);
  });

  it("shows truthful empty allergy state instead of a placeholder record", async () => {
    mocks.pathname = "/phr/allergies";
    render(<PhrPage />);

    expect(await screen.findByText(/Chưa có dị ứng nào trong hồ sơ/)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Tên dị ứng")).not.toBeInTheDocument();
  });

  it("separates current medicines from medicines no longer used", async () => {
    mocks.pathname = "/phr/medications";
    mocks.getPhrRecord.mockResolvedValue({
      ...record,
      medications: [
        {
          id: "current",
          name: "Thuốc đang dùng",
          dose: "",
          frequency: "",
          started_on: null,
          is_current: true,
          note: "",
        },
        {
          id: "past",
          name: "Thuốc đã ngừng",
          dose: "",
          frequency: "",
          started_on: null,
          is_current: false,
          note: "",
        },
      ],
    });

    render(<PhrPage />);

    expect(await screen.findByDisplayValue("Thuốc đang dùng")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Thuốc đã ngừng")).not.toBeInTheDocument();
    expect(screen.getByText("Thuốc đã ngừng dùng (1)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đánh dấu đang dùng" })).toBeInTheDocument();
  });

  it("persists an explicit no-known-allergy declaration", async () => {
    mocks.pathname = "/phr/allergies";
    mocks.updatePhrRecord.mockImplementation(async (payload) => payload);
    render(<PhrPage />);

    const action = await screen.findByRole("button", { name: "Tôi chưa từng ghi nhận dị ứng" });
    fireEvent.click(action);

    await waitFor(() => {
      expect(mocks.updatePhrRecord).toHaveBeenCalledWith(expect.objectContaining({
        allergy_status: "none_known",
        allergies: [],
      }));
    });
    expect(screen.getByText("Bạn chưa từng ghi nhận dị ứng")).toBeInTheDocument();
  });
});
