"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const RESEARCH_LAB_NAV_ITEMS = [
  { href: "/research", label: "Overview" },
  { href: "/research/deepdive", label: "Deep Dive" },
  { href: "/research/analyze", label: "Analyze" },
  { href: "/research/citations", label: "Citations" },
  { href: "/research/details", label: "Details" }
] as const;

type ResearchLabRoute = (typeof RESEARCH_LAB_NAV_ITEMS)[number]["href"];

type ResearchLabNavProps = {
  className?: string;
  pathname?: string;
};

function isActiveRoute(pathname: string, href: ResearchLabRoute): boolean {
  if (href === "/research") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function ResearchLabNav({ className, pathname: pathnameProp }: ResearchLabNavProps) {
  const currentPathname = usePathname();
  const pathname = pathnameProp ?? currentPathname ?? "";
  const panelClassName = [
    "chrome-panel research-panel-modern rounded-[1.35rem] border border-[color:var(--shell-border)] p-2.5 sm:p-3",
    className
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <nav
      aria-label="Research navigation"
      className={panelClassName}
    >
      <p className="px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Research Lab</p>
      <ul className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {RESEARCH_LAB_NAV_ITEMS.map((item) => {
          const active = isActiveRoute(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`chrome-nav-link inline-flex min-h-[42px] items-center rounded-xl border px-3.5 text-sm font-semibold whitespace-nowrap transition ${
                  active
                    ? "border-cyan-300/70 bg-cyan-500/10 text-cyan-700 dark:text-cyan-200"
                    : "border-transparent bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
