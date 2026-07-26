"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tokenPreview, setTokenPreview] = useState("");

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setNotice("");
    setTokenPreview("");
    try {
      const response = await api.post("/auth/forgot-password", { email });
      const token = response.data?.reset_token_preview as string | undefined;
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";
      if (token) {
        setTokenPreview(token);
        setNotice("Yêu cầu đặt lại mật khẩu đã được tạo (chế độ dev).");
      } else if (deliveryStatus === "sent") {
        setNotice("Hệ thống đã gửi email đặt lại mật khẩu. Vui lòng kiểm tra hộp thư.");
      } else {
        setNotice("Nếu email tồn tại, hệ thống đã gửi hướng dẫn đặt lại mật khẩu.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xử lý yêu cầu.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">The Clara Care</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          Quên mật khẩu
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          Nhập email tài khoản để nhận hướng dẫn đặt lại mật khẩu.
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Field
            id="forgot-email"
            label="Email"
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@example.com"
            required
          />

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

          {tokenPreview ? (
            <p className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              Mã reset (dev): <code className="font-mono text-xs">{tokenPreview}</code>{" "}
              <Link
                href={`/reset-password?token=${encodeURIComponent(tokenPreview)}`}
                className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
              >
                Mở trang đặt lại
              </Link>
            </p>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel="Đang gửi...">
            Gửi yêu cầu
          </Button>

          <Link
            href="/login"
            className="focus-ring inline-block rounded text-sm text-[var(--text-secondary)] hover:underline"
          >
            Quay lại đăng nhập
          </Link>
        </form>
      </SurfaceCard>
    </main>
  );
}
