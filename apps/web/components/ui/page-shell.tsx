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
    <div className="space-y-2">
      <h1 className="text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-[2.2rem] lg:text-[2.4rem]">{title}</h1>
      {description ? <p className="max-w-[74ch] text-base leading-relaxed text-[var(--text-secondary)]">{description}</p> : null}
    </div>
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
      <div className="chrome-panel rounded-[1.65rem] p-5 sm:p-6 lg:p-7">
        {children}
      </div>
    </section>
  );
}
