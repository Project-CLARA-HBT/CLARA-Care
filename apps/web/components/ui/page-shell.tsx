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
    <header className="border-b border-[color:var(--shell-border)] pb-5">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-brand)]">CLARA Care</p>
      <h1 className="text-[1.75rem] font-semibold leading-9 tracking-[-0.02em] text-[var(--text-primary)] sm:text-[2rem]">{title}</h1>
      {description ? <p className="mt-2 max-w-[72ch] text-[0.95rem] leading-6 text-[var(--text-secondary)]">{description}</p> : null}
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
      <div className="fluent-card p-4 sm:p-6">
        {children}
      </div>
    </section>
  );
}
