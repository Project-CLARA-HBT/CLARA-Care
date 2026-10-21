import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import LoginPage from "../login/page";
import RegisterPage from "../register/page";
import ForgotPasswordPage from "../forgot-password/page";
import AuthCallbackPage from "./callback/page";
import ResetPasswordPage from "../reset-password/page";
import VerifyEmailPage from "../verify-email/page";
import AppShell from "@/components/app-shell";
import { PreferenceProvider } from "@/components/shell/preference-provider";
import { SessionBoundary } from "@/components/shell/session-boundary";
import { ProfileBoundary } from "@/components/shell/profile-boundary";
import { ShellModeProvider } from "@/components/shell/shell-mode-provider";
import { CommandPaletteProvider } from "@/components/shell/command-palette-provider";
import api from "@/lib/http-client";
import { clearAllAuthRateLimits, recordAuthFailure } from "@/lib/auth-rate-limit";

const mocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  const routerPush = vi.fn();
  const routerRefresh = vi.fn();
  return {
    routerReplace,
    routerPush,
    routerRefresh,
    router: {
      replace: routerReplace,
      push: routerPush,
      refresh: routerRefresh,
    },
    pathname: "/login",
    searchParams: new Map<string, string>(),
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => mocks.router,
  useSearchParams: () => ({
    get: (key: string) => mocks.searchParams.get(key) ?? null,
  }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: vi.fn().mockResolvedValue({ needs_onboarding: false }),
}));

vi.mock("@/lib/profile-context-api", () => ({
  getProfileContext: vi.fn().mockResolvedValue({}),
  activateOwnedProfile: vi.fn(),
}));

vi.mock("@/lib/visit-family", () => ({
  listFamilyNotifications: vi.fn().mockResolvedValue([]),
}));

function renderInShell(ui: ReactNode, pathname: string) {
  mocks.pathname = pathname;
  return render(
    <PreferenceProvider initialLanguage="vi">
      <SessionBoundary>
        <ProfileBoundary>
          <ShellModeProvider>
            <CommandPaletteProvider>
              <AppShell>{ui}</AppShell>
            </CommandPaletteProvider>
          </ShellModeProvider>
        </ProfileBoundary>
      </SessionBoundary>
    </PreferenceProvider>,
  );
}

beforeEach(() => {
  clearAllAuthRateLimits();
  vi.mocked(api.post).mockReset();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(api.post).mockReset();
  mocks.searchParams.clear();
  clearAllAuthRateLimits();
});

describe("Public Auth Pages — Spec v5 Section 6.2, 6.3, 6.4, 6.5 (PUBLIC_AUTH Shell)", () => {
  describe("AppShell Navigation Suppression on Public Auth Surfaces", () => {
    it("suppresses FloatingPrimaryDock and GlobalContextBar on /login", () => {
      renderInShell(<LoginPage />, "/login");
      expect(screen.queryByTestId("global-context-bar")).toBeNull();
      expect(screen.queryByTestId("floating-primary-dock")).toBeNull();
      expect(screen.queryByRole("navigation")).toBeNull();
    });

    it("suppresses FloatingPrimaryDock and GlobalContextBar on /register", () => {
      renderInShell(<RegisterPage />, "/register");
      expect(screen.queryByTestId("global-context-bar")).toBeNull();
      expect(screen.queryByTestId("floating-primary-dock")).toBeNull();
    });

    it("suppresses FloatingPrimaryDock and GlobalContextBar on /forgot-password", () => {
      renderInShell(<ForgotPasswordPage />, "/forgot-password");
      expect(screen.queryByTestId("global-context-bar")).toBeNull();
      expect(screen.queryByTestId("floating-primary-dock")).toBeNull();
    });

    it("suppresses FloatingPrimaryDock and GlobalContextBar on /auth/callback", () => {
      renderInShell(<AuthCallbackPage />, "/auth/callback");
      expect(screen.queryByTestId("global-context-bar")).toBeNull();
      expect(screen.queryByTestId("floating-primary-dock")).toBeNull();
    });
  });

  describe("Section 6.2 `/login` (Auth Focus Archetype)", () => {
    it("renders centered distraction-free layout with brand link, title, fields, and legal consent", () => {
      render(<LoginPage />);

      // Brand badge and back link
      expect(screen.getByText(/The Clara Care/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/");

      // Heading and form inputs
      expect(screen.getByRole("heading", { level: 1, name: /Đăng nhập/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Mật khẩu/i)).toBeInTheDocument();

      // Submit button
      expect(screen.getByRole("button", { name: /Đăng nhập/i })).toBeInTheDocument();

      // Secondary links
      expect(screen.getByRole("link", { name: /Tạo tài khoản/i })).toHaveAttribute("href", "/register");
      expect(screen.getByRole("link", { name: /Quên mật khẩu\?/i })).toHaveAttribute("href", "/forgot-password");

      // Clear legal consent disclaimer
      expect(screen.getByRole("link", { name: /Điều khoản/i })).toHaveAttribute("href", "/legal/terms");
      expect(screen.getByRole("link", { name: /Quyền riêng tư/i })).toHaveAttribute("href", "/legal/privacy");
      expect(screen.getByRole("link", { name: /Đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");
    });

    it("submits login credentials and redirects to default post-login path", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { role: "normal" },
      });

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "user@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), {
        target: { value: "Password123!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/login", {
          email: "user@example.com",
          password: "Password123!",
        });
        expect(mocks.routerReplace).toHaveBeenCalledWith("/home");
      });
    });

    it("transitions into OTP verification step when server requires OTP", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          otp_required: true,
          otp_delivery_status: "sent",
          otp_code_preview: "123456",
          otp_expires_in_seconds: 300,
        },
      });

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "otpuser@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), {
        target: { value: "Password123!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1, name: /Xác thực OTP/i })).toBeInTheDocument();
        expect(screen.getByLabelText(/Mã OTP/i)).toBeInTheDocument();
        expect(screen.getByText(/123456/)).toBeInTheDocument();
      });

      // Verify OTP step submit
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { role: "doctor" },
      });

      fireEvent.change(screen.getByLabelText(/Mã OTP/i), {
        target: { value: "123456" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Xác thực OTP/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/login-otp/verify", {
          email: "otpuser@example.com",
          otp_code: "123456",
        });
        expect(mocks.routerReplace).toHaveBeenCalledWith("/dashboard");
      });
    });

    it("displays error alert on invalid credentials", async () => {
      vi.mocked(api.post).mockRejectedValueOnce(new Error("Email hoặc mật khẩu không chính xác"));

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "wrong@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), {
        target: { value: "wrongpassword" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Email hoặc mật khẩu không chính xác");
      });
    });

    it("enforces progressive delay and countdown after repeated failed login attempts", async () => {
      vi.mocked(api.post)
        .mockRejectedValueOnce(new Error("Email hoặc mật khẩu không chính xác"))
        .mockRejectedValueOnce(new Error("Email hoặc mật khẩu không chính xác"));

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/Email/i);
      const passwordInput = screen.getByLabelText(/Mật khẩu/i);
      const submitButton = screen.getByRole("button", { name: /Đăng nhập/i });

      // First failure (0s delay)
      fireEvent.change(emailInput, { target: { value: "brute@example.com" } });
      fireEvent.change(passwordInput, { target: { value: "wrong1" } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      // Second failure (1s progressive cooling delay)
      fireEvent.change(passwordInput, { target: { value: "wrong2" } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(2);
        expect(screen.getByTestId("auth-rate-limit-banner")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Thử lại sau/i })).toBeDisabled();
      });
    });

    it("handles server 429 lockout by disabling submission and showing lockout countdown", async () => {
      const rateLimitError = new Error("Tạm khóa đăng nhập do quá nhiều lần thử sai. Thử lại sau 60s") as Error & {
        status?: number;
        retryAfter?: number;
      };
      rateLimitError.status = 429;
      rateLimitError.retryAfter = 60;

      vi.mocked(api.post).mockRejectedValueOnce(rateLimitError);

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "locked@example.com" } });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), { target: { value: "lockedpass" } });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByTestId("auth-rate-limit-banner")).toBeInTheDocument();
        expect(screen.getByText(/Tài khoản tạm thời bị khóa do nhiều lần thử không thành công/i)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Thử lại sau \(60s\)/i })).toBeDisabled();
        expect(screen.getByLabelText(/Email/i)).toBeDisabled();
        expect(screen.getByLabelText(/Mật khẩu/i)).toBeDisabled();
      });
    });

    it("requires security verification challenge after reaching failure threshold and blocks submission until solved", async () => {
      // Pre-seed 3 failures to trigger the CAPTCHA threshold
      recordAuthFailure("login", "captcha-user@example.com");
      recordAuthFailure("login", "captcha-user@example.com");
      recordAuthFailure("login", "captcha-user@example.com");

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/Email/i);
      fireEvent.change(emailInput, { target: { value: "captcha-user@example.com" } });

      // Security challenge must be rendered
      await waitFor(() => {
        expect(screen.getByTestId("auth-security-challenge")).toBeInTheDocument();
      });

      // Submit button is disabled while challenge is unsolved
      const submitBtn = screen.getByRole("button", { name: /(Đăng nhập|Thử lại sau)/i });
      expect(submitBtn).toBeDisabled();
    });

    it("mitigates OTP brute-force attacks with failure tracking and attempt warnings", async () => {
      // First setup: password step transitions to OTP
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          otp_required: true,
          otp_delivery_status: "sent",
          otp_expires_in_seconds: 300,
        },
      });

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "otpbrute@example.com" } });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), { target: { value: "CorrectPass123!" } });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1, name: /Xác thực OTP/i })).toBeInTheDocument();
      });

      // Fail OTP code attempt
      vi.mocked(api.post).mockRejectedValueOnce(new Error("Mã OTP không hợp lệ hoặc đã hết hạn"));

      fireEvent.change(screen.getByLabelText(/Mã OTP/i), { target: { value: "000000" } });
      fireEvent.click(screen.getByRole("button", { name: /Xác thực OTP/i }));

      await waitFor(() => {
        expect(screen.getByTestId("auth-otp-attempt-warning")).toBeInTheDocument();
        expect(screen.getByText(/Bạn đã nhập sai 1 lần/i)).toBeInTheDocument();
      });
    });

    it("resets rate limit and cooldown state upon successful authentication", async () => {
      // 1 failed attempt followed by success
      vi.mocked(api.post)
        .mockRejectedValueOnce(new Error("Sai mật khẩu"))
        .mockResolvedValueOnce({ data: { role: "normal" } });

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/Email/i);
      const passwordInput = screen.getByLabelText(/Mật khẩu/i);
      const submitButton = screen.getByRole("button", { name: /Đăng nhập/i });

      fireEvent.change(emailInput, { target: { value: "reset@example.com" } });
      fireEvent.change(passwordInput, { target: { value: "wrong" } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      fireEvent.change(passwordInput, { target: { value: "correct" } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(2);
        expect(mocks.routerReplace).toHaveBeenCalledWith("/home");
      });
    });
  });

  describe("Section 6.3 `/register` (Auth Focus Archetype)", () => {
    it("renders compact registration form with role selection and legal consent acknowledgement", () => {
      render(<RegisterPage />);

      expect(screen.getByRole("heading", { level: 1, name: /Tạo tài khoản/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Xác nhận mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Vai trò sử dụng/i)).toBeInTheDocument();
      expect(screen.getByRole("checkbox")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Tạo tài khoản/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Đăng nhập/i })).toHaveAttribute("href", "/login");
    });

    it("validates legal consent and password match before submission", async () => {
      render(<RegisterPage />);

      fireEvent.change(screen.getByLabelText(/Họ và tên/i), { target: { value: "Nguyen Van A" } });
      fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "new@example.com" } });
      fireEvent.change(screen.getByLabelText(/^Mật khẩu/i), { target: { value: "Password123" } });
      fireEvent.change(screen.getByLabelText(/Xác nhận mật khẩu/i), { target: { value: "Password123" } });

      // Click submit without legal consent
      fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản/i }));

      expect(screen.getByText(/Vui lòng xác nhận đã đọc Điều khoản, Quyền riêng tư và Đồng thuận y tế/i)).toBeInTheDocument();

      // Check legal consent but set mismatching password
      fireEvent.click(screen.getByRole("checkbox"));
      fireEvent.change(screen.getByLabelText(/Xác nhận mật khẩu/i), { target: { value: "Mismatch123" } });
      fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản/i }));

      expect(screen.getAllByText(/Mật khẩu xác nhận không khớp/i).length).toBeGreaterThan(0);
    });

    it("submits valid registration and displays verification notice", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          is_email_verified: false,
          verification_token_preview: "VERIFY-999",
          email_delivery_status: "sent",
        },
      });

      render(<RegisterPage />);

      fireEvent.change(screen.getByLabelText(/Họ và tên/i), { target: { value: "Nguyen Van A" } });
      fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "new@example.com" } });
      fireEvent.change(screen.getByLabelText(/^Mật khẩu/i), { target: { value: "Password123" } });
      fireEvent.change(screen.getByLabelText(/Xác nhận mật khẩu/i), { target: { value: "Password123" } });
      fireEvent.click(screen.getByRole("checkbox"));

      fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản/i }));

      await waitFor(() => {
        expect(screen.getByRole("status")).toHaveTextContent(/VERIFY-999/);
        expect(screen.getByRole("link", { name: /Đi đến trang xác thực email/i })).toHaveAttribute(
          "href",
          "/verify-email?email=new%40example.com",
        );
      });
    });
  });

  describe("Section 6.4 `/forgot-password` (Recovery Focus Archetype)", () => {
    it("renders centered recovery layout with email input, submit button, and back link", () => {
      render(<ForgotPasswordPage />);

      expect(screen.getByRole("heading", { level: 1, name: /Quên mật khẩu/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Gửi yêu cầu/i })).toBeInTheDocument();
      const backLinks = screen.getAllByRole("link", { name: /Quay lại đăng nhập/i });
      expect(backLinks.length).toBeGreaterThanOrEqual(1);
      expect(backLinks[0]).toHaveAttribute("href", "/login");
    });

    it("submits recovery request and surfaces reset token preview in dev mode", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          reset_token_preview: "RESET-TOKEN-1234",
          email_delivery_status: "sent",
        },
      });

      render(<ForgotPasswordPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "recovery@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Gửi yêu cầu/i }));

      await waitFor(() => {
        expect(screen.getByText(/RESET-TOKEN-1234/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Mở trang đặt lại/i })).toHaveAttribute(
          "href",
          "/reset-password?token=RESET-TOKEN-1234",
        );
      });
    });
  });

  describe("Section 6.5 & Public Auth `/auth/callback` (Public Auth / Callback Archetype)", () => {
    it("handles direct token params, establishes browser session, and redirects to destination", async () => {
      mocks.searchParams.set("token", "jwt-token-sample");
      mocks.searchParams.set("role", "doctor");
      mocks.searchParams.set("next", "/council");

      render(<AuthCallbackPage />);

      expect(screen.getByRole("heading", { name: /Xác thực thành công/i })).toBeInTheDocument();

      await waitFor(() => {
        expect(mocks.routerReplace).toHaveBeenCalledWith("/council");
      });
    });

    it("handles authorization code exchange and sets session", async () => {
      mocks.searchParams.set("code", "oauth-auth-code-123");
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { role: "normal" },
      });

      render(<AuthCallbackPage />);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/callback", { code: "oauth-auth-code-123" });
        expect(mocks.routerReplace).toHaveBeenCalledWith("/home");
      });
    });

    it("displays clear error alert and retry button when auth error parameter is present", () => {
      mocks.searchParams.set("error", "access_denied");
      mocks.searchParams.set("error_description", "User rejected authorization");

      render(<AuthCallbackPage />);

      expect(screen.getByRole("alert")).toHaveTextContent("access_denied");
      expect(screen.getByRole("button", { name: /Quay lại đăng nhập/i })).toBeInTheDocument();
    });
  });

  describe("Section 6.5 `/reset-password` & Section 6.6 `/verify-email`", () => {
    it("renders ResetPasswordPage with token and new password inputs", () => {
      render(<ResetPasswordPage />);
      expect(screen.getByRole("heading", { level: 1, name: /Đặt lại mật khẩu/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Mã đặt lại mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Mật khẩu mới/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Đặt lại mật khẩu/i })).toBeInTheDocument();
    });

    it("validates password format before submitting in ResetPasswordPage", async () => {
      render(<ResetPasswordPage />);

      fireEvent.change(screen.getByLabelText(/Mã đặt lại mật khẩu/i), {
        target: { value: "RESET-TOKEN-123" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu mới/i), {
        target: { value: "short" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đặt lại mật khẩu/i }));

      expect(screen.getByText(/Mật khẩu phải có ít nhất 8 ký tự/i)).toBeInTheDocument();
      expect(api.post).not.toHaveBeenCalled();
    });

    it("submits valid reset password and displays success message with login link", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { message: "Password updated successfully" },
      });

      render(<ResetPasswordPage />);

      fireEvent.change(screen.getByLabelText(/Mã đặt lại mật khẩu/i), {
        target: { value: "RESET-TOKEN-123" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu mới/i), {
        target: { value: "ValidPass123!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đặt lại mật khẩu/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/reset-password", {
          token: "RESET-TOKEN-123",
          new_password: "ValidPass123!",
        });
        expect(screen.getByRole("status")).toHaveTextContent(/Đặt lại mật khẩu thành công/i);
        expect(screen.getByRole("link", { name: /Đi đến đăng nhập/i })).toHaveAttribute("href", "/login");
      });
    });

    it("renders VerifyEmailPage with token input and resend form", () => {
      render(<VerifyEmailPage />);
      expect(screen.getByRole("heading", { level: 1, name: /Xác thực email/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Mã xác thực/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Xác thực email/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Email tài khoản/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Gửi lại mã xác thực/i })).toBeInTheDocument();
    });

    it("submits email verification and displays success notification", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { is_email_verified: true },
      });

      render(<VerifyEmailPage />);

      fireEvent.change(screen.getByLabelText(/Mã xác thực/i), {
        target: { value: "VERIFY-TOKEN-789" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Xác thực email/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/verify-email", {
          token: "VERIFY-TOKEN-789",
        });
        expect(screen.getByRole("status")).toHaveTextContent(/Xác thực email thành công/i);
      });
    });

    it("resends email verification and pre-fills preview token in dev mode", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          verification_token_preview: "AUTO-FILLED-PREVIEW-123",
          email_delivery_status: "sent",
        },
      });

      render(<VerifyEmailPage />);

      fireEvent.change(screen.getByLabelText(/Email tài khoản/i), {
        target: { value: "user@example.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Gửi lại mã xác thực/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/resend-verification", {
          email: "user@example.com",
        });
        expect(screen.getByLabelText(/Mã xác thực/i)).toHaveValue("AUTO-FILLED-PREVIEW-123");
        expect(screen.getByRole("status")).toBeInTheDocument();
      });
    });
  });
});
