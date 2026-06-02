import Link from "next/link";
import { ReactNode } from "react";

export type AdminTabKey =
  | "overview"
  | "knowledge-sources"
  | "answer-flow"
  | "observability"
  | "product-analytics"
  | "clinical-analytics";

type AdminShellProps = {
  activeTab: AdminTabKey;
  title: string;
  description: string;
  children: ReactNode;
};

const ADMIN_TABS: Array<{
  key: AdminTabKey;
  href: string;
  label: string;
  hint: string;
  code: string;
}> = [
  {
    key: "overview",
    href: "/admin/overview",
    label: "Tổng quan",
    hint: "Toàn cảnh cấu hình và trạng thái",
    code: "A01"
  },
  {
    key: "knowledge-sources",
    href: "/admin/knowledge-sources",
    label: "Nguồn tri thức",
    hint: "Kho tri thức và connector truy xuất",
    code: "A02"
  },
  {
    key: "answer-flow",
    href: "/admin/answer-flow",
    label: "Luồng trả lời",
    hint: "Flow flags và runtime debug",
    code: "A03"
  },
  {
    key: "observability",
    href: "/admin/observability",
    label: "Giám sát",
    hint: "Health, metrics và signal board",
    code: "A04"
  },
  {
    key: "product-analytics",
    href: "/admin/analytics",
    label: "Phân tích sản phẩm",
    hint: "Người dùng, Surface và giữ chân",
    code: "A05"
  },
  {
    key: "clinical-analytics",
    href: "/admin/analytics/clinical",
    label: "Phân tích lâm sàng",
    hint: "Kiểm chứng, DDI và độ trễ",
    code: "A06"
  }
];

export default function AdminShell({ activeTab, title, description, children }: AdminShellProps) {
  return (
    <div className="space-y-5">
      <div className="sr-only">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <nav
        className="rounded-[1.4rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 shadow-soft"
        aria-label="Admin navigation"
      >
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
          {ADMIN_TABS.map((tab) => {
            const isActive = tab.key === activeTab;
            return (
              <li key={tab.key}>
                <Link
                  href={tab.href}
                  aria-current={isActive ? "page" : undefined}
                  className={[
                    "group flex min-h-[90px] flex-col justify-between rounded-xl border p-3 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900",
                    isActive
                      ? "border-sky-500 bg-sky-100/80 text-sky-900 shadow-[inset_0_0_0_1px_rgba(14,165,233,0.22)] dark:bg-sky-950/50 dark:text-sky-100"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]"
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{tab.label}</span>
                    <span
                      className={[
                        "inline-flex min-w-[2rem] items-center justify-center rounded-lg border px-2 py-0.5 text-[11px] font-semibold",
                        isActive
                          ? "border-sky-300/80 bg-white/70 text-sky-800 dark:border-sky-700 dark:bg-sky-950/80 dark:text-sky-200"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-muted)]"
                      ].join(" ")}
                      aria-hidden="true"
                    >
                      {tab.code}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--text-muted)]">{tab.hint}</p>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {children}
    </div>
  );
}
