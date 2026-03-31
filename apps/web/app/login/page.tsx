"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { setAccessToken, setRefreshToken, setRole as setStoredRole } from "@/lib/auth-store";
import AuthFormShell from "@/components/auth-form-shell";
import AuthField from "@/components/auth/auth-field";
import AuthFeedback from "@/components/auth/auth-feedback";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const shouldShowVerifyLink = error.toLowerCase().includes("xác thực");

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const response = await api.post("/auth/login", { email, password });
      const accessToken = response.data?.access_token as string | undefined;
      const refreshToken = response.data?.refresh_token as string | undefined;
      const serverRole = response.data?.role as "normal" | "researcher" | "doctor" | "admin" | undefined;

      if (!accessToken || !refreshToken) {
        throw new Error("Phản hồi đăng nhập thiếu token.");
      }

      const nextRole = serverRole ?? "normal";
      setAccessToken(accessToken);
      setRefreshToken(refreshToken);
      setStoredRole(nextRole);
      const nextPath =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("next")
          : null;
      if (nextPath && nextPath.startsWith("/")) {
        router.push(nextPath);
      } else {
        router.push("/dashboard");
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
    <AuthFormShell title="Đăng nhập" subtitle="Đăng nhập để truy cập CLARA Research, Self-Med và các công cụ chuyên môn.">
      <form className="space-y-4" onSubmit={onSubmit}>
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

        <AuthFeedback error={error} />

        {shouldShowVerifyLink ? (
          <Link href={`/verify-email?email=${encodeURIComponent(email)}`} className="text-sm font-medium text-blue-700 hover:underline">
            Tài khoản chưa xác thực? Đi đến trang xác thực email
          </Link>
        ) : null}

        <button className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-70" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>

        <div className="flex justify-between text-sm">
          <Link href="/register" className="text-blue-700 hover:underline">
            Tạo tài khoản
          </Link>
          <Link href="/forgot-password" className="text-slate-600 hover:underline">
            Quên mật khẩu?
          </Link>
        </div>
      </form>
    </AuthFormShell>
  );
}
