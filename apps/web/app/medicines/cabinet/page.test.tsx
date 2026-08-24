import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const replace = vi.fn();
  const refresh = vi.fn();
  const push = vi.fn();
  return {
    getCabinet: vi.fn(),
    deleteCabinetItem: vi.fn(),
    updateCabinetItem: vi.fn(),
    createMedicationCourse: vi.fn(),
    replace,
    refresh,
    push,
    router: { replace, refresh, push },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/components/medicines/medical-consent-gate", () => ({
  default: ({ children }: { children: ReactNode }) => <div data-testid="consent-gate">{children}</div>,
}));

vi.mock("@/lib/selfmed", () => ({
  getCabinet: mocks.getCabinet,
  deleteCabinetItem: mocks.deleteCabinetItem,
  updateCabinetItem: mocks.updateCabinetItem,
}));

vi.mock("@/lib/medication-courses", () => ({
  createMedicationCourse: mocks.createMedicationCourse,
}));

import MedicineCabinetInventoryPage from "./page";

const mockItems = [
  {
    id: 1,
    drug_name: "Augmentin 625mg",
    brand_name: "Augmentin",
    manufacturer: "GSK",
    normalized_name: "Amoxicillin and Clavulanate",
    normalization_source: "db",
    normalization_status: "matched",
    dosage: "625 mg",
    dosage_form: "viên nén",
    quantity: 14,
    source: "ocr",
    rx_cui: "12345",
    ocr_confidence: 0.96,
    expires_on: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString(), // valid > 30d
    note: "Dùng sau ăn",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    drug_name: "Panadol Extra",
    brand_name: "Panadol",
    manufacturer: "GSK",
    normalized_name: "Paracetamol and Caffeine",
    normalization_source: "candidate",
    normalization_status: "candidate",
    dosage: "500mg/65mg",
    dosage_form: "viên nén",
    quantity: 8,
    source: "manual",
    rx_cui: "",
    ocr_confidence: null,
    expires_on: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString(), // expiring soon <= 30d
    note: "Giảm đau hạ sốt",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 3,
    drug_name: "Amoxicillin 250mg",
    brand_name: "Ospamox",
    manufacturer: "Sandoz",
    normalized_name: "Amoxicillin",
    normalization_source: "db",
    normalization_status: "matched",
    dosage: "250 mg",
    dosage_form: "viên nang",
    quantity: 6,
    source: "ocr",
    rx_cui: "54321",
    ocr_confidence: 0.92,
    expires_on: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(), // expired < now
    note: "Kháng sinh cũ",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getCabinet.mockResolvedValue({
    cabinet_id: 1,
    label: "Tủ thuốc gia đình",
    items: mockItems,
  });
  mocks.deleteCabinetItem.mockResolvedValue(undefined);
  mocks.updateCabinetItem.mockResolvedValue({ id: 1, quantity: 15 });
  mocks.createMedicationCourse.mockResolvedValue({ id: "course-new-1" });
});

afterEach(cleanup);

describe("MedicineCabinetInventoryPage (Spec v5 Section 6.28, 6.30 - EXPLORE Shell)", () => {
  it("renders Cabinet Stock Inventory with KPI cards, items, and disposal guidance", async () => {
    render(<MedicineCabinetInventoryPage />);

    expect(screen.getByTestId("consent-gate")).toBeInTheDocument();

    // Header & Archetype
    expect(await screen.findByRole("heading", { name: "Tủ thuốc gia đình" })).toBeInTheDocument();
    expect(screen.getByText("Tủ thuốc Gia đình & Tồn kho")).toBeInTheDocument();

    // Action buttons
    const addBtn = screen.getByRole("link", { name: "Thêm thuốc" });
    expect(addBtn).toHaveAttribute("href", "/medicines/cabinet/add");

    const safetyBtn = screen.getByRole("link", { name: "Kiểm tra tương tác thuốc" });
    expect(safetyBtn).toHaveAttribute("href", "/medicines?tab=safety");

    // Inventory KPIs
    expect(screen.getByText("Tổng số thuốc")).toBeInTheDocument();
    expect(screen.getByText("Còn hạn sử dụng")).toBeInTheDocument();
    expect(screen.getByText("Sắp hết hạn (≤30 ngày)")).toBeInTheDocument();
    expect(screen.getByText("Đã quá hạn")).toBeInTheDocument();

    // Items list
    expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
    expect(screen.getByText("Panadol Extra")).toBeInTheDocument();
    expect(screen.getByText("Amoxicillin 250mg")).toBeInTheDocument();

    // Badges
    expect(screen.getByText("Đã hết hạn")).toBeInTheDocument();
    expect(screen.getByText("Sắp hết hạn")).toBeInTheDocument();

    // Safe Disposal Guidance Section
    expect(
      screen.getByRole("heading", { name: "Hướng dẫn tiêu hủy thuốc an toàn & Đúng cách" }),
    ).toBeInTheDocument();
    expect(screen.getByText("KHÔNG xả thuốc xuống bồn cầu / cống")).toBeInTheDocument();
    expect(screen.getByText("Xử lý rác thải an toàn tại nhà")).toBeInTheDocument();
    expect(screen.getByText("Bảo vệ thông tin cá nhân")).toBeInTheDocument();
    expect(screen.getByText("Điểm thu hồi thuốc y tế")).toBeInTheDocument();
  });

  it("executes 'Chuyển thành thuốc đang dùng' action and creates active medication course", async () => {
    render(<MedicineCabinetInventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
    });

    const convertButtons = screen.getAllByRole("button", { name: "Chuyển thành thuốc đang dùng" });
    expect(convertButtons.length).toBeGreaterThan(0);

    // Click convert on first item (Augmentin 625mg)
    fireEvent.click(convertButtons[0]);

    await waitFor(() => {
      expect(mocks.createMedicationCourse).toHaveBeenCalledWith({
        medication_name: "Augmentin 625mg",
        dose_text: "625 mg",
        form_text: "viên nén",
        route_text: "uống",
        schedule_text: "Uống hàng ngày",
      });
      expect(
        screen.getByText('Đã chuyển "Augmentin 625mg" thành thuốc đang dùng trong hồ sơ.'),
      ).toBeInTheDocument();
      expect(screen.getByText("Xem đơn thuốc đang dùng →")).toBeInTheDocument();
    });
  });

  it("filters inventory by search query and category tabs", async () => {
    render(<MedicineCabinetInventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
    });

    // Search for Panadol
    const searchInput = screen.getByPlaceholderText("Tìm thuốc theo tên, biệt dược...");
    fireEvent.change(searchInput, { target: { value: "Panadol" } });

    expect(screen.getByText("Panadol Extra")).toBeInTheDocument();
    expect(screen.queryByText("Augmentin 625mg")).not.toBeInTheDocument();

    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });

    // Filter by Expired tab
    const expiredTab = screen.getByRole("button", { name: /Quá hạn \(1\)/ });
    fireEvent.click(expiredTab);

    expect(screen.getByText("Amoxicillin 250mg")).toBeInTheDocument();
    expect(screen.queryByText("Augmentin 625mg")).not.toBeInTheDocument();
  });

  it("adjusts quantity and allows editing cabinet item via modal", async () => {
    render(<MedicineCabinetInventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
    });

    // Increase quantity (+ button)
    const incButton = screen.getAllByRole("button", { name: "Tăng số lượng" })[0];
    fireEvent.click(incButton);
    expect(mocks.updateCabinetItem).toHaveBeenCalledWith(1, { quantity: 15 });

    // Open Edit modal
    const editButton = screen.getAllByRole("button", { name: "Sửa" })[0];
    fireEvent.click(editButton);

    expect(screen.getByRole("heading", { name: "Chỉnh sửa thuốc trong tủ" })).toBeInTheDocument();

    const nameInput = screen.getByLabelText("Tên thuốc *");
    fireEvent.change(nameInput, { target: { value: "Augmentin 1g" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu thay đổi" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mocks.updateCabinetItem).toHaveBeenCalledWith(1, expect.objectContaining({
        drug_name: "Augmentin 1g",
      }));
    });
  });

  it("deletes an item from the cabinet inventory", async () => {
    render(<MedicineCabinetInventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
    });

    const deleteButton = screen.getAllByRole("button", { name: "Xóa" })[0];
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mocks.deleteCabinetItem).toHaveBeenCalledWith(1);
      expect(mocks.getCabinet).toHaveBeenCalledTimes(2);
    });
  });
});
