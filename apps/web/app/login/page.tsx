"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { setAccessToken, setRefreshToken, setRole as setStoredRole } from "@/lib/auth-store";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { resolvePostLoginPath } from "@/lib/navigation.config";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState<string | null>(null);
  const [otpDeliveryStatus, setOtpDeliveryStatus] = useState<string | null>(null);
  const [otpPreviewCode, setOtpPreviewCode] = useState<string | null>(null);
  const [otpExpiresInSeconds, setOtpExpiresInSeconds] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isOtpStep = Boolean(otpEmail);
  const shouldShowVerifyLink = error.toLowerCase().includes("xác thực");

  const resetOtpStep = () => {
    setOtpCode("");
    setOtpEmail(null);
    setOtpDeliveryStatus(null);
    setOtpPreviewCode(null);
    setOtpExpiresInSeconds(null);
  };

  const finishLogin = (payload: {
    access_token?: string;
    refresh_token?: string;
    role?: "normal" | "researcher" | "doctor" | "admin";
  }) => {
    const accessToken = payload.access_token;
    const refreshToken = payload.refresh_token;
    const serverRole = payload.role;

    if (!accessToken) {
      throw new Error("Phản hồi đăng nhập thiếu access token.");
    }

    const nextRole = serverRole ?? "normal";
    setAccessToken(accessToken);
    if (refreshToken) {
      setRefreshToken(refreshToken);
    }
    setStoredRole(nextRole);
    const targetPath = resolvePostLoginPath({
      nextPath:
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("next")
          : null,
      role: nextRole
    });
    router.replace(targetPath);
    router.refresh();
    if (typeof window !== "undefined") {
      window.setTimeout(() => {
        if (window.location.pathname === "/login") {
          window.location.assign(targetPath);
        }
      }, 350);
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      if (isOtpStep) {
        const normalizedEmail = (otpEmail ?? email).trim();
        const normalizedOtpCode = otpCode.trim();
        const response = await api.post("/auth/login-otp/verify", {
          email: normalizedEmail,
          otp_code: normalizedOtpCode,
        });
        finishLogin(response.data ?? {});
      } else {
        const normalizedEmail = email.trim();
        const response = await api.post("/auth/login", { email: normalizedEmail, password });
        const otpRequired = Boolean(response.data?.otp_required);
        if (otpRequired) {
          setOtpEmail(normalizedEmail);
          setOtpCode("");
          setOtpDeliveryStatus(
            typeof response.data?.otp_delivery_status === "string"
              ? response.data.otp_delivery_status
              : null
          );
          setOtpPreviewCode(
            typeof response.data?.otp_code_preview === "string"
              ? response.data.otp_code_preview
              : null
          );
          setOtpExpiresInSeconds(
            typeof response.data?.otp_expires_in_seconds === "number"
              ? response.data.otp_expires_in_seconds
              : null
          );
          return;
        }
        finishLogin(response.data ?? {});
      }
    } catch (submitError) {
      const fallbackMessage = "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.";
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">The Clara Care</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          {isOtpStep ? "Xác thực OTP" : "Đăng nhập"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {isOtpStep
            ? "Nhập mã OTP vừa gửi để hoàn tất đăng nhập."
            : "Đăng nhập để truy cập CLARA Chat, Self-Med và các công cụ chuyên môn."}
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          {!isOtpStep ? (
            <>
              <Field
                id="login-email"
                label="Email"
                type="email"
                inputMode="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@example.com"
                required
              />
              <Field
                id="login-password"
                label="Mật khẩu"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Nhập mật khẩu"
                required
              />
            </>
          ) : (
            <>
              <Field
                id="login-otp"
                label="Mã OTP"
                type="text"
                value={otpCode}
                onChange={(event) => setOtpCode(event.target.value)}
                placeholder="Nhập mã OTP 6 số"
                required
                minLength={6}
                maxLength={6}
                autoComplete="one-time-code"
              />
              <p className="text-xs text-[var(--text-muted)]">
                OTP đã gửi tới:{" "}
                <span className="font-semibold text-[var(--text-primary)]">{otpEmail}</span>
              </p>
              {otpDeliveryStatus ? (
                <p className="text-xs text-[var(--text-muted)]">
                  Trạng thái gửi OTP: {otpDeliveryStatus}
                </p>
              ) : null}
              {otpExpiresInSeconds ? (
                <p className="text-xs text-[var(--text-muted)]">
                  Mã có hiệu lực khoảng {Math.max(1, Math.round(otpExpiresInSeconds / 60))} phút.
                </p>
              ) : null}
              {otpPreviewCode ? (
                <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-xs text-[var(--status-warn-text)]">
                  OTP preview (dev): <span className="font-bold">{otpPreviewCode}</span>
                </p>
              ) : null}
            </>
          )}

          {error ? (
            <p
              role="alert"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]"
            >
              {error}
            </p>
          ) : null}

          {!isOtpStep && shouldShowVerifyLink ? (
            <Link
              href={`/verify-email?email=${encodeURIComponent(email)}`}
              className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
            >
              Tài khoản chưa xác thực? Đi đến trang xác thực email
            </Link>
          ) : null}

          <Button
            type="submit"
            block
            loading={isSubmitting}
            loadingLabel={isOtpStep ? "Đang xác thực..." : "Đang đăng nhập..."}
          >
            {isOtpStep ? "Xác thực OTP" : "Đăng nhập"}
          </Button>

          {!isOtpStep ? (
            <div className="flex justify-between text-sm">
              <Link
                href="/register"
                className="focus-ring rounded text-[var(--text-brand)] hover:underline"
              >
                Tạo tài khoản
              </Link>
              <Link
                href="/forgot-password"
                className="focus-ring rounded text-[var(--text-secondary)] hover:underline"
              >
                Quên mật khẩu?
              </Link>
            </div>
          ) : (
            <Button type="button" variant="secondary" block onClick={resetOtpStep}>
              Quay lại đăng nhập bằng mật khẩu
            </Button>
          )}

          <p className="text-xs leading-6 text-[var(--text-muted)]">
            Bằng việc tiếp tục, bạn xác nhận đã đọc{" "}
            <Link
              href="/legal/terms"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              Điều khoản
            </Link>
            ,{" "}
            <Link
              href="/legal/privacy"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              Quyền riêng tư
            </Link>{" "}
            và{" "}
            <Link
              href="/legal/consent"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              Đồng thuận y tế
            </Link>
            .
          </p>
        </form>
      </SurfaceCard>
    </main>
  );
}
