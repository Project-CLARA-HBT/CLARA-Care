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
    replace,
    refresh,
    push,
    router: { replace, refresh, push },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
  useParams: () => ({ id: "med-101" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/lib/medication-courses", () => ({
  getMedicationCourses: mocks.getMedicationCourses,
  correctMedicationCourse: mocks.correctMedicationCourse,
  endMedicationCourse: mocks.endMedicationCourse,
}));

import MedicineDetailInspectorPage from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getMedicationCourses.mockResolvedValue([
    {
      id: "med-101",
      medication_name: "Metformin Hydrochloride",
      original_text: "Metformin Hydrochloride 500mg",
      normalized_name: "Metformin",
      reconciliation_status: "matched",
      drugbank_id: "DB00331",
      status: "active",
      dose_text: "500 mg",
      schedule_text: "1 viên x 2 lần/ngày sau khi ăn",
      route_text: "uống",
      form_text: "viên nén",
      truth_state: "confirmed",
      version: 2,
      ended_at: null,
    },
  ]);
  mocks.correctMedicationCourse.mockResolvedValue({ id: "med-101", version: 3 });
  mocks.endMedicationCourse.mockResolvedValue({ id: "med-101", status: "ended" });
});

afterEach(cleanup);

describe("MedicineDetailInspectorPage (Spec v5 Section 6.28, 6.30 - READ Shell)", () => {
  it("renders the 5 core clinical sections of the Medicine Detail Inspector", async () => {
    render(<MedicineDetailInspectorPage />);

    // Header & Badges
    expect(await screen.findByRole("heading", { name: "Metformin Hydrochloride" })).toBeInTheDocument();
    expect(screen.getByText("Đang sử dụng")).toBeInTheDocument();
    expect(screen.getByText("Khớp chuẩn DrugBank")).toBeInTheDocument();
    expect(screen.getAllByText("DB00331").length).toBeGreaterThan(0);
    expect(screen.getByText("Chi tiết Dược thư & Phác đồ")).toBeInTheDocument();

    // Section 1: Drug Monograph
    expect(screen.getByRole("heading", { name: /1\. Dược thư & Thông tin hoạt chất/ })).toBeInTheDocument();
    expect(screen.getByText("Chỉ định điều trị chính")).toBeInTheDocument();
    expect(screen.getByText("Cơ chế tác động dược lý")).toBeInTheDocument();
    expect(screen.getByText("Bảo quản & Hướng dẫn sử dụng")).toBeInTheDocument();

    // Section 2: Active Dosage Schedule
    expect(screen.getByRole("heading", { name: /2\. Phác đồ & Lịch dùng hiện tại/ })).toBeInTheDocument();
    expect(screen.getByText("500 mg")).toBeInTheDocument();
    expect(screen.getByText("1 viên x 2 lần/ngày sau khi ăn")).toBeInTheDocument();
    expect(screen.getByText("Khung giờ uống thuốc hàng ngày:")).toBeInTheDocument();

    // Section 3: Side Effects
    expect(screen.getByRole("heading", { name: /3\. Tác dụng phụ & Hướng dẫn xử trí/ })).toBeInTheDocument();
    expect(screen.getByText(/Tác dụng phụ thường gặp/)).toBeInTheDocument();
    expect(screen.getByText(/Cảnh báo nghiêm trọng/)).toBeInTheDocument();

    // Section 4: Verified Contraindications
    expect(screen.getByRole("heading", { name: /4\. Chống chỉ định & Cảnh báo an toàn/ })).toBeInTheDocument();
    expect(screen.getByText("Chống chỉ định tuyệt đối")).toBeInTheDocument();
    expect(screen.getByText("Kiêng khem & Lưu ý lối sống")).toBeInTheDocument();

    // Section 5: Adherence Log
    expect(screen.getByRole("heading", { name: /5\. Nhật ký tuân thủ dùng thuốc/ })).toBeInTheDocument();
    expect(screen.getByText(/Tuân thủ/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đã uống liều này" })).toBeInTheDocument();
  });

  it("interactively logs a taken intake dose and updates the adherence stream", async () => {
    render(<MedicineDetailInspectorPage />);

    await waitFor(() => {
      expect(screen.getByText("Metformin Hydrochloride")).toBeInTheDocument();
    });

    const takeButton = screen.getByRole("button", { name: "Đã uống liều này" });
    fireEvent.click(takeButton);

    expect(screen.getByText("Đã ghi nhận nhật ký dùng thuốc.")).toBeInTheDocument();
    expect(screen.getAllByText("Đã ghi nhận uống thuốc")[0]).toBeInTheDocument();
  });

  it("opens correction modal, modifies dose, and commits with reason", async () => {
    render(<MedicineDetailInspectorPage />);

    await waitFor(() => {
      expect(screen.getByText("Metformin Hydrochloride")).toBeInTheDocument();
    });

    // Open Edit modal
    const editButton = screen.getByRole("button", { name: "Sửa thông tin" });
    fireEvent.click(editButton);

    expect(screen.getByRole("heading", { name: "Chỉnh sửa bản ghi thuốc" })).toBeInTheDocument();

    // Modify dose
    const doseInput = screen.getByLabelText("Liều dùng");
    fireEvent.change(doseInput, { target: { value: "850 mg" } });

    // Submit changes
    const saveButton = screen.getByRole("button", { name: "Lưu thay đổi" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mocks.correctMedicationCourse).toHaveBeenCalledWith("med-101", 2, {
        medication_name: "Metformin Hydrochloride",
        dose_text: "850 mg",
        schedule_text: "1 viên x 2 lần/ngày sau khi ăn",
        route_text: "uống",
        form_text: "viên nén",
        reason: "Cập nhật theo đơn thuốc hiện tại",
      });
      expect(screen.getByText("Đã cập nhật thông tin thuốc thành công.")).toBeInTheDocument();
    });
  });

  it("concludes medication course via confirmation modal", async () => {
    render(<MedicineDetailInspectorPage />);

    await waitFor(() => {
      expect(screen.getByText("Metformin Hydrochloride")).toBeInTheDocument();
    });

    // Open Conclude modal
    const concludeButton = screen.getByRole("button", { name: "Kết thúc đợt dùng" });
    fireEvent.click(concludeButton);

    expect(screen.getByRole("heading", { name: "Kết thúc đợt dùng thuốc" })).toBeInTheDocument();

    const reasonInput = screen.getByLabelText("Lý do kết thúc đợt dùng");
    fireEvent.change(reasonInput, { target: { value: "Bác sĩ đổi sang phác đồ mới" } });

    const confirmButton = screen.getByRole("button", { name: "Xác nhận kết thúc" });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mocks.endMedicationCourse).toHaveBeenCalledWith(
        "med-101",
        2,
        "Bác sĩ đổi sang phác đồ mới",
      );
      expect(screen.getByText("Đã kết thúc đợt dùng thuốc.")).toBeInTheDocument();
    });
  });
});
