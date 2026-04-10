import Link from "next/link";
import { ReactNode } from "react";

export type LegalPolicyKey = "hub" | "privacy" | "terms" | "consent" | "cookies";

type LegalNavItem = {
  key: Exclude<LegalPolicyKey, "hub">;
  href: string;
  shortLabel: string;
  title: string;
};

type LegalPageShellProps = {
  title: string;
  summary: string;
  updatedAt: string;
  policyKey: LegalPolicyKey;
  sections?: Array<{ id: string; label: string }>;
  highlights?: string[];
  children: ReactNode;
};

type LegalSectionProps = {
  id: string;
  title: string;
  children: ReactNode;
};

const POLICY_NAV_ITEMS: LegalNavItem[] = [
  {
    key: "privacy",
    href: "/legal/privacy",
    shortLabel: "Privacy",
    title: "Chính sách quyền riêng tư",
  },
  {
    key: "terms",
    href: "/legal/terms",
    shortLabel: "Terms",
    title: "Điều khoản sử dụng",
  },
  {
    key: "consent",
    href: "/legal/consent",
    shortLabel: "Consent",
    title: "Đồng thuận y tế",
  },
  {
    key: "cookies",
    href: "/legal/cookies",
    shortLabel: "Cookies",
    title: "Chính sách cookie",
  },
];

export function LegalSection({ id, title, children }: LegalSectionProps) {
  return (
    <article id={id} className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5 sm:p-6">
      <h2 className="text-lg font-extrabold tracking-tight text-[var(--text-primary)] sm:text-xl">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-7 text-[var(--text-secondary)] sm:text-[15px]">{children}</div>
    </article>
  );
}

export default function LegalPageShell({
  title,
  summary,
  updatedAt,
  policyKey,
  sections = [],
  highlights = [],
  children,
}: LegalPageShellProps) {
  return (
    <main className="chrome-shell min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-10 pt-8 sm:px-6 lg:px-8">
        <section className="chrome-panel rounded-[1.9rem] border border-[color:var(--shell-border)] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">The Clara Care · Policy Center</p>
              <p className="mt-2 text-sm text-[var(--text-muted)]">Bộ chính sách vận hành và bảo vệ dữ liệu cho toàn bộ hệ thống.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-bold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
              >
                Về trang chủ
              </Link>
              <Link
                href="/legal"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-bold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
              >
                Trung tâm pháp lý
              </Link>
            </div>
          </div>

          <div className="mt-6 space-y-3">
            <h1 className="text-2xl font-black tracking-tight text-[var(--text-primary)] sm:text-[2rem]">{title}</h1>
            <p className="max-w-[86ch] text-sm leading-7 text-[var(--text-secondary)] sm:text-base">{summary}</p>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full border border-cyan-400/35 bg-cyan-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300">
              Branding: The Clara Care
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Cập nhật: {updatedAt}
            </span>
            <span className="rounded-full border border-emerald-400/35 bg-emerald-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-300">
              Hiệu lực toàn hệ thống
            </span>
          </div>

          {highlights.length > 0 ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {highlights.slice(0, 6).map((item) => (
                <div
                  key={item}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-3 text-xs font-semibold leading-6 text-[var(--text-secondary)]"
                >
                  {item}
                </div>
              ))}
            </div>
          ) : null}

          <nav className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {POLICY_NAV_ITEMS.map((item) => {
              const active = policyKey === item.key;
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  className={[
                    "rounded-xl border px-3 py-3 transition",
                    active
                      ? "border-cyan-400/45 bg-cyan-500/12 text-cyan-700 dark:text-cyan-300"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]",
                  ].join(" ")}
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.14em]">{item.shortLabel}</p>
                  <p className="mt-1 text-sm font-bold leading-6">{item.title}</p>
                </Link>
              );
            })}
          </nav>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-4">{children}</div>

          <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
            <div className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5">
              <p className="text-[11px] font-black uppercase tracking-[0.15em] text-[var(--text-brand)]">Mục lục nhanh</p>
              {sections.length ? (
                <div className="mt-3 space-y-2">
                  {sections.map((item, index) => (
                    <a
                      key={item.id}
                      href={`#${item.id}`}
                      className="block rounded-lg border border-transparent px-2 py-2 text-sm font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
                    >
                      <span className="mr-2 text-xs font-black text-[var(--text-muted)]">{String(index + 1).padStart(2, "0")}</span>
                      {item.label}
                    </a>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-[var(--text-muted)]">Trang này chưa có mục lục chi tiết.</p>
              )}
            </div>

            <div className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-5">
              <p className="text-[11px] font-black uppercase tracking-[0.15em] text-[var(--text-brand)]">Ghi chú tuân thủ</p>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[var(--text-secondary)]">
                <li>Policy này áp dụng cho tất cả module thuộc The Clara Care.</li>
                <li>Trong xung đột văn bản, ưu tiên phiên bản cập nhật mới nhất tại Policy Center.</li>
                <li>Dữ liệu lâm sàng luôn cần xác nhận bởi chuyên môn y tế trước khi hành động.</li>
              </ul>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
