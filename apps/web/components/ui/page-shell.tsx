export default function PageShell({
  title,
  description,
  children,
  variant = "card"
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
  variant?: "card" | "plain";
}) {
  const hasHeading = Boolean(title?.trim()) || Boolean(description?.trim());
  const heading = (
    <header className="page-intro">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.09em] text-[var(--text-brand)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" aria-hidden="true" />
        <span>CLARA Care</span>
      </div>
      <h1 className="mt-3 text-[2rem] font-semibold leading-[1.15] tracking-[-0.035em] text-[var(--text-primary)] sm:text-[2.35rem]">{title}</h1>
      {description ? <p className="mt-3 max-w-[72ch] text-base leading-7 text-[var(--text-secondary)]">{description}</p> : null}
    </header>
  );

  if (variant === "plain") {
    return (
      <section className="space-y-5">
        {hasHeading ? heading : null}
        <div>{children}</div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      {hasHeading ? heading : null}
      <div className="fluent-card rounded-2xl p-4 sm:p-6 lg:p-7">
        {children}
      </div>
    </section>
  );
}
