"use client";

import Link from "next/link";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function CouncilEmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const language = useUILanguage();
  return (
    <section className="rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 text-center">
      <p className="text-base font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{description}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Link
          href="/council/new"
          className="inline-flex min-h-[46px] items-center rounded-[var(--radius-lg)] bg-[var(--brand-600)] px-5 text-sm font-semibold text-[#cdd7ff] transition hover:bg-[var(--brand-500)]"
        >
          {t(language, "council.empty.create")}
        </Link>
        <Link
          href="/council"
          className="inline-flex min-h-[46px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)]"
        >
          {t(language, "council.empty.landing")}
        </Link>
      </div>
    </section>
  );
}
