import { ReactNode } from "react";

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
};

export default function AuthFormShell({ title, subtitle, children }: Props) {
  return (
    <main className="relative isolate mx-auto flex min-h-[100dvh] max-w-6xl items-center justify-center overflow-hidden px-4 py-12 sm:px-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_10%_14%,rgba(96,165,250,0.18),transparent_38%),radial-gradient(circle_at_86%_16%,rgba(59,130,246,0.16),transparent_36%),radial-gradient(circle_at_50%_96%,rgba(45,212,191,0.14),transparent_45%)]" />
      <div className="pointer-events-none absolute -left-16 top-10 h-72 w-72 rounded-full bg-sky-300/25 blur-3xl dark:bg-sky-700/20" />
      <div className="pointer-events-none absolute -right-16 bottom-10 h-72 w-72 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-700/20" />

      <section
        className="glass-surface-3 relative w-full max-w-xl overflow-hidden rounded-[2rem] border border-sky-200/70 p-7 shadow-hero sm:p-10 dark:border-sky-700/40"
        aria-labelledby="auth-form-title"
        aria-describedby="auth-form-subtitle auth-form-help"
      >
        <div className="pointer-events-none absolute -top-20 right-10 h-40 w-40 rounded-full bg-sky-300/20 blur-3xl dark:bg-sky-500/20" />
        <div className="pointer-events-none absolute -bottom-20 -left-6 h-40 w-48 rounded-full bg-cyan-300/20 blur-3xl dark:bg-cyan-500/20" />

        <p className="inline-flex items-center rounded-full border border-sky-200/80 bg-white/75 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700 dark:border-sky-700/50 dark:bg-slate-900/70 dark:text-sky-200">
          The Clara Care
        </p>
        <h1 id="auth-form-title" className="mt-4 text-3xl font-semibold tracking-tight text-slate-900 sm:text-[2.4rem] dark:text-slate-100">
          {title}
        </h1>
        <p id="auth-form-subtitle" className="mt-3 text-base leading-7 text-slate-700 dark:text-slate-300">
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
