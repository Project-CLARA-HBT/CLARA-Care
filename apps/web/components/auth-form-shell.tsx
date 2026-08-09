import { ReactNode } from "react";

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
};

export default function AuthFormShell({ title, subtitle, children }: Props) {
  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-[1120px] items-center justify-center px-4 py-12 sm:px-6 lg:px-12">

      <section
        className="w-full max-w-xl rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8"
        aria-labelledby="auth-form-title"
        aria-describedby="auth-form-subtitle auth-form-help"
      >
        <p className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">
          CLARA-Care
        </p>
        <h1 id="auth-form-title" className="mt-4 text-[1.75rem] font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-[2rem]">
          {title}
        </h1>
        <p id="auth-form-subtitle" className="mt-3 text-base leading-7 text-[var(--text-secondary)]">
          {subtitle}
        </p>
        <p id="auth-form-help" className="sr-only">
          Cac truong co dau sao la bat buoc.
        </p>
        <div className="mt-8">{children}</div>
      </section>
    </main>
  );
}
