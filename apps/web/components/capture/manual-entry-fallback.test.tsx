import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ManualEntryFallback, parseFreeformText } from "./manual-entry-fallback";

afterEach(cleanup);

describe("ManualEntryFallback Component & Parser", () => {
  it("parses blood pressure, heart rate, and medications from freeform text", () => {
    const text = "Huyết áp 130/85 mmHg\nNhịp tim 78 bpm\nParacetamol 500mg ngày uống 2 viên";
    const candidates = parseFreeformText(text, "vi");

    expect(candidates).toHaveLength(3);

    // 1. Blood Pressure
    expect(candidates[0].field_name).toBe("blood_pressure");
    expect(candidates[0].value).toEqual({ systolic: 130, diastolic: 85, unit: "mmHg" });

    // 2. Heart rate
    expect(candidates[1].field_name).toBe("heart_rate");
    expect(candidates[1].value).toBe(78);

    // 3. Medication
    expect(candidates[2].category).toBe("medication");
    expect(candidates[2].field_name).toBe("medication_name");
  });

  it("renders structured form mode and submits a medication item", () => {
    const onAddCandidate = vi.fn();

    render(<ManualEntryFallback onAddCandidate={onAddCandidate} locale="vi" />);

    expect(screen.getByTestId("manual-entry-fallback")).toBeInTheDocument();
    expect(screen.getByTestId("form-medication")).toBeInTheDocument();

    const nameInput = screen.getByTestId("input-med-name");
    fireEvent.change(nameInput, { target: { value: "Augmentin 1g" } });

    const dosageInput = screen.getByTestId("input-med-dosage");
    fireEvent.change(dosageInput, { target: { value: "1000mg" } });

    const addBtn = screen.getByTestId("btn-add-manual-item");
    fireEvent.click(addBtn);

    expect(onAddCandidate).toHaveBeenCalledWith(
      expect.objectContaining({
        category: "medication",
        field_name: "medication_name",
        display_name: "Augmentin 1g",
        value: expect.objectContaining({
          medication_name: "Augmentin 1g",
          dosage: "1000mg",
        }),
      }),
    );
  });

  it("switches to measurement form and submits blood pressure values", () => {
    const onAddCandidate = vi.fn();

    render(<ManualEntryFallback onAddCandidate={onAddCandidate} locale="vi" />);

    const measCatBtn = screen.getByTestId("manual-cat-measurement");
    fireEvent.click(measCatBtn);

    expect(screen.getByTestId("form-measurement")).toBeInTheDocument();

    const sysInput = screen.getByTestId("input-systolic");
    fireEvent.change(sysInput, { target: { value: "125" } });

    const diaInput = screen.getByTestId("input-diastolic");
    fireEvent.change(diaInput, { target: { value: "82" } });

    const addBtn = screen.getByTestId("btn-add-manual-item");
    fireEvent.click(addBtn);

    expect(onAddCandidate).toHaveBeenCalledWith(
      expect.objectContaining({
        category: "measurement",
        field_name: "blood_pressure",
        value: { systolic: 125, diastolic: 82, unit: "mmHg" },
      }),
    );
  });

  it("switches to freeform text mode and parses text into candidates", () => {
    const onAddMultiple = vi.fn();

    render(
      <ManualEntryFallback
        onAddCandidate={vi.fn()}
        onAddMultipleCandidates={onAddMultiple}
        locale="vi"
      />,
    );

    const freeformTab = screen.getByTestId("manual-mode-freeform");
    fireEvent.click(freeformTab);

    const textarea = screen.getByTestId("freeform-textarea");
    fireEvent.change(textarea, { target: { value: "Huyết áp 120/80\nGlucose 5.5 mmol/L" } });

    const parseBtn = screen.getByTestId("btn-parse-freeform");
    fireEvent.click(parseBtn);

    expect(onAddMultiple).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ field_name: "blood_pressure" }),
        expect.objectContaining({ field_name: "blood_glucose" }),
      ]),
    );
  });
});
