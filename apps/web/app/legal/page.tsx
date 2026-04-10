import Link from "next/link";
import type { Metadata } from "next";
import {
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

export const metadata: Metadata = {
  title: "Trung tâm pháp lý | The Clara Care",
  description:
    "Tổng hợp tài liệu pháp lý The Clara Care: Privacy Policy, Terms of Service, Medical Consent và Cookie Policy.",
};

const LEGAL_ITEMS = [
  {
    href: "/legal/privacy",
    shortLabel: "Privacy",
    title: "Chính sách quyền riêng tư",
    detail:
      "Giải thích dữ liệu nào được thu thập, mục đích sử dụng, thời gian lưu trữ, quyền chủ thể dữ liệu và cơ chế phản hồi yêu cầu.",
  },
  {
    href: "/legal/terms",
    shortLabel: "Terms",
    title: "Điều khoản sử dụng",
    detail:
      "Quy định quyền và nghĩa vụ khi dùng The Clara Care, phạm vi sử dụng hợp lệ, giới hạn trách nhiệm và điều kiện tạm ngưng tài khoản.",
  },
  {
    href: "/legal/consent",
    shortLabel: "Consent",
    title: "Đồng thuận y tế",
    detail:
      "Điều khoản bắt buộc cho tính năng có tác động lâm sàng. Nêu rõ vai trò hỗ trợ của AI và yêu cầu xác nhận chuyên môn trước quyết định điều trị.",
  },
  {
    href: "/legal/cookies",
    shortLabel: "Cookies",
    title: "Chính sách cookie",
    detail:
      "Mô tả cookie cần thiết, cookie chức năng, cách quản lý tại trình duyệt và ảnh hưởng khi tắt cookie quan trọng.",
  },
] as const;

const OPERATING_PRINCIPLES = [
  "Mọi module cùng dùng một chuẩn chính sách The Clara Care.",
  "Tài liệu pháp lý được version hóa để audit nội bộ.",
  "Chính sách ưu tiên tính an toàn lâm sàng trước tốc độ phản hồi.",
  "Mọi thay đổi điều khoản đều được công bố tập trung tại Policy Center.",
] as const;

export default function LegalHubPage() {
  return (
    <main className="chrome-shell min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-10 pt-8 sm:px-6 lg:px-8">
        <section className="chrome-panel rounded-[1.9rem] border border-[color:var(--shell-border)] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">The Clara Care · Policy Center</p>
              <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-[2rem]">Trung tâm pháp lý</h1>
              <p className="mt-3 max-w-[84ch] text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                Không gian tập trung toàn bộ chính sách pháp lý của The Clara Care. Đây là nguồn tham chiếu chính thức cho người dùng,
                quản trị viên và đội vận hành khi cần xác định quyền, nghĩa vụ và phạm vi sử dụng hệ thống.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-bold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
              >
                Về trang chủ
              </Link>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full border border-cyan-400/35 bg-cyan-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300">
              Branding: The Clara Care
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Policy version: {LEGAL_POLICY_VERSION}
            </span>
            <span className="rounded-full border border-emerald-400/35 bg-emerald-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-300">
              Cập nhật: {LEGAL_UPDATED_AT}
            </span>
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          {LEGAL_ITEMS.map((item) => (
            <article key={item.href} className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5 sm:p-6">
              <p className="text-[11px] font-black uppercase tracking-[0.14em] text-[var(--text-brand)]">{item.shortLabel}</p>
              <h2 className="mt-2 text-lg font-extrabold tracking-tight text-[var(--text-primary)] sm:text-xl">{item.title}</h2>
              <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{item.detail}</p>
              <Link href={item.href} className="mt-4 inline-flex min-h-[44px] items-center rounded-xl bg-[var(--text-brand)] px-4 py-2 text-sm font-bold text-white transition hover:opacity-90">
                Xem chính sách
              </Link>
            </article>
          ))}
        </section>

        <section className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5 sm:p-6">
          <h2 className="text-lg font-extrabold tracking-tight text-[var(--text-primary)] sm:text-xl">Nguyên tắc vận hành chính sách</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {OPERATING_PRINCIPLES.map((item) => (
              <div key={item} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-3 text-sm font-semibold leading-6 text-[var(--text-secondary)]">
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5 sm:p-6">
          <h2 className="text-lg font-extrabold tracking-tight text-[var(--text-primary)] sm:text-xl">Thông tin chủ thể vận hành</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
            <li>
              <span className="font-bold">Tên chủ thể:</span> {LEGAL_OPERATOR_NAME}
            </li>
            <li>
              <span className="font-bold">Domain chính thức:</span> https://{LEGAL_PRIMARY_DOMAIN}
            </li>
            <li>
              <span className="font-bold">Số điện thoại liên lạc:</span> {LEGAL_CONTACT_PHONE}
            </li>
          </ul>
        </section>
      </div>
    </main>
  );
}
