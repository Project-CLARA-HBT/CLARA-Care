"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token") ?? "";
    if (tokenFromUrl) setToken(tokenFromUrl);
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setNotice("");
    setError("");
    try {
      await api.post("/auth/reset-password", { token, new_password: newPassword });
      setNotice("Đặt lại mật khẩu thành công. Bạn có thể đăng nhập lại.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đặt lại mật khẩu.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">The Clara Care</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          Đặt lại mật khẩu
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          Nhập mã đặt lại và mật khẩu mới để tiếp tục sử dụng tài khoản.
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Textarea
            id="reset-token"
            label="Mã đặt lại mật khẩu"
            rows={3}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Dán mã đặt lại tại đây"
            required
          />

          <Field
            id="reset-new-password"
            label="Mật khẩu mới"
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="Tối thiểu 8 ký tự"
            minLength={8}
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

          <Button type="submit" block loading={isSubmitting} loadingLabel="Đang xử lý...">
            Đặt lại mật khẩu
          </Button>
        </form>
      </SurfaceCard>
    </main>
  );
}
