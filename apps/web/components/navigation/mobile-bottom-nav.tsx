"use client";

import { usePathname } from "next/navigation";
import NavItem from "@/components/navigation/nav-item";
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
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-[color:var(--shell-border)] bg-[var(--surface-header)] pb-[env(safe-area-inset-bottom,0px)] lg:hidden" aria-label="Điều hướng chính">
      <div className="mx-auto max-w-2xl px-1 py-1">
        <ul
          className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${Math.max(items.length, 1)}, minmax(0, 1fr))` }}
        >
          {items.map((item) => (
            <li key={item.href}>
              <NavItem
                item={item}
                active={isActiveRoute(pathname, item.href)}
                variant="bottom"
              />
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
