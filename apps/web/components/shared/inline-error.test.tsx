import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InlineError } from "./inline-error";

afterEach(cleanup);

describe("InlineError", () => {
  it("renders error message and alert role", () => {
    render(
      <InlineError
        title="Lỗi tải dữ liệu"
        message="Không thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng."
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText("Lỗi tải dữ liệu")).toBeInTheDocument();
    expect(
      screen.getByText("Không thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng."),
    ).toBeInTheDocument();
  });

  it("handles retry action", () => {
    const onRetry = vi.fn();
    render(
      <InlineError
        message="Yêu cầu hết thời gian chờ."
        onRetry={onRetry}
        retryLabel="Thử lại"
      />,
    );

    const retryBtn = screen.getByTestId("inline-error-retry");
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("handles dismiss action", () => {
    const onDismiss = vi.fn();
    render(
      <InlineError
        message="Thông báo có thể đóng."
        onDismiss={onDismiss}
        dismissLabel="Đóng thông báo"
      />,
    );

    const dismissBtn = screen.getByTestId("inline-error-dismiss");
    fireEvent.click(dismissBtn);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("supports warning and info severity levels", () => {
    const { rerender } = render(
      <InlineError
        severity="warning"
        message="Dữ liệu chưa được đồng bộ hoàn toàn."
      />,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();

    rerender(
      <InlineError
        severity="info"
        message="Đã lưu bản nháp tự động."
      />,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
