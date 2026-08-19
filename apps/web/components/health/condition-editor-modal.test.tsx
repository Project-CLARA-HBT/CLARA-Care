import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConditionEditorModal } from "./condition-editor-modal";
import * as v2ClientModule from "@/lib/api/v2-client";
import { ApiV2ClientError } from "@/lib/api/v2-client";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConditionEditorModal", () => {
  const mockCondition: v2ClientModule.HealthConditionDto = {
    id: "cond-1",
    name: "Tăng huyết áp vô căn",
    clinical_status: "active",
    verification_status: "confirmed",
    onset_date: "2024-05-10",
    notes: "Uống thuốc đều đặn",
    base_version: "v2",
  };

  it("renders create form and submits new condition", async () => {
    const addSpy = vi.spyOn(v2ClientModule, "apiV2AddCondition").mockResolvedValueOnce({
      id: "cond-2",
      name: "Hen phế quản",
      clinical_status: "active",
    });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <ConditionEditorModal
        open={true}
        onClose={closeSpy}
        onSuccess={successSpy}
      />,
    );

    expect(screen.getByText("Thêm bệnh nền / Tình trạng sức khỏe")).toBeInTheDocument();

    const nameInput = screen.getByTestId("field-condition-name");
    fireEvent.change(nameInput, { target: { value: "Hen phế quản" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(addSpy).toHaveBeenCalledTimes(1);
    });

    expect(addSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Hen phế quản",
        clinical_status: "active",
      }),
    );
    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("renders edit form and submits update with base_version", async () => {
    const updateSpy = vi.spyOn(v2ClientModule, "apiV2UpdateCondition").mockResolvedValueOnce({
      ...mockCondition,
      clinical_status: "resolved",
    });

    render(
      <ConditionEditorModal
        open={true}
        onClose={vi.fn()}
        condition={mockCondition}
      />,
    );

    expect(screen.getByText("Chỉnh sửa bệnh nền / tình trạng")).toBeInTheDocument();
    expect(screen.getByTestId("field-condition-name")).toHaveValue("Tăng huyết áp vô căn");

    const statusSelect = screen.getByTestId("field-condition-status");
    fireEvent.change(statusSelect, { target: { value: "resolved" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "cond-1",
        expect.objectContaining({
          name: "Tăng huyết áp vô căn",
          clinical_status: "resolved",
          base_version: "v2",
        }),
        expect.objectContaining({
          baseVersion: "v2",
        }),
      );
    });
  });

  it("deletes condition when delete button is confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteSpy = vi.spyOn(v2ClientModule, "apiV2DeleteCondition").mockResolvedValueOnce({
      success: true,
    });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <ConditionEditorModal
        open={true}
        onClose={closeSpy}
        condition={mockCondition}
        onSuccess={successSpy}
      />,
    );

    const deleteBtn = screen.getByRole("button", { name: "Xóa" });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith("cond-1");
    });

    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("handles 409 conflict during condition update", async () => {
    const conflictError = new ApiV2ClientError({
      message: "State conflict",
      code: "state_conflict",
      status: 409,
      currentVersion: "v4",
      changedFields: ["clinical_status"],
      details: { clinical_status: "inactive" },
    });

    vi.spyOn(v2ClientModule, "apiV2UpdateCondition").mockRejectedValueOnce(conflictError);

    render(
      <ConditionEditorModal
        open={true}
        onClose={vi.fn()}
        condition={mockCondition}
      />,
    );

    const saveBtn = screen.getByRole("button", { name: "Lưu" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    expect(screen.getByText(/Xung đột dữ liệu: Bản ghi bệnh nền/i)).toBeInTheDocument();
  });
});
