import Link from "next/link";
import { ReactNode } from "react";

type LegalPageShellProps = {
  title: string;
  summary: string;
  updatedAt: string;
  children: ReactNode;
};

export default function LegalPageShell({ title, summary, updatedAt, children }: LegalPageShellProps) {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-10 text-[var(--text-primary)]">
      <section className="chrome-panel rounded-2xl border border-[color:var(--shell-border)] p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Project CLARA - Legal</p>
        <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">{title}</h1>
        <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{summary}</p>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Cập nhật lần cuối: <span className="font-semibold">{updatedAt}</span>
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href="/legal"
            className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
          >
            Trung tâm pháp lý
          </Link>
          <Link
            href="/"
            className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
          >
            Về trang chủ
          </Link>
        </div>
      </section>

      <section className="space-y-4">{children}</section>
    </main>
  );
}
