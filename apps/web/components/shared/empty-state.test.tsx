import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EmptyState } from "./empty-state";

afterEach(cleanup);

describe("EmptyState", () => {
  it("renders title, description and primary action", () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        title="Chưa có hành trình nào"
        description="Khi bạn tạo hành trình theo dõi sức khỏe, thông tin sẽ xuất hiện tại đây."
        actionLabel="Tạo hành trình mới"
        onAction={onAction}
      />,
    );

    expect(screen.getByText("Chưa có hành trình nào")).toBeInTheDocument();
    expect(
      screen.getByText("Khi bạn tạo hành trình theo dõi sức khỏe, thông tin sẽ xuất hiện tại đây."),
    ).toBeInTheDocument();

    const btn = screen.getByRole("button", { name: "Tạo hành trình mới" });
    fireEvent.click(btn);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("renders links for primary and secondary actions", () => {
    render(
      <EmptyState
        title="Chưa có thuốc trong tủ thuốc"
        description="Thêm thuốc để theo dõi lịch uống và kiểm tra tương tác."
        actionLabel="Thêm thuốc"
        actionHref="/medicines/add"
        secondaryActionLabel="Tìm hiểu thêm"
        secondaryActionHref="/help"
      />,
    );

    const primaryLink = screen.getByRole("link", { name: "Thêm thuốc" });
    expect(primaryLink).toHaveAttribute("href", "/medicines/add");

    const secondaryLink = screen.getByRole("link", { name: "Tìm hiểu thêm" });
    expect(secondaryLink).toHaveAttribute("href", "/help");
  });

  it("does not render false health reassurance (safety check)", () => {
    const { container } = render(
      <EmptyState
        title="Không có lịch hẹn"
        description="Bạn chưa có lịch hẹn khám sắp tới."
      />,
    );

    // Ensure content explains missing state without fabricating health status
    expect(container.textContent).not.toContain("Bạn hoàn toàn khỏe mạnh");
    expect(container.textContent).not.toContain("Không có bệnh tật gì");
  });
});
