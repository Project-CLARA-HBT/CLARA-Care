import Link from "next/link";
import { ReactNode } from "react";

export type AdminTabKey =
  | "overview"
  | "rag-sources"
  | "knowledge-sources"
  | "source-hub"
  | "answer-flow"
  | "observability";

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
    label: "Overview",
    hint: "Toàn cảnh cấu hình và trạng thái",
    code: "A01"
  },
  {
    key: "rag-sources",
    href: "/admin/rag-sources",
    label: "RAG Sources",
    hint: "Nguồn truy xuất và độ ưu tiên",
    code: "A02"
  },
  {
    key: "knowledge-sources",
    href: "/admin/knowledge-sources",
    label: "Knowledge",
    hint: "Kho tài liệu upload theo source",
    code: "A03"
  },
  {
    key: "source-hub",
    href: "/admin/source-hub",
    label: "Source Hub",
    hint: "Đồng bộ nguồn chuẩn y khoa",
    code: "A04"
  },
  {
    key: "answer-flow",
    href: "/admin/answer-flow",
    label: "Answer Flow",
    hint: "Flow flags và runtime debug",
    code: "A05"
  },
  {
    key: "observability",
    href: "/admin/observability",
    label: "Observability",
    hint: "Health, metrics và Grafana",
    code: "A06"
  }
];

export default function AdminShell({ activeTab, title, description, children }: AdminShellProps) {
  const rawGrafanaBase = (process.env.NEXT_PUBLIC_GRAFANA_URL ?? "/grafana").trim();
  const grafanaBase = rawGrafanaBase.endsWith("/")
    ? rawGrafanaBase.slice(0, -1)
    : rawGrafanaBase;
  const grafanaOverviewUrl = `${grafanaBase}/d/clara-observability/clara-observability?orgId=1`;

  return (
    <div className="space-y-5">
      <section
        className="relative overflow-hidden rounded-[2rem] border border-[color:var(--shell-border)] bg-[linear-gradient(145deg,rgba(255,255,255,0.92),rgba(248,250,252,0.86))] p-5 shadow-[0_28px_68px_-44px_rgba(15,23,42,0.48)] dark:bg-[linear-gradient(145deg,rgba(6,12,24,0.94),rgba(10,18,34,0.9))]"
        aria-labelledby="admin-shell-title"
        aria-describedby="admin-shell-description"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-400/10" />
        <div className="pointer-events-none absolute -left-12 bottom-0 h-44 w-52 rounded-full bg-blue-300/15 blur-3xl dark:bg-blue-400/10" />

        <div className="relative grid gap-5 xl:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <p className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.17em] text-[var(--text-brand)]">
              Admin Control Plane
            </p>
            <h2 id="admin-shell-title" className="mt-3 text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-[2.15rem]">
              {title}
            </h2>
            <p id="admin-shell-description" className="mt-2 max-w-3xl text-base leading-7 text-[var(--text-secondary)]">
              {description}
            </p>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-1">
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Control Endpoint</p>
              <p className="mt-1 text-sm font-mono text-[var(--text-primary)]">/system/control-tower/config</p>
            </div>
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Operating Surface</p>
              <p className="mt-1 text-sm font-mono text-[var(--text-primary)]">RAG · Flow · Runtime · Grafana</p>
            </div>
            <a
              href={grafanaOverviewUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 transition hover:border-[color:var(--shell-border-strong)]"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Grafana Board</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text-brand)]">Mở dashboard giám sát ↗</p>
            </a>
          </div>
        </div>
      </section>

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
