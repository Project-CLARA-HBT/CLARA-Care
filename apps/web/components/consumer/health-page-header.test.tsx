import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HealthPageHeader } from "./health-page-header";

afterEach(cleanup);

describe("HealthPageHeader", () => {
  it("renders page title as h1 and subtitle", () => {
    render(
      <HealthPageHeader
        title="Tủ thuốc gia đình"
        subtitle="Quản lý các loại thuốc đang dùng và cảnh báo tương tác."
      />,
    );

    const h1 = screen.getByRole("heading", { level: 1, name: "Tủ thuốc gia đình" });
    expect(h1).toBeInTheDocument();
    expect(
      screen.getByText("Quản lý các loại thuốc đang dùng và cảnh báo tương tác."),
    ).toBeInTheDocument();
  });

  it("renders active profile banner with name, relationship and switch button", () => {
    const onSwitch = vi.fn();
    render(
      <HealthPageHeader
        title="Hành trình sức khỏe"
        activeProfile={{
          name: "Nguyễn Thị Mai",
          relationship: "Mẹ",
        }}
        onSwitchProfile={onSwitch}
      />,
    );

    expect(screen.getByText("Nguyễn Thị Mai")).toBeInTheDocument();
    expect(screen.getByText("Mẹ")).toBeInTheDocument();

    const switchBtn = screen.getByTestId("header-switch-profile-btn");
    fireEvent.click(switchBtn);
    expect(onSwitch).toHaveBeenCalledTimes(1);
  });

  it("renders primary and secondary actions", () => {
    const onPrimary = vi.fn();
    render(
      <HealthPageHeader
        title="Buổi khám sắp tới"
        primaryAction={{
          label: "Tạo buổi khám mới",
          onClick: onPrimary,
          icon: "plus",
        }}
        secondaryAction={{
          label: "Lịch sử khám",
          href: "/visits/history",
        }}
      />,
    );

    const primaryBtn = screen.getByRole("button", { name: "Tạo buổi khám mới" });
    fireEvent.click(primaryBtn);
    expect(onPrimary).toHaveBeenCalledTimes(1);

    const secondaryLink = screen.getByRole("link", { name: "Lịch sử khám" });
    expect(secondaryLink).toHaveAttribute("href", "/visits/history");
  });

  it("renders back link if backHref is provided", () => {
    render(
      <HealthPageHeader
        title="Chi tiết đơn thuốc"
        backHref="/medicines"
        backLabel="Quay lại danh sách"
      />,
    );

    const backLink = screen.getByTestId("health-page-back-link");
    expect(backLink).toHaveAttribute("href", "/medicines");
    expect(screen.getByText("Quay lại danh sách")).toBeInTheDocument();
  });
});
