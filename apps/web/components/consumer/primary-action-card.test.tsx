import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PrimaryActionCard } from "./primary-action-card";

afterEach(cleanup);

describe("PrimaryActionCard", () => {
  it("renders title, description, and primary action button", () => {
    const onAction = vi.fn();
    render(
      <PrimaryActionCard
        title="Uống thuốc huyết áp buổi sáng"
        description="Amlodipine 5mg - 1 viên sau ăn sáng."
        actionLabel="Đã uống thuốc"
        onAction={onAction}
        severity="high"
        locale="vi"
      />,
    );

    expect(screen.getByText("Uống thuốc huyết áp buổi sáng")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg - 1 viên sau ăn sáng.")).toBeInTheDocument();
    expect(screen.getByText("Ưu tiên cao")).toBeInTheDocument();

    const actionButton = screen.getByRole("button", { name: "Đã uống thuốc" });
    fireEvent.click(actionButton);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("renders with link href when actionHref is passed", () => {
    render(
      <PrimaryActionCard
        title="Tạo hành trình theo dõi huyết áp"
        actionLabel="Bắt đầu ngay"
        actionHref="/lifemap/new"
        severity="info"
        locale="en"
      />,
    );

    expect(screen.getByText("Suggested")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Bắt đầu ngay" });
    expect(link).toHaveAttribute("href", "/lifemap/new");
  });

  it("handles loading state properly", () => {
    render(
      <PrimaryActionCard
        title="Đang đồng bộ dữ liệu"
        actionLabel="Xác nhận"
        loading={true}
        loadingLabel="Đang xử lý..."
        onAction={vi.fn()}
      />,
    );

    const card = screen.getByTestId("primary-action-card");
    expect(card).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Đang xử lý...")).toBeInTheDocument();
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });

  it("displays error with retry callback", () => {
    const onRetry = vi.fn();
    render(
      <PrimaryActionCard
        title="Lưu lịch khám"
        actionLabel="Lưu"
        error="Không thể kết nối máy chủ"
        onRetry={onRetry}
        retryLabel="Thử lại ngay"
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Không thể kết nối máy chủ")).toBeInTheDocument();

    const retryBtn = screen.getByText("Thử lại ngay");
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders secondary action if provided", () => {
    const onSecondary = vi.fn();
    render(
      <PrimaryActionCard
        title="Thông báo lịch khám"
        actionLabel="Xác nhận tham gia"
        onAction={vi.fn()}
        secondaryActionLabel="Để sau"
        onSecondaryAction={onSecondary}
      />,
    );

    const secondaryBtn = screen.getByRole("button", { name: "Để sau" });
    fireEvent.click(secondaryBtn);
    expect(onSecondary).toHaveBeenCalledTimes(1);
  });
});
