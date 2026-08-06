import type { ReactNode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

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
      expect(screen.getByRole("link", { name: /Thông tin cơ bản/ })).toHaveAttribute("href", "/phr/identity");
    });
    expect(screen.getByRole("link", { name: /Chỉ số cơ thể/ })).toHaveAttribute("href", "/phr/body");
    expect(screen.getByRole("link", { name: /Dị ứng/ })).toHaveAttribute("href", "/phr/allergies");
    expect(screen.queryByLabelText("Họ và tên")).not.toBeInTheDocument();
    expect(mocks.getPhrRecord).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("progressbar", { name: "Tiến độ hoàn thiện hồ sơ" })).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getByRole("link", { name: /Tiếp tục hoàn thiện/ })).toHaveAttribute("href", "/phr/contact");
    expect(container.querySelectorAll("svg[data-icon]")).toHaveLength(7);
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
  });
});
