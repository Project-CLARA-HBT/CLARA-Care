import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DrugAutocompleteSearch } from "./drug-autocomplete-search";

const mockAddCabinetItem = vi.fn();

vi.mock("@/lib/selfmed", () => ({
  addCabinetItem: (...args: unknown[]) => mockAddCabinetItem(...args),
}));

describe("DrugAutocompleteSearch Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAddCabinetItem.mockResolvedValue({ id: 101, drug_name: "Panadol Extra" });
  });

  afterEach(cleanup);

  it("renders search input with placeholder and popular Vietnamese drug presets", () => {
    render(<DrugAutocompleteSearch />);

    const input = screen.getByRole("combobox");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute(
      "placeholder",
      "Tìm tên biệt dược (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...)",
    );

    // Popular chips
    expect(screen.getByText("+ Panadol Extra")).toBeInTheDocument();
    expect(screen.getByText("+ Glucophage XR")).toBeInTheDocument();
    expect(screen.getByText("+ Coversyl")).toBeInTheDocument();
    expect(screen.getByText("+ Augmentin")).toBeInTheDocument();
    expect(screen.getByText("+ Lipitor")).toBeInTheDocument();
  });

  it("shows autocomplete dropdown when typing a query like 'glucophage'", async () => {
    render(<DrugAutocompleteSearch />);

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "glucophage" } });

    await waitFor(() => {
      expect(screen.getByText("Glucophage XR")).toBeInTheDocument();
      expect(screen.getByText(/Metformin/)).toBeInTheDocument();
    });
  });

  it("calls onSelectDrug when clicking a suggestion", async () => {
    const onSelect = vi.fn();
    render(<DrugAutocompleteSearch onSelectDrug={onSelect} />);

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "coversyl" } });

    const suggestion = await screen.findByText("Coversyl");
    fireEvent.click(suggestion);

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        tradeName: "Coversyl",
        genericName: "Perindopril Arginine",
      }),
    );
  });

  it("executes 1-click 'Thêm nhanh vào Tủ thuốc' button from autocomplete dropdown", async () => {
    const onAdded = vi.fn();
    render(<DrugAutocompleteSearch onAddedToCabinet={onAdded} />);

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "augmentin" } });

    await screen.findByText("Augmentin");
    const addCabinetButtons = screen.getAllByRole("button", { name: /\+ Tủ thuốc/i });
    expect(addCabinetButtons.length).toBeGreaterThan(0);

    fireEvent.click(addCabinetButtons[0]);

    await waitFor(() => {
      expect(mockAddCabinetItem).toHaveBeenCalledWith(
        expect.objectContaining({
          drug_name: "Augmentin",
          brand_name: "Augmentin",
        }),
      );
      expect(screen.getByText(/Đã thêm "Augmentin" vào Tủ thuốc/)).toBeInTheDocument();
      expect(onAdded).toHaveBeenCalled();
    });
  });
});
