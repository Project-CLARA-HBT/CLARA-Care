"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";

export default function VerifyEmailPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token") ?? "";
    const emailFromUrl = params.get("email") ?? "";
    if (tokenFromUrl) setToken(tokenFromUrl);
    if (emailFromUrl) setEmail(emailFromUrl);
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setNotice("");
    setError("");
    setIsSubmitting(true);
    try {
      await api.post("/auth/verify-email", { token });
      setNotice("Xác thực email thành công.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể xác thực email.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const onResend = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice("");
    setError("");
    setIsResending(true);
    try {
      const response = await api.post("/auth/resend-verification", { email });
      const tokenPreview = response.data?.verification_token_preview as string | undefined;
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";
      if (tokenPreview) {
        setToken(tokenPreview);
        setNotice("Đã tạo mã xác thực mới (chế độ dev). Vui lòng bấm xác thực ngay.");
      } else if (deliveryStatus === "sent") {
        setNotice("Đã gửi lại email xác thực. Vui lòng kiểm tra hộp thư.");
      } else {
        setNotice("Nếu tài khoản chưa xác thực, hệ thống đã xử lý yêu cầu gửi lại.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể gửi lại email xác thực.");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">The Clara Care</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          Xác thực email
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          Nhập mã xác thực hoặc yêu cầu gửi lại mã để kích hoạt tài khoản.
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Textarea
            id="verify-token"
            label="Mã xác thực"
            rows={3}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Dán mã xác thực tại đây"
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

          {notice ? (
            <Link
              href="/login"
              className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
            >
              Đi đến đăng nhập
            </Link>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel="Đang xác thực...">
            Xác thực email
          </Button>
        </form>

        <div className="my-6 border-t border-[color:var(--shell-border)]" />

        <form className="space-y-4" onSubmit={onResend}>
          <Field
            id="verify-email"
            label="Email tài khoản"
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@example.com"
            required
          />
          <Button
            type="submit"
            variant="secondary"
            block
            loading={isResending}
            loadingLabel="Đang gửi lại..."
          >
            Gửi lại mã xác thực
          </Button>
        </form>
      </SurfaceCard>
    </main>
  );
}
