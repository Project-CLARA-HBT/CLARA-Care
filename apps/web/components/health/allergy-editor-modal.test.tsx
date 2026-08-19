import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AllergyEditorModal } from "./allergy-editor-modal";
import * as v2ClientModule from "@/lib/api/v2-client";
import { ApiV2ClientError } from "@/lib/api/v2-client";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("AllergyEditorModal", () => {
  const mockAllergy: v2ClientModule.HealthAllergyDto = {
    id: "alg-1",
    substance: "Aspirin",
    reaction: "Nổi mẩn ngứa",
    severity: "moderate",
    verification_state: "confirmed",
    base_version: "v1",
  };

  it("renders create form when no allergy is passed", async () => {
    const addSpy = vi.spyOn(v2ClientModule, "apiV2AddAllergy").mockResolvedValueOnce({
      id: "alg-2",
      substance: "Peanut",
      severity: "severe",
    });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <AllergyEditorModal
        open={true}
        onClose={closeSpy}
        onSuccess={successSpy}
      />,
    );

    expect(screen.getByText("Thêm dị ứng / Không dung nạp")).toBeInTheDocument();

    const substanceInput = screen.getByTestId("field-allergy-substance");
    fireEvent.change(substanceInput, { target: { value: "Peanut" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledTimes(1);
    });

    expect(addSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        substance: "Peanut",
        severity: "moderate",
        source_kind: "patient",
      }),
    );
    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("renders edit form and submits update with base_version", async () => {
    const updateSpy = vi.spyOn(v2ClientModule, "apiV2UpdateAllergy").mockResolvedValueOnce({
      ...mockAllergy,
      severity: "severe",
    });

    render(
      <AllergyEditorModal
        open={true}
        onClose={vi.fn()}
        allergy={mockAllergy}
      />,
    );

    expect(screen.getByText("Chỉnh sửa thông tin dị ứng")).toBeInTheDocument();
    expect(screen.getByTestId("field-allergy-substance")).toHaveValue("Aspirin");

    const severitySelect = screen.getByTestId("field-allergy-severity");
    fireEvent.change(severitySelect, { target: { value: "severe" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "alg-1",
        expect.objectContaining({
          substance: "Aspirin",
          severity: "severe",
          base_version: "v1",
        }),
        expect.objectContaining({
          baseVersion: "v1",
        }),
      );
    });
  });

  it("deletes allergy when delete button is confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteSpy = vi.spyOn(v2ClientModule, "apiV2DeleteAllergy").mockResolvedValueOnce({
      success: true,
    });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <AllergyEditorModal
        open={true}
        onClose={closeSpy}
        allergy={mockAllergy}
        onSuccess={successSpy}
      />,
    );

    const deleteBtn = screen.getByRole("button", { name: "Xóa" });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith("alg-1");
    });

    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("handles 409 conflict during allergy update", async () => {
    const conflictError = new ApiV2ClientError({
      message: "State conflict",
      code: "state_conflict",
      status: 409,
      currentVersion: "v3",
      changedFields: ["severity"],
      details: { severity: "severe", substance: "Aspirin 500mg" },
    });

    vi.spyOn(v2ClientModule, "apiV2UpdateAllergy").mockRejectedValueOnce(conflictError);

    render(
      <AllergyEditorModal
        open={true}
        onClose={vi.fn()}
        allergy={mockAllergy}
      />,
    );

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    expect(screen.getByText(/Xung đột dữ liệu: Bản ghi dị ứng/i)).toBeInTheDocument();
  });
});
