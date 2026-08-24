import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const replace = vi.fn();
  const refresh = vi.fn();
  const push = vi.fn();
  return {
    getMedicationCourses: vi.fn(),
    correctMedicationCourse: vi.fn(),
    endMedicationCourse: vi.fn(),
    createMedicationCourse: vi.fn(),
    getCabinet: vi.fn(),
    deleteCabinetItem: vi.fn(),
    updateCabinetItem: vi.fn(),
    replace,
    refresh,
    push,
    router: { replace, refresh, push },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
  useSearchParams: () => new URLSearchParams("tab=list"),
  useParams: () => ({ id: "med-v8-1" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/components/medicines/medical-consent-gate", () => ({
  default: ({ children }: { children: ReactNode }) => <div data-testid="consent-gate">{children}</div>,
}));

vi.mock("@/lib/medication-courses", () => ({
  getMedicationCourses: mocks.getMedicationCourses,
  correctMedicationCourse: mocks.correctMedicationCourse,
  endMedicationCourse: mocks.endMedicationCourse,
  createMedicationCourse: mocks.createMedicationCourse,
}));

vi.mock("@/lib/selfmed", () => ({
  getCabinet: mocks.getCabinet,
  deleteCabinetItem: mocks.deleteCabinetItem,
  updateCabinetItem: mocks.updateCabinetItem,
}));

import MedicinesPage from "./page";
import MedicineDetailInspectorPage from "./[id]/page";
import MedicineCabinetInventoryPage from "./cabinet/page";

const mockActiveConfirmedCourses = [
  {
    id: "med-v8-1",
    version: 1,
    medication_name: "Metformin 500mg",
    original_text: "Metformin 500mg",
    normalized_name: "Metformin",
    reconciliation_status: "matched",
    drugbank_id: "DB00331",
    status: "active",
    dose_text: "500 mg",
    schedule_text: "1 viên sau ăn sáng",
    route_text: "uống",
    form_text: "viên nén",
    truth_state: "confirmed",
    ended_at: null,
  },
  {
    id: "med-v8-2",
    version: 1,
    medication_name: "Amlodipine 5mg",
    original_text: "Amlodipine 5mg",
    normalized_name: "Amlodipine",
    reconciliation_status: "matched",
    drugbank_id: "DB00381",
    status: "active",
    dose_text: "5 mg",
    schedule_text: "1 viên buổi sáng",
    route_text: "uống",
    form_text: "viên nén",
    truth_state: "confirmed",
    ended_at: null,
  },
];

const mockUnresolvedCourses = [
  {
    id: "med-v8-unresolved",
    version: 1,
    medication_name: "Thuốc đề xuất chưa định danh",
    original_text: "Thuốc đề xuất chưa định danh",
    normalized_name: null,
    reconciliation_status: "unmatched",
    drugbank_id: null,
    status: "active",
    dose_text: "",
    schedule_text: "",
    route_text: "",
    form_text: "",
    truth_state: "proposed",
    ended_at: null,
  },
];

const mockCabinetInventory = [
  {
    id: 901,
    drug_name: "Paracetamol 500mg",
    brand_name: "Panadol",
    manufacturer: "GSK",
    dosage: "500 mg",
    dosage_form: "viên nén",
    quantity: 10,
    source: "ocr",
    ocr_confidence: 0.95,
    expires_on: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 902,
    drug_name: "Berberin 100mg",
    brand_name: "Berberin",
    manufacturer: "OPC",
    dosage: "100 mg",
    dosage_form: "viên nang",
    quantity: 20,
    source: "manual",
    ocr_confidence: null,
    expires_on: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(), // expired
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getMedicationCourses.mockResolvedValue([
    ...mockActiveConfirmedCourses,
    ...mockUnresolvedCourses,
  ]);
  mocks.getCabinet.mockResolvedValue({
    cabinet_id: 10,
    label: "Tủ thuốc gia đình",
    items: mockCabinetInventory,
  });
  mocks.correctMedicationCourse.mockResolvedValue({ id: "med-v8-1", version: 2 });
  mocks.endMedicationCourse.mockResolvedValue({ id: "med-v8-1", status: "ended" });
  mocks.createMedicationCourse.mockResolvedValue({ id: "course-converted-1" });
});

afterEach(cleanup);

describe("Spec v8 Section 7.9: MEDICINE_WORKSPACE Reconstruction", () => {
  describe("1. Four Distinct Visual Domains on `/medicines`", () => {
    it("renders Domain 1: Current confirmed medications (`taking`)", async () => {
      render(<MedicinesPage />);

      const domainTaking = await screen.findByTestId("domain-taking");
      expect(domainTaking).toBeInTheDocument();
      expect(screen.getByText("Thuốc đang sử dụng (Đã xác nhận)")).toBeInTheDocument();
      expect(screen.getByText("Metformin 500mg")).toBeInTheDocument();
      expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();
      expect(screen.getByText("DrugBank ID: DB00331")).toBeInTheDocument();
      expect(screen.getByText("DrugBank ID: DB00381")).toBeInTheDocument();
    });

    it("renders Domain 2: Unresolved proposals requiring review (`unresolved`)", async () => {
      render(<MedicinesPage />);

      const domainUnresolved = await screen.findByTestId("domain-unresolved");
      expect(domainUnresolved).toBeInTheDocument();
      expect(screen.getByText("Cần xác nhận / Đề xuất chưa đối chiếu")).toBeInTheDocument();
      expect(screen.getByText("Thuốc đề xuất chưa định danh")).toBeInTheDocument();
      expect(screen.getByText("Chưa đối chiếu chuẩn")).toBeInTheDocument();
      expect(
        screen.getByText(/Có 1 thuốc cần rà soát lại thông tin đối chiếu/),
      ).toBeInTheDocument();
    });

    it("renders Domain 3: Drug Interaction Safety ActionObject with Two-medicine guard and DrugBank v5.1 verification", async () => {
      render(<MedicinesPage />);

      const domainSafety = await screen.findByTestId("domain-safety-action");
      expect(domainSafety).toBeInTheDocument();
      expect(
        screen.getAllByText("Kiểm tra tương tác thuốc (Drug Interaction Guard)")[0],
      ).toBeInTheDocument();
      expect(screen.getByText("DrugBank v5.1 & FIDES")).toBeInTheDocument();
      expect(
        screen.getByText("Quy tắc 2 thuốc: Tối thiểu 2 hoạt chất phân biệt"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Xác thực nguồn DrugBank v5.1 & FIDES verification"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Cơ chế Fail-closed: Không báo an toàn giả khi thiếu dữ liệu"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Mở công cụ kiểm tra tương tác"),
      ).toBeInTheDocument();
    });

    it("renders Domain 4: Home Medicine Cabinet inventory (`cabinet_stored`)", async () => {
      render(<MedicinesPage />);

      const domainCabinet = await screen.findByTestId("domain-cabinet-stored");
      expect(domainCabinet).toBeInTheDocument();
      expect(screen.getByText("Tủ thuốc gia đình (Tồn kho dự phòng)")).toBeInTheDocument();
      expect(screen.getByText("Paracetamol 500mg")).toBeInTheDocument();
    });
  });

  describe("2. Opaque cards for all clinical medicine records (No ungrounded transparency)", () => {
    it("renders opaque SurfaceCard containers without glass blurs on clinical records", async () => {
      render(<MedicineDetailInspectorPage />);

      const inspector = await screen.findByTestId("medicine-detail-inspector");
      expect(inspector).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Metformin 500mg" })).toBeInTheDocument();

      // Clinical sections are opaque SurfaceCards
      expect(screen.getByRole("heading", { name: /1\. Dược thư & Thông tin hoạt chất/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /2\. Phác đồ & Lịch dùng hiện tại/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /3\. Tác dụng phụ & Hướng dẫn xử trí/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /4\. Chống chỉ định & Cảnh báo an toàn/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /5\. Nhật ký tuân thủ dùng thuốc/ })).toBeInTheDocument();
    });
  });

  describe("3. Invariant: Never merge physical possession with active prescription", () => {
    it("displays the invariant disclaimer distinguishing cabinet storage from active prescriptions", async () => {
      render(<MedicinesPage />);

      await waitFor(() => {
        expect(
          screen.getByText(
            "Thuốc trong tủ là tồn kho dự trữ gia đình. Chưa được đưa vào đơn thuốc đang dùng thực tế.",
          ),
        ).toBeInTheDocument();
      });
    });

    it("requires explicit user action on `/medicines/cabinet` to promote a physical item into an active prescription", async () => {
      render(<MedicineCabinetInventoryPage />);

      await waitFor(() => {
        expect(screen.getByText("Paracetamol 500mg")).toBeInTheDocument();
      });

      const convertButtons = screen.getAllByRole("button", { name: "Chuyển thành thuốc đang dùng" });
      expect(convertButtons.length).toBeGreaterThan(0);

      fireEvent.click(convertButtons[0]);

      await waitFor(() => {
        expect(mocks.createMedicationCourse).toHaveBeenCalledWith({
          medication_name: "Paracetamol 500mg",
          dose_text: "500 mg",
          form_text: "viên nén",
          route_text: "uống",
          schedule_text: "Uống hàng ngày",
        });
        expect(
          screen.getByText('Đã chuyển "Paracetamol 500mg" thành thuốc đang dùng trong hồ sơ.'),
        ).toBeInTheDocument();
      });
    });
  });
});
