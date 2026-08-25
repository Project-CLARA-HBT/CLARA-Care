import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuickInteractionChecker } from "./quick-interaction-checker";

const mockAddCabinetItem = vi.fn();
const mockGetCabinet = vi.fn();
const mockAnalyzeCareguard = vi.fn();

vi.mock("@/lib/selfmed", () => ({
  addCabinetItem: (...args: unknown[]) => mockAddCabinetItem(...args),
  getCabinet: (...args: unknown[]) => mockGetCabinet(...args),
}));

vi.mock("@/lib/careguard", () => ({
  analyzeCareguard: (...args: unknown[]) => mockAnalyzeCareguard(...args),
}));

describe("QuickInteractionChecker Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCabinet.mockResolvedValue({
      cabinet_id: 1,
      label: "Tủ thuốc gia đình",
      items: [
        { id: 1, drug_name: "Panadol Extra", dosage: "500mg", source: "manual" },
        { id: 2, drug_name: "Augmentin", dosage: "625mg", source: "manual" },
      ],
    });
    mockAddCabinetItem.mockResolvedValue({ id: 99, drug_name: "Lipitor" });
    mockAnalyzeCareguard.mockResolvedValue({ risk_tier: "low", ddi_alerts: [] });
  });

  afterEach(cleanup);

  it("renders the instant 1-click drug interaction search workspace", () => {
    render(<QuickInteractionChecker />);

    expect(screen.getByText("Kiểm tra Tương tác Thuốc Tức thì")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("+ Panadol Extra")).toBeInTheDocument();
    expect(screen.getByText("+ Glucophage XR")).toBeInTheDocument();
    expect(screen.getByText("+ Coversyl")).toBeInTheDocument();
    expect(screen.getByText("+ Augmentin")).toBeInTheDocument();
    expect(screen.getByText("+ Lipitor")).toBeInTheDocument();
  });

  it("adds drugs to the comparison tray via 1-click popular preset chips", async () => {
    render(<QuickInteractionChecker />);

    const panadolChip = screen.getByText("+ Panadol Extra");
    fireEvent.click(panadolChip);

    await waitFor(() => {
      expect(
        screen.getByText("2. Thuốc đang được chọn để đối chiếu (1):"),
      ).toBeInTheDocument();
      expect(screen.getAllByText("Panadol Extra").length).toBeGreaterThan(0);
    });

    const glucophageChip = screen.getByText("+ Glucophage XR");
    fireEvent.click(glucophageChip);

    await waitFor(() => {
      expect(
        screen.getByText("2. Thuốc đang được chọn để đối chiếu (2):"),
      ).toBeInTheDocument();
      expect(screen.getByText("Glucophage XR")).toBeInTheDocument();
    });
  });

  it("triggers instant interaction check and displays Traffic-Light Safety Indicator", async () => {
    render(<QuickInteractionChecker />);

    // Add Plavix and Aspirin Protect (which trigger red/dangerous interaction)
    fireEvent.click(screen.getByText("+ Plavix"));
    fireEvent.click(screen.getByText("+ Aspirin Protect"));

    await waitFor(() => {
      const indicator = screen.getByTestId("traffic-light-safety-indicator");
      expect(indicator).toBeInTheDocument();
      expect(indicator).toHaveAttribute("data-safety-level", "danger");
      expect(screen.getByText("ĐỎ: TƯƠNG TÁC NGUY HIỂM")).toBeInTheDocument();
      expect(screen.getByText(/Tăng nguy cơ xuất huyết/)).toBeInTheDocument();
    });
  });

  it("executes 1-click 'Thêm tất cả vào Tủ thuốc' button", async () => {
    const onCabinetUpdated = vi.fn();
    render(<QuickInteractionChecker onCabinetUpdated={onCabinetUpdated} />);

    fireEvent.click(screen.getByText("+ Augmentin"));
    fireEvent.click(screen.getByText("+ Lipitor"));

    const addAllBtn = await screen.findByRole("button", { name: /1-Click Thêm tất cả \(2\) vào Tủ thuốc/i });
    fireEvent.click(addAllBtn);

    await waitFor(() => {
      expect(mockAddCabinetItem).toHaveBeenCalledTimes(2);
      expect(screen.getByText(/Đã thêm nhanh 2 thuốc vào Tủ thuốc gia đình!/)).toBeInTheDocument();
      expect(onCabinetUpdated).toHaveBeenCalled();
    });
  });

  it("imports items from existing cabinet with 1 click", async () => {
    render(<QuickInteractionChecker />);

    const importBtn = await screen.findByRole("button", { name: /Lấy từ Tủ thuốc \(2\)/i });
    fireEvent.click(importBtn);

    await waitFor(() => {
      expect(screen.getByText(/Đã nhập 2 thuốc từ Tủ thuốc gia đình để kiểm tra/)).toBeInTheDocument();
      expect(
        screen.getByText("2. Thuốc đang được chọn để đối chiếu (2):"),
      ).toBeInTheDocument();
    });
  });
});
