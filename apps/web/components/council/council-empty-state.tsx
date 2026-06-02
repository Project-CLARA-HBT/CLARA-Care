import Link from "next/link";

export default function CouncilEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="chrome-panel rounded-[1.55rem] p-6 text-center">
      <p className="text-base font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{description}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Link
          href="/council/new"
          className="inline-flex min-h-[46px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white"
        >
          Tạo ca mới
        </Link>
        <Link
          href="/council"
          className="inline-flex min-h-[46px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)]"
        >
          Về landing
        </Link>
      </div>
    </section>
  );
}
