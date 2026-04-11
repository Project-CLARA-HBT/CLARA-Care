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
    shortLabel: "Riêng tư",
    title: "Chính sách quyền riêng tư",
    detail:
      "Nêu rõ dữ liệu tài khoản, dữ liệu vận hành và dữ liệu lâm sàng tham khảo được thu thập như thế nào, dùng vào mục đích gì và được bảo vệ ra sao.",
  },
  {
    href: "/legal/terms",
    shortLabel: "Điều khoản",
    title: "Điều khoản sử dụng",
    detail:
      "Xác định phạm vi sử dụng hợp lệ cho các module CLARA, trách nhiệm người dùng, giới hạn của AI và cơ chế tạm ngưng/chấm dứt truy cập.",
  },
  {
    href: "/legal/consent",
    shortLabel: "Đồng thuận",
    title: "Đồng thuận y tế",
    detail:
      "Điều kiện bắt buộc trước khi dùng các luồng có rủi ro lâm sàng, đặc biệt Self-Med và CareGuard, với cơ chế version hóa để truy vết.",
  },
  {
    href: "/legal/cookies",
    shortLabel: "Cookie",
    title: "Chính sách cookie",
    detail:
      "Mô tả cookie phiên đăng nhập, cookie bảo vệ CSRF và cookie chức năng; giải thích cách quản lý tại trình duyệt và tác động khi vô hiệu hóa.",
  },
] as const;

const OPERATING_PRINCIPLES = [
  "Một bộ chính sách chung cho toàn bộ module: Research, Council, Self-Med, CareGuard, Scribe, Control Tower.",
  "Điều khoản và consent được version hóa để phục vụ audit, truy vết và kiểm soát thay đổi.",
  "Ưu tiên biên an toàn lâm sàng và minh bạch nguồn dẫn trước tốc độ phản hồi.",
  "Mọi cập nhật chính sách được công bố tập trung tại Policy Hub của The Clara Care.",
] as const;

const LEGAL_MODULE_MAP = [
  {
    name: "Research",
    rule: "Bắt buộc trích dẫn nguồn và ghi nhận telemetry cho truy vết.",
  },
  {
    name: "Council",
    rule: "Hỗ trợ hội chẩn tham khảo, không thay thế quyết định chuyên môn cuối.",
  },
  {
    name: "Self-Med",
    rule: "Yêu cầu đồng thuận y tế trước khi mở luồng dữ liệu thuốc cá nhân.",
  },
  {
    name: "CareGuard",
    rule: "Ràng buộc đồng thuận y tế và cảnh báo rủi ro theo nguyên tắc safety-first.",
  },
  {
    name: "Scribe",
    rule: "Chuẩn hóa ghi chú tham khảo, cần rà soát lại trước khi dùng chính thức.",
  },
  {
    name: "Control Tower",
    rule: "Quản trị cấu hình vận hành và policy guard ở cấp hệ thống.",
  },
] as const;

export default function LegalHubPage() {
  return (
    <main className="chrome-shell min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-10 pt-8 sm:px-6 lg:px-8">
        <section className="chrome-panel rounded-[1.9rem] border border-[color:var(--shell-border)] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">The Clara Care · Policy Hub</p>
              <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-[2rem]">Trung tâm pháp lý</h1>
              <p className="mt-3 max-w-[84ch] text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                Nguồn tham chiếu pháp lý chính thức của The Clara Care cho toàn bộ luồng sản phẩm. Người dùng, đội vận hành và quản
                trị viên cần dựa vào trang này để xác định phạm vi sử dụng, quyền và nghĩa vụ khi làm việc với hệ thống.
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
              Safety-First AI
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Policy version: {LEGAL_POLICY_VERSION}
            </span>
            <span className="rounded-full border border-emerald-400/35 bg-emerald-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-300">
              Áp dụng: Web · API · ML
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
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
          <h2 className="text-lg font-extrabold tracking-tight text-[var(--text-primary)] sm:text-xl">Bản đồ legal theo module</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {LEGAL_MODULE_MAP.map((item) => (
              <article key={item.name} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-3">
                <p className="text-sm font-black tracking-tight text-[var(--text-primary)]">{item.name}</p>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{item.rule}</p>
              </article>
            ))}
          </div>
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
