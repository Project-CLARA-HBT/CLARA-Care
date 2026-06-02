"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getMobilePrimaryNav, isActiveRoute, type UserRole } from "@/lib/navigation.config";

type MobileBottomNavProps = {
  role: UserRole;
};

export default function MobileBottomNav({ role }: MobileBottomNavProps) {
  const pathname = usePathname();
  if (pathname === "/research" || pathname.startsWith("/research/")) {
    return null;
  }
  const items = getMobilePrimaryNav(role);

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+12px)] pt-2 lg:hidden">
      <div className="chrome-panel mx-auto max-w-2xl rounded-[1.45rem] border border-[color:var(--shell-border)] px-2 py-2">
        <ul
          className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${Math.max(items.length, 1)}, minmax(0, 1fr))` }}
        >
          {items.map((item) => {
            const active = isActiveRoute(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`chrome-nav-link flex min-h-[56px] flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-center transition ${
                    active
                      ? "border-[color:var(--shell-border-strong)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                      : "border-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span className="text-xs font-semibold leading-tight">{item.label}</span>
                  <span
                    className={`mt-1 h-1.5 w-1.5 rounded-full transition ${
                      active ? "bg-[var(--text-brand)]" : "bg-[var(--text-muted)]/50"
                    }`}
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
