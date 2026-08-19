import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MeasurementEditorModal } from "./measurement-editor-modal";
import * as v2ClientModule from "@/lib/api/v2-client";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("MeasurementEditorModal", () => {
  it("submits blood pressure with systolic and diastolic components", async () => {
    const addSpy = vi.spyOn(v2ClientModule, "apiV2AddMeasurement").mockResolvedValueOnce({
      id: "m-1",
      type: "blood_pressure",
      value: "120/80",
      systolic: 120,
      diastolic: 80,
      unit: "mmHg",
      recorded_at: "2026-08-19T08:00:00.000Z",
    });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <MeasurementEditorModal
        open={true}
        onClose={closeSpy}
        defaultType="blood_pressure"
        onSuccess={successSpy}
      />,
    );

    const sysInput = screen.getByTestId("field-measurement-systolic");
    const diaInput = screen.getByTestId("field-measurement-diastolic");

    fireEvent.change(sysInput, { target: { value: "120" } });
    fireEvent.change(diaInput, { target: { value: "80" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu chỉ số" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledTimes(1);
    });

    expect(addSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "blood_pressure",
        value: "120/80",
        systolic: 120,
        diastolic: 80,
        unit: "mmHg",
      }),
    );
    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("submits single value metric such as blood glucose", async () => {
    const addSpy = vi.spyOn(v2ClientModule, "apiV2AddMeasurement").mockResolvedValueOnce({
      id: "m-2",
      type: "blood_glucose",
      value: "5.6",
      unit: "mmol/L",
      recorded_at: "2026-08-19T08:00:00.000Z",
    });

    render(
      <MeasurementEditorModal
        open={true}
        onClose={vi.fn()}
        defaultType="blood_glucose"
      />,
    );

    const valueInput = screen.getByTestId("field-measurement-value");
    fireEvent.change(valueInput, { target: { value: "5.6" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu chỉ số" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "blood_glucose",
          value: "5.6",
          unit: "mmol/L",
        }),
      );
    });
  });
});
