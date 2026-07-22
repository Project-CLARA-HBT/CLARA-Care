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
        <h1 className="text-[1.8rem] font-semibold leading-[1.15] tracking-[-0.035em] text-[var(--text-primary)] sm:text-[2.15rem]">
          {title}
        </h1>
      ) : null}
      {description ? (
        <p className="mt-2 max-w-[68ch] text-[15px] leading-6 text-[var(--text-secondary)]">
          {description}
        </p>
      ) : null}
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
