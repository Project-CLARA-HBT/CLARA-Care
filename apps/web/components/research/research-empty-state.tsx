import Link from "next/link";

type ResearchEmptyStateProps = {
  title?: string;
  description?: string;
  actionLabel?: string;
  className?: string;
};

export default function ResearchEmptyState({
  title = "No research run available",
  description = "Run a research query to populate this view with the latest deep-analysis output.",
  actionLabel = "Go to Research",
  className
}: ResearchEmptyStateProps) {
  const containerClassName = ["chrome-panel rounded-[1.6rem] p-5 sm:p-6", className]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={containerClassName}>
      <div className="rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 py-8 text-center">
        <p className="text-base font-semibold text-[var(--text-primary)]">{title}</p>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
        <Link
          href="/chat"
          className="mt-4 inline-flex min-h-[46px] items-center rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-5 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)]"
        >
          {actionLabel}
        </Link>
      </div>
    </section>
  );
}
