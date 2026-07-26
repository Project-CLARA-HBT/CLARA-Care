"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";

type UserRole = "normal" | "researcher" | "doctor";

function normalizeRegisterErrorMessage(message: string): string {
  const normalized = message.trim();
  const lowered = normalized.toLowerCase();
  if (!normalized) {
    return "Chưa thể tạo tài khoản. Vui lòng thử lại sau ít phút.";
  }
  if (
    lowered.includes("internal server error") ||
    lowered.includes("request failed with status code 500") ||
    lowered.includes("status code: 500") ||
    lowered.includes("gateway") ||
    lowered.includes("timeout")
  ) {
    return "Chưa thể tạo tài khoản lúc này. Vui lòng thử lại sau ít phút hoặc kiểm tra kết nối.";
  }
  return normalized;
}

function getPasswordValidationError(password: string): string | null {
  if (password.length < 8) {
    return "Mật khẩu phải có ít nhất 8 ký tự.";
  }
  if (password !== password.trim()) {
    return "Mật khẩu không được chứa khoảng trắng ở đầu/cuối.";
  }
  const hasAlpha = /[A-Za-z]/.test(password);
  const hasDigit = /\d/.test(password);
  if (!hasAlpha || !hasDigit) {
    return "Mật khẩu phải có ít nhất 1 chữ cái và 1 chữ số.";
  }
  return null;
}

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>("normal");
  const [acceptedLegal, setAcceptedLegal] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const passwordValidationError = getPasswordValidationError(password);
  const confirmPasswordError =
    confirmPassword && password !== confirmPassword ? "Mật khẩu xác nhận không khớp." : "";

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!acceptedLegal) {
      setError("Vui lòng xác nhận đã đọc Điều khoản, Quyền riêng tư và Đồng thuận y tế trước khi tạo tài khoản.");
      return;
    }
    if (passwordValidationError) {
      setError(passwordValidationError);
      return;
    }
    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await api.post("/auth/register", {
        full_name: fullName,
        email,
        password,
        role,
        accepted_terms: true,
        accepted_privacy: true,
        accepted_medical_consent: true,
      });
      const tokenPreview = response.data?.verification_token_preview as string | undefined;
      const isVerified = Boolean(response.data?.is_email_verified);
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";

      if (isVerified) {
        setNotice("Đăng ký thành công. Bạn có thể đăng nhập ngay.");
        setTimeout(() => router.push("/login"), 1000);
      } else if (tokenPreview) {
        setNotice(`Đăng ký thành công. Mã xác thực (dev): ${tokenPreview}`);
      } else if (deliveryStatus === "sent") {
        setNotice("Đăng ký thành công. Hệ thống đã gửi email xác thực, vui lòng kiểm tra hộp thư.");
      } else {
        setNotice("Đăng ký thành công. Vui lòng xác thực email trước khi đăng nhập.");
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? normalizeRegisterErrorMessage(cause.message)
          : "Chưa thể tạo tài khoản. Vui lòng thử lại sau ít phút."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">The Clara Care</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          Tạo tài khoản
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          Khởi tạo tài khoản CLARA và chọn vai trò phù hợp nhu cầu của bạn.
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Field
            id="register-full-name"
            label="Họ và tên"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Nguyễn Văn A"
            required
          />
          <Field
            id="register-email"
            label="Email"
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@example.com"
            required
          />
          <div className="space-y-1.5">
            <Field
              id="register-password"
              label="Mật khẩu"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Tối thiểu 8 ký tự"
              autoComplete="new-password"
              minLength={8}
              required
            />
            <p className="text-sm text-[var(--text-secondary)]">
              Ít nhất 8 ký tự, gồm tối thiểu 1 chữ cái, 1 chữ số và không có khoảng trắng ở đầu/cuối.
            </p>
          </div>
          <div className="space-y-1.5">
            <Field
              id="register-confirm-password"
              label="Xác nhận mật khẩu"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Nhập lại mật khẩu"
              autoComplete="new-password"
              minLength={8}
              required
              aria-invalid={confirmPasswordError ? true : undefined}
            />
            {confirmPasswordError ? (
              <p role="alert" className="text-sm font-medium text-[var(--status-danger-text)]">
                {confirmPasswordError}
              </p>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">
                Nhập lại mật khẩu để tránh gõ nhầm.
              </p>
            )}
          </div>

          <Select
            id="register-role"
            label="Vai trò sử dụng"
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
          >
            <option value="normal">Người dùng cá nhân</option>
            <option value="researcher">Nhà nghiên cứu</option>
            <option value="doctor">Bác sĩ</option>
          </Select>

          <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
            <input
              type="checkbox"
              checked={acceptedLegal}
              onChange={(event) => setAcceptedLegal(event.target.checked)}
              className="focus-ring mt-1 h-5 w-5 rounded border-[color:var(--shell-border-strong)]"
            />
            <span className="text-sm leading-6 text-[var(--text-secondary)]">
              Tôi đồng ý với{" "}
              <Link
                href="/legal/terms"
                className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
              >
                Điều khoản sử dụng
              </Link>
              ,{" "}
              <Link
                href="/legal/privacy"
                className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
              >
                Chính sách quyền riêng tư
              </Link>{" "}
              và{" "}
              <Link
                href="/legal/consent"
                className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
              >
                Đồng thuận sử dụng y tế
              </Link>
              .
            </span>
          </label>

          {notice ? (
            <p
              role="status"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-ok-text)]"
            >
              {notice}
            </p>
          ) : null}
          {error ? (
            <p
              role="alert"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]"
            >
              {error}
            </p>
          ) : null}

          {notice.includes("xác thực") ? (
            <Link
              href={`/verify-email?email=${encodeURIComponent(email)}`}
              className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
            >
              Đi đến trang xác thực email
            </Link>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel="Đang xử lý...">
            Tạo tài khoản
          </Button>

          <p className="text-sm text-[var(--text-secondary)]">
            Đã có tài khoản?{" "}
            <Link
              href="/login"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              Đăng nhập
            </Link>
          </p>
        </form>
      </SurfaceCard>
    </main>
  );
}
