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
  const heading = (
    <div className="space-y-1.5">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-[2rem]">{title}</h1>
      {description ? <p className="text-sm text-slate-600 sm:text-[15px]">{description}</p> : null}
    </div>
  );

  if (variant === "plain") {
    return (
      <section className="space-y-4">
        {heading}
        <div>{children}</div>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      {heading}
      <div className="rounded-2xl border border-slate-200/90 bg-white/90 p-4 shadow-[0_14px_34px_-26px_rgba(15,23,42,0.5)] backdrop-blur sm:p-5">
        {children}
      </div>
    </section>
  );
}
