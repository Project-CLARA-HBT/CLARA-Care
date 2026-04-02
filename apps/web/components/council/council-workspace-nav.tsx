"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type CouncilWorkspaceLink = {
  href: string;
  label: string;
  hint: string;
};

export const COUNCIL_WORKSPACE_LINKS: CouncilWorkspaceLink[] = [
  { href: "/council", label: "Landing", hint: "Tổng quan" },
  { href: "/council/new", label: "New Case", hint: "Cấu hình từng bước" },
  { href: "/council/result", label: "Result", hint: "Kết quả hội chẩn" },
];

function isActiveLink(pathname: string, href: string): boolean {
  if (href === "/council") {
    return pathname === "/council";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function CouncilWorkspaceNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  return (
    <nav className={`chrome-panel rounded-[1.3rem] border border-[color:var(--shell-border)] p-2.5 ${className}`.trim()}>
      <p className="px-1 text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">Council Workspace</p>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-3">
        {COUNCIL_WORKSPACE_LINKS.map((item) => {
          const active = isActiveLink(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-xl border px-3 py-2.5 transition ${
                active
                  ? "border-sky-400 bg-sky-100 text-sky-900 dark:border-sky-500 dark:bg-sky-950/45 dark:text-sky-100"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              <p className="text-sm font-semibold">{item.label}</p>
              <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{item.hint}</p>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
