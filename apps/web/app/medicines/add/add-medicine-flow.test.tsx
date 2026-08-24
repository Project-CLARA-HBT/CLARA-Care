import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    createMedicationCourse: vi.fn(),
    scanReceiptText: vi.fn(),
    scanReceiptFile: vi.fn(),
    replace,
    refresh,
    router: { replace, refresh },
  };
});

vi.mock("next/navigation", () => ({ useRouter: () => mocks.router }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/medication-courses", () => ({
  createMedicationCourse: mocks.createMedicationCourse,
}));
vi.mock("@/lib/selfmed", () => ({
  scanReceiptText: mocks.scanReceiptText,
  scanReceiptFile: mocks.scanReceiptFile,
}));

import AddMedicineFlow from "./add-medicine-flow";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.createMedicationCourse.mockResolvedValue({ id: "med-1" });
  mocks.scanReceiptText.mockResolvedValue([
    {
      drug_name: "Amlodipine 5mg",
      normalized_name: "Amlodipine",
      dosage: "5 mg",
      brand_name: "Norvasc",
      manufacturer: "Pfizer",
      confidence: 0.94,
      evidence: "Amlodipine 5mg tablet",
    },
  ]);
});

afterEach(cleanup);

async function advance(label = "Tiếp tục") {
  fireEvent.click(screen.getByRole("button", { name: label }));
  await waitFor(() => expect(screen.getByText(/Bước/)).toBeInTheDocument());
}

describe("AddMedicineFlow (Spec v5 Section 6.28 - Medicine Intake Wizard in FOCUS shell)", () => {
  it("keeps one concept per step and focuses the required identity input", () => {
    render(<AddMedicineFlow />);
    const name = screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn");

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Nhập ít nhất 2 ký tự");
    expect(name).toHaveFocus();
    expect(mocks.createMedicationCourse).not.toHaveBeenCalled();
    expect(screen.getByRole("navigation", { name: "Tiến trình" })).toHaveTextContent("Bước 1 / 4");
  });

  it("supports scanning prescription OCR text and populating candidate drug", async () => {
    render(<AddMedicineFlow />);

    // Switch to Scanner Mode
    fireEvent.click(screen.getByRole("button", { name: "Quét đơn / Bao bì thuốc (OCR)" }));

    const textInput = screen.getByLabelText("Hoặc dán nội dung đơn thuốc");
    fireEvent.change(textInput, { target: { value: "Amlodipine 5mg 1 tab daily" } });

    fireEvent.click(screen.getByRole("button", { name: "Nhận diện từ văn bản" }));

    await waitFor(() => {
      expect(mocks.scanReceiptText).toHaveBeenCalledWith("Amlodipine 5mg 1 tab daily");
      expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();
      expect(screen.getByText("94%")).toBeInTheDocument();
    });

    // Select candidate
    fireEvent.click(screen.getByRole("button", { name: "Chọn thuốc này" }));

    // Back in manual view with populated fields
    expect(screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn")).toHaveValue("Amlodipine 5mg");
    expect(screen.getByText(/Đã điền tự động từ quét OCR/)).toBeInTheDocument();
  });

  it("walks through drug verification, schedule presets, interaction preflight check, and submits only on review", async () => {
    render(<AddMedicineFlow />);
    fireEvent.change(screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn"), {
      target: { value: "  Metformin  " },
    });
    await advance();

    // Step 2: Drug Verification
    expect(screen.getByText("Trạng thái xác thực định danh")).toBeInTheDocument();
    expect(screen.getByText("Đã đối chiếu hoạt chất")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Liều ghi trên nhãn/), {
      target: { value: "500 mg" },
    });
    await advance();

    // Step 3: Dosage Schedule Setup with quick presets
    expect(screen.getByText("Gợi ý chọn nhanh thời điểm dùng:")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "+ Buổi tối" }));
    expect(screen.getByLabelText(/Lịch dùng ghi trên nhãn hoặc đơn/)).toHaveValue("Buổi tối");
    await advance();

    // Step 4: Interaction Preflight Check & Review
    expect(screen.getByText("Kiểm tra an toàn tương tác trước khi kích hoạt")).toBeInTheDocument();
    expect(screen.getByText("An toàn sơ bộ")).toBeInTheDocument();
    expect(screen.getByText("Metformin")).toBeInTheDocument();
    expect(mocks.createMedicationCourse).not.toHaveBeenCalled();
    expect(window.location.search).not.toContain("Metformin");

    fireEvent.click(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" }));
    await waitFor(() => {
      expect(mocks.createMedicationCourse).toHaveBeenCalledWith({
        medication_name: "Metformin",
        dose_text: "500 mg",
        route_text: undefined,
        form_text: undefined,
        schedule_text: "Buổi tối",
        drugbank_id: undefined,
      });
      expect(mocks.replace).toHaveBeenCalledWith("/medicines?tab=list");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });

  it("keeps API error detail out of the primary view and allows a retry", async () => {
    mocks.createMedicationCourse.mockRejectedValue(new Error("internal-secret-token"));
    render(<AddMedicineFlow />);
    fireEvent.change(screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn"), {
      target: { value: "Metformin" },
    });
    await advance();
    await advance();
    await advance();
    fireEvent.click(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Chưa thể lưu thuốc lúc này");
    expect(alert).not.toHaveTextContent("internal-secret-token");
    expect(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" })).toBeEnabled();
  });
});
