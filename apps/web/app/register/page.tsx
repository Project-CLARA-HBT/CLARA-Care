"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import AuthFormShell from "@/components/auth-form-shell";
import AuthField from "@/components/auth/auth-field";
import AuthFeedback from "@/components/auth/auth-feedback";

type UserRole = "normal" | "researcher" | "doctor";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("normal");
  const [acceptedLegal, setAcceptedLegal] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!acceptedLegal) {
      setError("Vui lòng xác nhận đã đọc Điều khoản, Quyền riêng tư và Đồng thuận y tế trước khi tạo tài khoản.");
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
      setError(cause instanceof Error ? cause.message : "Không thể tạo tài khoản.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthFormShell title="Tạo tài khoản" subtitle="Khởi tạo tài khoản CLARA và chọn vai trò phù hợp nhu cầu của bạn.">
      <form className="space-y-4" onSubmit={onSubmit}>
        <AuthField
          id="register-full-name"
          label="Họ và tên"
          value={fullName}
          onChange={setFullName}
          placeholder="Nguyễn Văn A"
          required
        />
        <AuthField
          id="register-email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="name@example.com"
          required
        />
        <AuthField
          id="register-password"
          label="Mật khẩu"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="Tối thiểu 8 ký tự"
          minLength={8}
          required
        />

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-slate-800" htmlFor="register-role">
            Vai trò sử dụng
          </label>
          <select
            id="register-role"
            className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
          >
            <option value="normal">Người dùng cá nhân</option>
            <option value="researcher">Nhà nghiên cứu</option>
            <option value="doctor">Bác sĩ</option>
          </select>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-300 bg-slate-50 p-3">
          <input
            type="checkbox"
            checked={acceptedLegal}
            onChange={(event) => setAcceptedLegal(event.target.checked)}
            className="mt-1 h-5 w-5 rounded border-slate-300"
          />
          <span className="text-sm leading-6 text-slate-700">
            Tôi đồng ý với{" "}
            <Link href="/legal/terms" className="font-semibold text-blue-700 hover:underline">
              Điều khoản sử dụng
            </Link>
            ,{" "}
            <Link href="/legal/privacy" className="font-semibold text-blue-700 hover:underline">
              Chính sách quyền riêng tư
            </Link>{" "}
            và{" "}
            <Link href="/legal/consent" className="font-semibold text-blue-700 hover:underline">
              Đồng thuận sử dụng y tế
            </Link>
            .
          </span>
        </label>

        <AuthFeedback notice={notice} error={error} />

        {notice.includes("xác thực") ? (
          <Link href={`/verify-email?email=${encodeURIComponent(email)}`} className="text-sm font-medium text-blue-700 hover:underline">
            Đi đến trang xác thực email
          </Link>
        ) : null}

        <button className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-70" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Đang xử lý..." : "Tạo tài khoản"}
        </button>

        <p className="text-sm text-slate-600">
          Đã có tài khoản?{" "}
          <Link href="/login" className="font-medium text-blue-700 hover:underline">
            Đăng nhập
          </Link>
        </p>
      </form>
    </AuthFormShell>
  );
}
