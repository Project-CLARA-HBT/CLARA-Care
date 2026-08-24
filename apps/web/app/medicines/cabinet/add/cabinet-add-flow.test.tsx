import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    scanReceiptFile: vi.fn(),
    scanReceiptText: vi.fn(),
    importDetections: vi.fn(),
    addCabinetItem: vi.fn(),
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

vi.mock("@/components/medicines/medical-consent-gate", () => ({
  default: ({ children }: { children: ReactNode }) => <div data-testid="consent-gate">{children}</div>,
}));

vi.mock("@/lib/selfmed", () => ({
  scanReceiptFile: mocks.scanReceiptFile,
  scanReceiptText: mocks.scanReceiptText,
  importDetections: mocks.importDetections,
  addCabinetItem: mocks.addCabinetItem,
  isLowConfidenceDetection: (item: { requires_manual_confirm?: boolean; confidence: number }) =>
    item.requires_manual_confirm === true || item.confidence < 0.9,
}));

import CabinetAddPage from "@/components/medicines/cabinet-add-page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.scanReceiptText.mockResolvedValue([
    {
      drug_name: "Augmentin 625mg",
      normalized_name: "Amoxicillin and Clavulanate",
      dosage: "625 mg",
      brand_name: "Augmentin",
      manufacturer: "GSK",
      confidence: 0.95,
      evidence: "Augmentin 625mg tablet",
      mapping_source: "db",
    },
    {
      drug_name: "Panadol Extra",
      normalized_name: "Paracetamol and Caffeine",
      dosage: "500mg/65mg",
      confidence: 0.75, // Low confidence -> requires confirmation
      evidence: "Panadol Extra",
      requires_manual_confirm: true,
      mapping_source: "candidate",
    },
  ]);
  mocks.importDetections.mockResolvedValue(2);
  mocks.addCabinetItem.mockResolvedValue({ id: 1 });
});

afterEach(cleanup);

describe("CabinetAddPage Guided Wizard (Spec v5 Section 6.29)", () => {
  it("renders GuidedFlowShell with 3 distinct step progress stages", () => {
    render(<CabinetAddPage />);
    expect(screen.getByTestId("consent-gate")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Tiến trình" })).toHaveTextContent("Bước 1 / 3");
    expect(screen.getByText("Quét / Nhập thuốc")).toBeInTheDocument();
    expect(screen.getByText("Xác thực định danh")).toBeInTheDocument();
    expect(screen.getByText("Lưu vào tủ thuốc")).toBeInTheDocument();
  });

  it("validates empty inputs and performs text OCR scan to transition to Step 2", async () => {
    render(<CabinetAddPage />);

    // Switch to Text input mode
    fireEvent.click(screen.getByRole("button", { name: "Dán nội dung OCR" }));

    // Verify scan button is disabled when empty
    expect(screen.getByRole("button", { name: "Nhận diện từ nội dung đã dán" })).toBeDisabled();
    expect(mocks.scanReceiptText).not.toHaveBeenCalled();

    // Type OCR text and scan
    fireEvent.change(screen.getByLabelText("Nhập hoặc dán nội dung thuốc"), {
      target: { value: "Augmentin 625mg, Panadol Extra" },
    });
    expect(screen.getByRole("button", { name: "Nhận diện từ nội dung đã dán" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Nhận diện từ nội dung đã dán" }));

    await waitFor(() => {
      expect(mocks.scanReceiptText).toHaveBeenCalledWith("Augmentin 625mg, Panadol Extra");
      expect(screen.getAllByText("Xác thực định danh")[0]).toBeInTheDocument();
      expect(screen.getByRole("navigation", { name: "Tiến trình" })).toHaveTextContent("Bước 2 / 3");
    });
  });

  it("enforces confirmation of low-confidence detections before advancing to Step 3", async () => {
    render(<CabinetAddPage />);

    // Scan text
    fireEvent.click(screen.getByRole("button", { name: "Dán nội dung OCR" }));
    fireEvent.change(screen.getByLabelText("Nhập hoặc dán nội dung thuốc"), {
      target: { value: "Augmentin 625mg, Panadol Extra" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Nhận diện từ nội dung đã dán" }));

    await waitFor(() => {
      expect(screen.getByText("Augmentin 625mg")).toBeInTheDocument();
      expect(screen.getByText("Panadol Extra")).toBeInTheDocument();
    });

    // Check low-confidence item checkbox (Panadol Extra)
    const checkboxes = screen.getAllByRole("checkbox");
    // Check the selection checkbox for Panadol Extra (second item)
    fireEvent.click(checkboxes[1]);

    // Try to advance without confirming low confidence
    fireEvent.click(screen.getByRole("button", { name: "Lưu vào tủ thuốc" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Xác nhận các thuốc cần kiểm tra lại");

    // Check confirmation checkbox for Panadol Extra
    fireEvent.click(screen.getByLabelText("Tôi xác nhận thuốc OCR này đúng trước khi nhập."));

    // Advance to review step
    fireEvent.click(screen.getByRole("button", { name: "Lưu vào tủ thuốc" }));

    await waitFor(() => {
      expect(screen.getAllByText("Lưu vào tủ thuốc").length).toBeGreaterThan(0);
      expect(screen.getByRole("navigation", { name: "Tiến trình" })).toHaveTextContent("Bước 3 / 3");
    });

    // Verify cabinet safety disclaimer is prominent
    expect(
      screen.getAllByText(/Thuốc thêm vào tủ thuốc gia đình chỉ là danh mục sở hữu\/tồn kho dự phòng/).length,
    ).toBeGreaterThan(0);

    // Commit to cabinet
    fireEvent.click(screen.getByRole("button", { name: "Thêm 2 thuốc vào tủ" }));

    await waitFor(() => {
      expect(mocks.importDetections).toHaveBeenCalled();
      expect(mocks.replace).toHaveBeenCalledWith("/medicines?tab=cabinet");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });

  it("supports manual medicine entry and commits directly to cabinet", async () => {
    render(<CabinetAddPage />);

    // Switch to manual mode
    fireEvent.click(screen.getByRole("button", { name: "Thêm thủ công" }));

    fireEvent.change(screen.getByLabelText("Tên thuốc *"), {
      target: { value: "Amlodipine" },
    });
    fireEvent.change(screen.getByLabelText("Liều dùng *"), {
      target: { value: "5 mg" },
    });
    fireEvent.change(screen.getByLabelText("Số lượng"), {
      target: { value: "30" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Xác thực định danh" }));

    await waitFor(() => {
      expect(screen.getByText("Amlodipine")).toBeInTheDocument();
    });

    // Advance to review
    fireEvent.click(screen.getByRole("button", { name: "Lưu vào tủ thuốc" }));

    await waitFor(() => {
      expect(screen.getAllByText("Lưu vào tủ thuốc").length).toBeGreaterThan(0);
    });

    // Commit
    fireEvent.click(screen.getByRole("button", { name: "Thêm 1 thuốc vào tủ" }));

    await waitFor(() => {
      expect(mocks.addCabinetItem).toHaveBeenCalledWith({
        drug_name: "Amlodipine",
        brand_name: undefined,
        manufacturer: undefined,
        dosage: "5 mg",
        quantity: 30,
        source: "manual",
      });
      expect(mocks.replace).toHaveBeenCalledWith("/medicines?tab=cabinet");
    });
  });
});
