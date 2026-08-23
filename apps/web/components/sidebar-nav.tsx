"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import NavItem from "@/components/navigation/nav-item";
import { resolveNavigationIcon } from "@/components/navigation/nav-item";
import Icon from "@/components/ui/icon";
import {
  isActiveRoute,
  type UserRole,
} from "@/lib/navigation.config";
import {
  getAvailableWorkspaces,
  getWorkspaceNavigation,
  type WorkspaceId,
} from "@/lib/navigation.workspaces";
import { t } from "@/lib/i18n/catalog";
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
  workspace: WorkspaceId;
  onWorkspaceChange: (workspace: WorkspaceId) => void;
};

export default function SidebarNav({
  role,
  collapsed = false,
  onToggleCollapse,
  uiLanguage,
  workspace,
  onWorkspaceChange,
}: SidebarNavProps) {
  const pathname = usePathname();
  const workspaces = getAvailableWorkspaces(role, uiLanguage);
  const navigation = getWorkspaceNavigation(role, workspace, uiLanguage);
  const homeHref = navigation.workspace.homeHref;
  const moreLabel = t(uiLanguage, "navigation.more");

  return (
    <aside
      className={[
        "app-navigation sticky top-0 hidden h-screen shrink-0 border-r border-[color:var(--shell-border)] lg:flex lg:flex-col",
        collapsed ? "w-[4.25rem] px-2" : "w-64 px-3",
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
          <Icon name="clinical-notes" size={21} aria-hidden="true" />
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

      {workspaces.length > 1 ? <div className="py-3">
        {collapsed ? (
          <button
            type="button"
            onClick={() => {
              const index = workspaces.findIndex((entry) => entry.id === workspace);
              const next = workspaces[(index + 1) % workspaces.length];
              if (next) onWorkspaceChange(next.id);
            }}
            className="app-sidebar-action mx-auto !h-11 !w-11 justify-center"
            aria-label={`${t(uiLanguage, "navigation.workspace.label")}: ${navigation.workspace.label}`}
            title={navigation.workspace.label}
          >
            <Icon name={resolveNavigationIcon(navigation.workspace.icon)} size={20} aria-hidden="true" />
          </button>
        ) : (
          <label className="block px-1">
            <span className="mb-1.5 block px-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
              {t(uiLanguage, "navigation.workspace.label")}
            </span>
            <span className="flex min-h-11 items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5">
              <Icon name={resolveNavigationIcon(navigation.workspace.icon)} size={19} className="text-[var(--text-brand)]" aria-hidden="true" />
              <select
                value={workspace}
                onChange={(event) => onWorkspaceChange(event.target.value as WorkspaceId)}
                className="min-w-0 flex-1 bg-transparent text-sm font-semibold text-[var(--text-primary)] outline-none"
                aria-label={t(uiLanguage, "navigation.workspace.choose")}
              >
                {workspaces.map((entry) => (
                  <option key={entry.id} value={entry.id}>{entry.label}</option>
                ))}
              </select>
            </span>
          </label>
        )}
      </div> : null}

      <div className="clara-scrollbar flex-1 overflow-y-auto pb-4">
        <nav className="space-y-1" aria-label={navigation.workspace.label}>
          {navigation.primary.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={isActiveRoute(pathname, item.href)}
              variant="sidebar"
              collapsed={collapsed}
            />
          ))}
        </nav>

        {navigation.secondary.length > 0 ? (
          <details className="group mt-3" open={!collapsed && navigation.secondary.some((item) => isActiveRoute(pathname, item.href))}>
            <summary
              className={[
                "app-nav-item cursor-pointer list-none",
                collapsed ? "justify-center px-0" : "gap-3 px-3",
              ].join(" ")}
              title={moreLabel}
            >
              <Icon name="more" size={20} aria-hidden="true" />
              {!collapsed ? <span>{moreLabel}</span> : null}
              {!collapsed ? <Icon name="chevron-down" size={17} className="ml-auto transition group-open:rotate-180" aria-hidden="true" /> : null}
            </summary>
            <nav className={collapsed ? "mt-1 space-y-1" : "mt-1 space-y-1 pl-2"} aria-label={moreLabel}>
              {navigation.secondary.map((item) => (
                <NavItem
                  key={item.href}
                  item={item}
                  active={isActiveRoute(pathname, item.href)}
                  variant="sidebar"
                  collapsed={collapsed}
                />
              ))}
            </nav>
          </details>
        ) : null}
      </div>

      <div className="border-t border-[color:var(--shell-border)] py-3">
        <div className={collapsed ? "flex justify-center" : "px-1"}>
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
            <Icon name={collapsed ? "arrow-right" : "menu"} size={18} aria-hidden="true" />
            {!collapsed ? (
              <span>{t(uiLanguage, "action.collapse")}</span>
            ) : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
