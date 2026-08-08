"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type CouncilWorkspaceLink = {
  href: string;
  labelKey: UITranslationKey;
  hintKey: UITranslationKey;
};

export const COUNCIL_WORKSPACE_LINKS: CouncilWorkspaceLink[] = [
  { href: "/council", labelKey: "council.nav.overview.label", hintKey: "council.nav.overview.hint" },
  { href: "/council/new", labelKey: "council.nav.new.label", hintKey: "council.nav.new.hint" },
  { href: "/council/result", labelKey: "council.nav.result.label", hintKey: "council.nav.result.hint" },
];

function isActiveLink(pathname: string, href: string): boolean {
  if (href === "/council") {
    return pathname === "/council";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function CouncilWorkspaceNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();
  const language = useUILanguage();

  return (
    <nav className={`rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-3 ${className}`.trim()}>
      <p className="px-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--text-muted)]">{t(language, "council.nav.title")}</p>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-3">
        {COUNCIL_WORKSPACE_LINKS.map((item) => {
          const active = isActiveLink(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-xl border px-3 py-2.5 transition ${
                active
                  ? "border-transparent bg-[color:var(--surface-brand-soft)] text-[color:var(--text-brand)]"
                  : "border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] text-[color:var(--text-primary)] hover:border-[color:var(--shell-border-strong)] hover:bg-[color:var(--surface-muted)]"
              }`}
            >
              <p className="text-sm font-bold">{t(language, item.labelKey)}</p>
              <p className="mt-0.5 text-xs font-medium text-[color:var(--text-secondary)]">{t(language, item.hintKey)}</p>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
