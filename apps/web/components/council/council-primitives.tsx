import { ReactNode } from "react";

export function CouncilMetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-1 text-xs text-[var(--text-secondary)]">{hint}</p> : null}
    </article>
  );
}

export function CouncilSection({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`chrome-panel rounded-[1.55rem] p-5 sm:p-6 ${className}`.trim()}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {eyebrow ? (
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">{eyebrow}</p>
          ) : null}
          <h2 className="mt-1 text-xl font-semibold text-[var(--text-primary)] sm:text-[1.7rem]">{title}</h2>
        </div>
        {action ? <div>{action}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function CouncilList({
  items,
  emptyText,
}: {
  items: string[];
  emptyText: string;
}) {
  if (!items.length) {
    return <p className="text-sm text-[var(--text-secondary)]">{emptyText}</p>;
  }

  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}
