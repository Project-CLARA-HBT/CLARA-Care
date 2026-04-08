import LegalPageShell from "@/components/legal/legal-page-shell";
import { LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách cookie | Project CLARA",
  description: "Mô tả cách Project CLARA sử dụng cookie để vận hành và bảo mật phiên người dùng.",
};

export default function CookiePolicyPage() {
  return (
    <LegalPageShell
      title="Chính sách cookie"
      summary="Cookie giúp CLARA duy trì phiên đăng nhập, ghi nhớ tuỳ chọn giao diện và cải thiện trải nghiệm sử dụng."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">1. Cookie là gì</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Cookie là các tệp nhỏ được lưu trên trình duyệt để nhận diện phiên làm việc và ghi nhớ một số tuỳ chọn của bạn.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">2. Cookie được sử dụng trong CLARA</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
          <li>Cookie cần thiết: duy trì đăng nhập, bảo mật phiên và chống truy cập trái phép.</li>
          <li>Cookie chức năng: ghi nhớ tuỳ chọn hiển thị (ví dụ light/dark mode) và trải nghiệm người dùng.</li>
        </ul>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">3. Cách quản lý cookie</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Bạn có thể xoá hoặc chặn cookie trong phần cài đặt trình duyệt. Việc tắt cookie cần thiết có thể khiến một số
          chức năng của CLARA hoạt động không ổn định.
        </p>
      </article>
    </LegalPageShell>
  );
}
