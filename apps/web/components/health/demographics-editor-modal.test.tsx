import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemographicsEditorModal } from "./demographics-editor-modal";
import * as v2ClientModule from "@/lib/api/v2-client";
import { ApiV2ClientError } from "@/lib/api/v2-client";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("DemographicsEditorModal", () => {
  const initialData: v2ClientModule.HealthDemographicsDto = {
    full_name: "Nguyễn Văn A",
    date_of_birth: "1990-01-01",
    gender: "male",
    blood_type: "O+",
    phone_number: "0901234567",
    emergency_contact: {
      name: "Nguyễn Thị B",
      relationship: "Vợ",
      phone: "0907654321",
    },
    base_version: "v1",
  };

  it("renders form fields populated with initial demographics", () => {
    render(
      <DemographicsEditorModal
        open={true}
        onClose={vi.fn()}
        initialData={initialData}
      />,
    );

    expect(screen.getByTestId("field-demographics-fullname")).toHaveValue("Nguyễn Văn A");
    expect(screen.getByTestId("field-demographics-dob")).toHaveValue("1990-01-01");
    expect(screen.getByTestId("field-demographics-gender")).toHaveValue("male");
    expect(screen.getByTestId("field-demographics-bloodtype")).toHaveValue("O+");
    expect(screen.getByTestId("field-demographics-emergency-name")).toHaveValue("Nguyễn Thị B");
  });

  it("submits updated data with base_version precondition", async () => {
    const updateSpy = vi
      .spyOn(v2ClientModule, "apiV2UpdateDemographics")
      .mockResolvedValueOnce({
        ...initialData,
        full_name: "Nguyễn Văn A (Cập nhật)",
      });

    const successSpy = vi.fn();
    const closeSpy = vi.fn();

    render(
      <DemographicsEditorModal
        open={true}
        onClose={closeSpy}
        initialData={initialData}
        onSuccess={successSpy}
      />,
    );

    const nameInput = screen.getByTestId("field-demographics-fullname");
    fireEvent.change(nameInput, { target: { value: "Nguyễn Văn A (Cập nhật)" } });

    const saveBtn = screen.getByRole("button", { name: "Lưu thay đổi" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledTimes(1);
    });

    expect(updateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: "Nguyễn Văn A (Cập nhật)",
        base_version: "v1",
      }),
      expect.objectContaining({
        baseVersion: "v1",
      }),
    );
    expect(successSpy).toHaveBeenCalledTimes(1);
    expect(closeSpy).toHaveBeenCalledTimes(1);
  });

  it("handles 409 write conflict by displaying ConflictResolverModal", async () => {
    const conflictError = new ApiV2ClientError({
      message: "State conflict",
      code: "state_conflict",
      status: 409,
      currentVersion: "v2",
      changedFields: ["full_name"],
      details: { full_name: "Nguyễn Văn A (Server Edit)" },
    });

    vi.spyOn(v2ClientModule, "apiV2UpdateDemographics").mockRejectedValueOnce(conflictError);

    render(
      <DemographicsEditorModal
        open={true}
        onClose={vi.fn()}
        initialData={initialData}
      />,
    );

    const saveBtn = screen.getByRole("button", { name: "Lưu thay đổi" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    });

    expect(screen.getByText(/Xung đột dữ liệu: Thông tin cá nhân/i)).toBeInTheDocument();
  });
});
