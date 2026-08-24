import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ActionBar,
  type ActionBarAction,
  type ActionBarProps,
} from "./action-bar";

describe("ActionBar Component (Spec v8 Section 5.9)", () => {
  it("renders floating contextual action bar with default role='toolbar' and accessible label", () => {
    render(
      <ActionBar
        step={2}
        totalSteps={4}
        status="Đang chỉnh sửa đơn thuốc"
        primaryAction={{ label: "Tiếp tục", onClick: vi.fn() }}
      />,
    );

    const toolbar = screen.getByRole("toolbar", {
      name: "Thanh thao tác quy trình",
    });
    expect(toolbar).toBeInTheDocument();
    expect(toolbar).toHaveAttribute("data-variant", "floating");
    expect(screen.getByText("Bước 2/4")).toBeInTheDocument();
    expect(screen.getByText("Đang chỉnh sửa đơn thuốc")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tiếp tục" })).toBeInTheDocument();
  });

  it("supports sticky and inline variants", () => {
    const { rerender } = render(
      <ActionBar
        variant="sticky"
        primaryAction={{ label: "Lưu thay đổi", onClick: vi.fn() }}
      />,
    );

    let bar = screen.getByTestId("action-bar");
    expect(bar).toHaveAttribute("data-variant", "sticky");

    rerender(
      <ActionBar
        variant="inline"
        primaryAction={{ label: "Lưu thay đổi", onClick: vi.fn() }}
      />,
    );

    bar = screen.getByTestId("action-bar");
    expect(bar).toHaveAttribute("data-variant", "inline");
  });

  it("renders multi-step progress bar when showProgress is true", () => {
    render(
      <ActionBar
        step={3}
        totalSteps={4}
        showProgress={true}
        primaryAction={{ label: "Xác nhận", onClick: vi.fn() }}
      />,
    );

    const progress = screen.getByRole("progressbar");
    expect(progress).toBeInTheDocument();
    expect(progress).toHaveAttribute("aria-valuenow", "75");
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders explicit progress percentage when provided", () => {
    render(
      <ActionBar
        showProgress={true}
        progress={90}
        primaryAction={{ label: "Hoàn tất", onClick: vi.fn() }}
      />,
    );

    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "90");
  });

  it("displays dirty state notice when form has unsaved modifications", () => {
    render(
      <ActionBar
        dirty={true}
        unsavedChangesLabel="Có 2 thay đổi chưa lưu"
        primaryAction={{ label: "Lưu", onClick: vi.fn() }}
      />,
    );

    expect(screen.getByText("Có 2 thay đổi chưa lưu")).toBeInTheDocument();
  });

  it("handles workflow navigation callbacks (onNext, onPrevious, onCancel, onSave, onReset)", () => {
    const handleNext = vi.fn();
    const handlePrev = vi.fn();
    const handleCancel = vi.fn();
    const handleReset = vi.fn();

    render(
      <ActionBar
        onPrevious={handlePrev}
        onNext={handleNext}
        onCancel={handleCancel}
        onReset={handleReset}
        nextLabel="Chuyển bước"
        prevLabel="Lùi lại"
        cancelLabel="Đóng"
        resetLabel="Khôi phục"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Lùi lại" }));
    expect(handlePrev).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Chuyển bước" }));
    expect(handleNext).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Đóng" }));
    expect(handleCancel).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Khôi phục" }));
    expect(handleReset).toHaveBeenCalledTimes(1);
  });

  it("handles keyboard shortcuts (Cmd+S / Ctrl+S to save, Escape to cancel)", () => {
    const handleSave = vi.fn();
    const handleCancel = vi.fn();

    render(
      <ActionBar
        onSave={handleSave}
        onCancel={handleCancel}
      />,
    );

    // Trigger Cmd+S
    fireEvent.keyDown(window, { key: "s", metaKey: true });
    expect(handleSave).toHaveBeenCalledTimes(1);

    // Trigger Ctrl+S
    fireEvent.keyDown(window, { key: "s", ctrlKey: true });
    expect(handleSave).toHaveBeenCalledTimes(2);

    // Trigger Escape
    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });

  it("disables actions and renders loading indicators when isBusy / loading is true", () => {
    const handleNext = vi.fn();

    render(
      <ActionBar
        isBusy={true}
        onNext={handleNext}
        secondaryAction={{ label: "Hủy", onClick: vi.fn() }}
      />,
    );

    const nextBtn = screen.getByTestId("action-bar-next");
    expect(nextBtn).toBeDisabled();

    fireEvent.click(nextBtn);
    expect(handleNext).not.toHaveBeenCalled();
  });

  it("renders secondary and danger action buttons with appropriate styles and handlers", () => {
    const handleSecondary = vi.fn();
    const handleDanger = vi.fn();

    render(
      <ActionBar
        secondaryAction={{
          label: "Xuất PDF",
          variant: "secondary",
          onClick: handleSecondary,
        }}
        dangerAction={{
          label: "Xóa đơn",
          variant: "danger",
          onClick: handleDanger,
        }}
      />,
    );

    const secBtn = screen.getByRole("button", { name: "Xuất PDF" });
    fireEvent.click(secBtn);
    expect(handleSecondary).toHaveBeenCalledTimes(1);

    const dangerBtn = screen.getByRole("button", { name: "Xóa đơn" });
    fireEvent.click(dangerBtn);
    expect(handleDanger).toHaveBeenCalledTimes(1);
  });

  it("renders Link action when href is provided in action item", () => {
    const linkAction: ActionBarAction = {
      label: "Xem hướng dẫn",
      href: "/huong-dan",
      variant: "outline",
    };

    render(<ActionBar primaryAction={linkAction} />);

    const link = screen.getByRole("link", { name: "Xem hướng dẫn" });
    expect(link).toHaveAttribute("href", "/huong-dan");
  });

  it("renders reserveSafeArea spacer when reserveSafeArea is true", () => {
    render(
      <ActionBar
        reserveSafeArea={true}
        primaryAction={{ label: "Xác nhận", onClick: vi.fn() }}
      />,
    );

    expect(screen.getByTestId("action-bar-safe-area-spacer")).toBeInTheDocument();
  });

  it("supports width presets (prose, instrument, workbench, full-bleed, numeric)", () => {
    const { container, rerender } = render(
      <ActionBar
        maxWidth="prose"
        primaryAction={{ label: "Lưu", onClick: vi.fn() }}
      />,
    );

    let bar = container.querySelector("aside");
    expect(bar).toHaveClass("max-w-3xl");

    rerender(
      <ActionBar
        maxWidth="workbench"
        primaryAction={{ label: "Lưu", onClick: vi.fn() }}
      />,
    );
    bar = container.querySelector("aside");
    expect(bar).toHaveClass("max-w-7xl");

    rerender(
      <ActionBar
        maxWidth="full-bleed"
        primaryAction={{ label: "Lưu", onClick: vi.fn() }}
      />,
    );
    bar = container.querySelector("aside");
    expect(bar).toHaveClass("max-w-full");

    rerender(
      <ActionBar
        maxWidth={640}
        primaryAction={{ label: "Lưu", onClick: vi.fn() }}
      />,
    );
    bar = container.querySelector("aside");
    expect(bar?.style.maxWidth).toBe("640px");
  });

  it("supports leading, center, trailing slots and custom children", () => {
    render(
      <ActionBar
        leading={<div data-testid="custom-leading">Custom Leading Slot</div>}
        center={<div data-testid="custom-center">Center Alignment</div>}
        trailing={<div data-testid="custom-trailing">Trailing Action Slot</div>}
      >
        <button type="button">Extra Custom Button</button>
      </ActionBar>,
    );

    expect(screen.getByTestId("custom-leading")).toBeInTheDocument();
    expect(screen.getByTestId("custom-center")).toBeInTheDocument();
    expect(screen.getByTestId("custom-trailing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Extra Custom Button" })).toBeInTheDocument();
  });
});
