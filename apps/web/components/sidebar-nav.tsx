"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { beginLogout } from "@/lib/logout";
import NavItem from "@/components/navigation/nav-item";
import {
  getGroupedNavItems,
  getSidebarNavItems,
  getRoleHomePath,
  isActiveRoute,
  type UserRole,
} from "@/lib/navigation.config";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { ThemePreference } from "@/lib/theme";
import type { UILanguage } from "@/lib/ui-language";
import type { ProfileContextProfile } from "@/lib/profile-context";

type SidebarNavProps = {
  role: UserRole;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  themePreference: ThemePreference;
  onThemeChange: (value: ThemePreference) => void;
  uiLanguage: UILanguage;
  onLanguageChange: (value: UILanguage) => void;
  activeProfile?: ProfileContextProfile | null;
};

const GROUP_KEYS: Record<string, UITranslationKey> = {
  care: "navigation.care",
  medicines: "navigation.medicines",
  explore: "navigation.explore",
  clinical: "navigation.clinical",
  admin: "navigation.admin",
  support: "navigation.support",
};

const ROLE_LABEL_KEYS: Record<UserRole, UITranslationKey> = {
  normal: "role.normal",
  researcher: "role.researcher",
  doctor: "role.doctor",
  admin: "role.admin",
};

export default function SidebarNav({
  role,
  collapsed = false,
  onToggleCollapse,
  uiLanguage,
  activeProfile = null,
}: SidebarNavProps) {
  const pathname = usePathname();
  const compactItems = getSidebarNavItems(role, uiLanguage, pathname);
  const groups = getGroupedNavItems(role, uiLanguage)
    .map((group) => ({
      ...group,
      items: group.items.filter((item) =>
        compactItems.some((compactItem) => compactItem.href === item.href),
      ),
    }))
    .filter((group) => group.items.length > 0);
  const homeHref = getRoleHomePath(role);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const roleLabel = t(uiLanguage, ROLE_LABEL_KEYS[role]);
  const groupLabel = (key: string, fallback: string) =>
    GROUP_KEYS[key] ? t(uiLanguage, GROUP_KEYS[key]) : fallback;

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  };

  return (
    <aside
      className={[
        "app-navigation sticky top-0 hidden h-screen shrink-0 border-r border-[color:var(--shell-border)] lg:flex lg:flex-col",
        collapsed ? "w-[5rem] px-2" : "w-[17.5rem] px-3",
      ].join(" ")}
      aria-label={t(uiLanguage, "navigation.primary")}
    >
      <div
        className={[
          "flex h-[4.5rem] shrink-0 items-center border-b border-[color:var(--shell-border)]",
          collapsed ? "justify-center" : "gap-3 px-2",
        ].join(" ")}
      >
        <Link href={homeHref} className="app-brand-mark" aria-label="CLARA">
          <span
            className="material-symbols-outlined text-[21px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
            aria-hidden="true"
          >
            health_and_safety
          </span>
        </Link>
        {!collapsed ? (
          <Link href={homeHref} className="min-w-0">
            <span className="block text-[17px] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
              CLARA
            </span>
            <span className="block truncate text-[11px] font-medium text-[var(--text-muted)]">
              {t(uiLanguage, "brand.healthAssistant")}
            </span>
          </Link>
        ) : null}
      </div>

      <div className="py-4">
        <Link
          href="/chat"
          className={collapsed ? "app-new-chat !px-0" : "app-new-chat"}
          title={t(uiLanguage, "action.askClara")}
        >
          <span
            className="material-symbols-outlined text-[19px]"
            aria-hidden="true"
          >
            auto_awesome
          </span>
          {!collapsed ? <span>{t(uiLanguage, "action.askClara")}</span> : null}
        </Link>
      </div>

      <div className="clara-scrollbar flex-1 space-y-5 overflow-y-auto pb-4">
        {groups.map((group) => (
          <section key={group.key}>
            {!collapsed ? (
              <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                {groupLabel(group.key, group.label)}
              </p>
            ) : null}
            <nav
              className="space-y-1"
              aria-label={
                groupLabel(group.key, group.label)
              }
            >
              {group.items.map((item) => (
                <NavItem
                  key={item.href}
                  item={item}
                  active={isActiveRoute(pathname, item.href)}
                  variant="sidebar"
                  collapsed={collapsed}
                />
              ))}
            </nav>
          </section>
        ))}
      </div>

      <div className="border-t border-[color:var(--shell-border)] py-3">
        <div className={collapsed ? "flex justify-center" : "px-1"}>
          <div
            className={[
              "flex items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
              collapsed ? "h-11 w-11 justify-center" : "gap-3 p-2.5",
            ].join(" ")}
          >
            <span className="app-profile-avatar shrink-0" aria-hidden="true">
              {roleLabel.slice(0, 1)}
            </span>
            {!collapsed ? (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold text-[var(--text-primary)]">
                  {activeProfile?.display_name ?? t(uiLanguage, "profile.yourAccount")}
                </span>
                <span className="block truncate text-[11px] text-[var(--text-muted)]">
                  {activeProfile?.kind === "shared" ? t(uiLanguage, "profile.sharedAccess") : roleLabel}
                </span>
              </span>
            ) : null}
          </div>
        </div>

        <div
          className={[
            "mt-2 flex items-center",
            collapsed ? "flex-col gap-1" : "justify-between px-1",
          ].join(" ")}
        >
          <button
            type="button"
            onClick={onToggleCollapse}
            className="app-sidebar-action"
            aria-label={
              collapsed
                ? t(uiLanguage, "action.expand")
                : t(uiLanguage, "action.collapse")
            }
            title={collapsed ? t(uiLanguage, "action.expand") : t(uiLanguage, "action.collapse")}
          >
            <span
              className="material-symbols-outlined text-[18px]"
              aria-hidden="true"
            >
              {collapsed ? "right_panel_open" : "left_panel_close"}
            </span>
            {!collapsed ? (
              <span>{t(uiLanguage, "action.collapse")}</span>
            ) : null}
          </button>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="app-sidebar-action hover:!text-[var(--status-danger-text)]"
            aria-label={t(uiLanguage, "action.signOut")}
            title={t(uiLanguage, "action.signOut")}
          >
            <span
              className="material-symbols-outlined text-[18px]"
              aria-hidden="true"
            >
              logout
            </span>
            {!collapsed ? (
              <span>
                {isLoggingOut ? t(uiLanguage, "action.signingOut") : t(uiLanguage, "action.signOut")}
              </span>
            ) : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
