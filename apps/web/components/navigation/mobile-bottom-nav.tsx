"use client";

import { usePathname } from "next/navigation";
import NavItem from "@/components/navigation/nav-item";
import { isActiveRoute, type UserRole } from "@/lib/navigation.config";
import { getMobileWorkspaceNav, type WorkspaceId } from "@/lib/navigation.workspaces";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import Icon from "@/components/ui/icon";

type MobileBottomNavProps = {
  role: UserRole;
  workspace: WorkspaceId;
  onOpenMore: () => void;
};

export default function MobileBottomNav({ role, workspace, onOpenMore }: MobileBottomNavProps) {
  const pathname = usePathname();
  const language = useUILanguage();
  if (pathname === "/research" || pathname.startsWith("/research/")) {
    return null;
  }
  const items = getMobileWorkspaceNav(role, workspace, language);
  const moreLabel = t(language, "navigation.more");

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-[color:var(--shell-border)] bg-[var(--surface-header)] pb-[env(safe-area-inset-bottom,0px)] lg:hidden" aria-label={t(language, "navigation.primary")}>
      <div className="mx-auto max-w-2xl px-1 py-1">
        <ul
          className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${Math.max(items.length + 1, 1)}, minmax(0, 1fr))` }}
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
          <li>
            <button
              type="button"
              onClick={onOpenMore}
              className="focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-2 py-1.5 text-center text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
              aria-label={moreLabel}
            >
              <Icon name="more" size={19} />
              <span className="max-w-full truncate text-[11px] font-semibold leading-tight">{moreLabel}</span>
            </button>
          </li>
        </ul>
      </div>
    </nav>
  );
}
