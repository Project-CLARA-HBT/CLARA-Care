"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { setAccessToken, setRefreshToken, setRole as setStoredRole } from "@/lib/auth-store";
import AuthFormShell from "@/components/auth-form-shell";
import AuthField from "@/components/auth/auth-field";
import AuthFeedback from "@/components/auth/auth-feedback";
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
    <AuthFormShell
      title={isOtpStep ? "Xác thực OTP" : "Đăng nhập"}
      subtitle={
        isOtpStep
          ? "Nhập mã OTP vừa gửi để hoàn tất đăng nhập."
          : "Đăng nhập để truy cập CLARA Chat, Self-Med và các công cụ chuyên môn."
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {!isOtpStep ? (
          <>
            <AuthField
              id="login-email"
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="name@example.com"
              required
            />
            <AuthField
              id="login-password"
              label="Mật khẩu"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="Nhập mật khẩu"
              required
            />
          </>
        ) : (
          <>
            <AuthField
              id="login-otp"
              label="Mã OTP"
              type="text"
              value={otpCode}
              onChange={setOtpCode}
              placeholder="Nhập mã OTP 6 số"
              required
              minLength={6}
              maxLength={6}
              autoComplete="one-time-code"
            />
            <p className="text-xs text-slate-500">
              OTP đã gửi tới: <span className="font-semibold text-slate-700">{otpEmail}</span>
            </p>
            {otpDeliveryStatus ? (
              <p className="text-xs text-slate-500">Trạng thái gửi OTP: {otpDeliveryStatus}</p>
            ) : null}
            {otpExpiresInSeconds ? (
              <p className="text-xs text-slate-500">
                Mã có hiệu lực khoảng {Math.max(1, Math.round(otpExpiresInSeconds / 60))} phút.
              </p>
            ) : null}
            {otpPreviewCode ? (
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                OTP preview (dev): <span className="font-bold">{otpPreviewCode}</span>
              </p>
            ) : null}
          </>
        )}

        <AuthFeedback error={error} />

        {!isOtpStep && shouldShowVerifyLink ? (
          <Link href={`/verify-email?email=${encodeURIComponent(email)}`} className="text-sm font-medium text-blue-700 hover:underline">
            Tài khoản chưa xác thực? Đi đến trang xác thực email
          </Link>
        ) : null}

        <button className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-70" disabled={isSubmitting} type="submit">
          {isSubmitting ? (isOtpStep ? "Đang xác thực..." : "Đang đăng nhập...") : isOtpStep ? "Xác thực OTP" : "Đăng nhập"}
        </button>

        {!isOtpStep ? (
          <div className="flex justify-between text-sm">
            <Link href="/register" className="text-blue-700 hover:underline">
              Tạo tài khoản
            </Link>
            <Link href="/forgot-password" className="text-slate-600 hover:underline">
              Quên mật khẩu?
            </Link>
          </div>
        ) : (
          <button
            type="button"
            onClick={resetOtpStep}
            className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Quay lại đăng nhập bằng mật khẩu
          </button>
        )}

        <p className="text-xs leading-6 text-slate-500">
          Bằng việc tiếp tục, bạn xác nhận đã đọc{" "}
          <Link href="/legal/terms" className="font-medium text-blue-700 hover:underline">
            Điều khoản
          </Link>
          ,{" "}
          <Link href="/legal/privacy" className="font-medium text-blue-700 hover:underline">
            Quyền riêng tư
          </Link>{" "}
          và{" "}
          <Link href="/legal/consent" className="font-medium text-blue-700 hover:underline">
            Đồng thuận y tế
          </Link>
          .
        </p>
      </form>
    </AuthFormShell>
  );
}
