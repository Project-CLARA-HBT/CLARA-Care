export default function PageShell({
  title,
  description,
  children,
  variant = "card",
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
  variant?: "card" | "plain";
}) {
  const hasHeading = Boolean(title?.trim()) || Boolean(description?.trim());
  const heading = (
    <header className="page-intro max-w-4xl">
      {title ? (
        <h1 className="text-[24px] font-bold leading-8 tracking-[-0.02em] text-[var(--text-primary)] lg:text-[32px] lg:leading-10">
          {title}
        </h1>
      ) : null}
      {description ? (
        <p className="mt-2 max-w-[68ch] text-sm leading-6 text-[var(--text-secondary)] sm:text-[15px]">
          {description}
        </p>
      ) : null}
    </header>
  );

  if (variant === "plain") {
    return (
      <section className="space-y-8">
        {hasHeading ? heading : null}
        <div>{children}</div>
      </section>
    );
  }

  return (
    <section className="space-y-8">
      {hasHeading ? heading : null}
      <div className="fluent-card rounded-xl p-4 sm:p-6">
        {children}
      </div>
    </section>
  );
}
