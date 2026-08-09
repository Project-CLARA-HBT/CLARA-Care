import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Modal } from "@/components/ui/modal";

afterEach(cleanup);

describe("Modal", () => {
  it("labels the dialog through its visible title and description", () => {
    render(
      <Modal open onClose={vi.fn()} title="Xác nhận lưu" description="Kiểm tra lại thông tin trước khi lưu.">
        <button type="button">Lưu hồ sơ</button>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog", { name: "Xác nhận lưu" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.getAttribute("aria-labelledby")).toContain("-title");
    expect(dialog.getAttribute("aria-describedby")).toContain("-description");
    expect(screen.getByText("Kiểm tra lại thông tin trước khi lưu.")).toHaveAttribute(
      "id",
      dialog.getAttribute("aria-describedby"),
    );
  });

  it("closes through Escape without relying on a pointer action", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Xác nhận">
        <button type="button">Tiếp tục</button>
      </Modal>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("supports alertdialog semantics for destructive confirmations", () => {
    render(
      <Modal open role="alertdialog" onClose={vi.fn()} title="Xóa dữ liệu ghi âm">
        <button type="button">Xóa</button>
      </Modal>,
    );

    expect(screen.getByRole("alertdialog", { name: "Xóa dữ liệu ghi âm" })).toHaveAttribute(
      "aria-modal",
      "true",
    );
  });
});
