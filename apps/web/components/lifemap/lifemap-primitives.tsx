"use client";

import { ReactNode } from "react";

export function SurfaceCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-[var(--shadow-sm)] ${className}`}
    >
      {children}
    </section>
  );
}

export function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-400/50 dark:bg-rose-500/15 dark:text-rose-100">
      <div className="flex items-start gap-3">
        <span className="material-symbols-outlined mt-0.5 text-lg" aria-hidden="true">error</span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Chưa thể tải dữ liệu</p>
          <p className="mt-1 leading-5">{message}</p>
        </div>
        {onRetry ? <button type="button" onClick={onRetry} className="rounded-lg border border-current px-3 py-1.5 font-medium hover:bg-rose-100/70 dark:hover:bg-rose-400/10">Thử lại</button> : null}
      </div>
    </div>
  );
}

export function LoadingCards({ count = 3 }: { count?: number }) {
  return <div aria-label="Đang tải" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: count }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-2xl bg-[var(--surface-muted)]" />)}</div>;
}

export function EmptyState({ icon, title, description, children }: { icon: string; title: string; description: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]/55 px-5 py-10 text-center">
      <span className="material-symbols-outlined inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface-brand-soft)] text-xl text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">{icon}</span>
      <h2 className="mt-4 text-base font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
      {children ? <div className="mt-5">{children}</div> : null}
    </div>
  );
}
