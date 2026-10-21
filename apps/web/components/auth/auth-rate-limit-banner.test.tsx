import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AuthRateLimitBanner from "./auth-rate-limit-banner";

describe("AuthRateLimitBanner Component", () => {
  it("renders cooldown warning banner when cooldownSeconds > 0", () => {
    render(
      <AuthRateLimitBanner
        cooldownSeconds={5}
        failedAttempts={2}
        isLockout={false}
        context="login"
        language="vi"
      />,
    );

    expect(screen.getByTestId("auth-rate-limit-banner")).toBeInTheDocument();
    expect(screen.getByText(/Vui lòng đợi 5 giây trước khi thử lại/i)).toBeInTheDocument();
  });

  it("renders lockout danger banner when isLockout is true", () => {
    render(
      <AuthRateLimitBanner
        cooldownSeconds={60}
        failedAttempts={5}
        isLockout={true}
        context="login"
        language="vi"
      />,
    );

    expect(screen.getByTestId("auth-rate-limit-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/Tài khoản tạm thời bị khóa do nhiều lần thử không thành công/i),
    ).toBeInTheDocument();
  });

  it("renders OTP attempt warning when context is otp and failedAttempts > 0", () => {
    render(
      <AuthRateLimitBanner
        cooldownSeconds={0}
        failedAttempts={2}
        isLockout={false}
        context="otp"
        language="vi"
      />,
    );

    expect(screen.getByTestId("auth-otp-attempt-warning")).toBeInTheDocument();
    expect(screen.getByText(/Bạn đã nhập sai 2 lần/i)).toBeInTheDocument();
  });

  it("renders nothing when there is no active cooldown or otp failures", () => {
    const { container } = render(
      <AuthRateLimitBanner
        cooldownSeconds={0}
        failedAttempts={0}
        isLockout={false}
        context="login"
        language="vi"
      />,
    );

    expect(container.firstChild).toBeNull();
  });
});
