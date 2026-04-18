"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { beginLogout } from "@/lib/logout";
import {
  getGroupMeta,
  getGroupedNavItems,
  isActiveRoute,
  type UserRole,
} from "@/lib/navigation.config";
import { type ThemePreference } from "@/lib/theme";
import { type UILanguage } from "@/lib/ui-language";

type SidebarNavProps = {
  role: UserRole;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  themePreference: ThemePreference;
  onThemeChange: (value: ThemePreference) => void;
  uiLanguage: UILanguage;
  onLanguageChange: (value: UILanguage) => void;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Nguoi dung",
  researcher: "Nghien cuu",
  doctor: "Bac si",
  admin: "Quan tri",
};

const THEME_OPTIONS: Array<{ value: ThemePreference; label: string; iconClass: string }> = [
  { value: "light", label: "Sang", iconClass: "fa-sun-o" },
  { value: "dark", label: "Toi", iconClass: "fa-moon-o" },
  { value: "system", label: "System", iconClass: "fa-desktop" },
];

const LANGUAGE_OPTIONS: Array<{ value: UILanguage; label: string }> = [
  { value: "vi", label: "VI" },
  { value: "en", label: "EN" },
];

const LEGACY_ACTIONS: Array<{ id: string; iconClass: string; ariaLabel: string; href: string }> = [
  { id: "notifications", iconClass: "fa-bell-o", ariaLabel: "Thong bao", href: "/chat" },
  { id: "settings", iconClass: "fa-cog", ariaLabel: "Cai dat", href: "/role-select" },
  { id: "help", iconClass: "fa-life-ring", ariaLabel: "Tro giup", href: "/huong-dan" },
];

function getNextThemePreference(current: ThemePreference): ThemePreference {
  if (current === "light") return "dark";
  if (current === "dark") return "system";
  return "light";
}

function getThemeIconClass(theme: ThemePreference): string {
  if (theme === "light") return "fa-sun-o";
  if (theme === "dark") return "fa-moon-o";
  return "fa-desktop";
}

export default function SidebarNav({
  role,
  collapsed = false,
  onToggleCollapse,
  themePreference,
  onThemeChange,
  uiLanguage,
  onLanguageChange,
}: SidebarNavProps) {
  const pathname = usePathname();
  const groups = getGroupedNavItems(role);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  };

  return (
    <aside
      className={[
        "sticky top-0 hidden h-screen shrink-0 border-r border-slate-200/70 bg-[#eceef0] py-6 shadow-[inset_-1px_0_0_rgba(0,0,0,0.05)] transition-[width,padding] dark:border-slate-800 dark:bg-slate-900 lg:flex lg:flex-col",
        collapsed ? "w-[5.5rem] px-2" : "w-64 px-4",
      ].join(" ")}
    >
      <div className={["mb-8 flex items-center", collapsed ? "justify-center" : "gap-3 px-2"].join(" ")}>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-slate-200/80 bg-white/90 text-[#2f4d67] shadow-sm dark:border-slate-700/80 dark:bg-slate-800/90 dark:text-slate-100">
          <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            clinical_notes
          </span>
        </div>
        {!collapsed ? (
          <div>
            <h1 className="text-[17px] font-semibold tracking-[-0.02em] text-slate-900 dark:text-slate-100">Clara Care</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">Không gian chăm sóc</p>
          </div>
        ) : null}
      </div>

      <div className={collapsed ? "mb-4 flex justify-center" : "mb-4 flex justify-end px-2"}>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition hover:text-sky-700 dark:hover:text-sky-300"
          aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
        >
          <span className="material-symbols-outlined text-base">
            {collapsed ? "keyboard_double_arrow_right" : "keyboard_double_arrow_left"}
          </span>
        </button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto pr-1 clara-scrollbar">
        {groups.map((group) => (
          <section key={group.key}>
            {!collapsed ? (
              <p className="mb-2 flex items-center gap-1.5 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-500">
                <span className="material-symbols-outlined text-[14px]">{getGroupMeta(group.key).icon}</span>
                {group.label}
              </p>
            ) : null}
            <nav className="space-y-1">
              {group.items.map((item) => {
                const active = isActiveRoute(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={item.label}
                    className={[
                      "group flex items-center rounded-lg py-2 text-sm transition-colors",
                      collapsed ? "justify-center px-2" : "gap-3 px-3",
                      active
                        ? "bg-white font-semibold text-[#003461] shadow-sm dark:bg-slate-800 dark:text-blue-300"
                        : "text-[#424750] hover:bg-[#e0e3e5] hover:text-[#003461] dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-200",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-lg">{item.icon}</span>
                    {!collapsed ? <span className="truncate">{item.label}</span> : null}
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>

      <div
        className={[
          "mt-4 border-t border-slate-200/70 pt-4 dark:border-slate-800",
          collapsed ? "px-0" : "px-2",
        ].join(" ")}
      >
        {!collapsed ? (
          <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2">
            <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
              Preferences
            </p>

            <div className="mt-1.5 flex items-center gap-0.5">
              {LEGACY_ACTIONS.map((action) => (
                <Link
                  key={action.id}
                  href={action.href}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] transition hover:text-sky-700 dark:hover:text-sky-300"
                  aria-label={action.ariaLabel}
                  title={action.ariaLabel}
                >
                  <i className={`fa ${action.iconClass} text-[12px]`} aria-hidden="true" />
                </Link>
              ))}
            </div>

            <div className="mt-1.5">
              <p className="mb-0.5 text-[9px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Theme</p>
              <div className="grid grid-cols-3 gap-0.5">
                {THEME_OPTIONS.map((option) => {
                  const active = themePreference === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onThemeChange(option.value)}
                      className={[
                        "inline-flex min-h-[24px] items-center justify-center rounded-md border px-0.5 text-[9px] font-medium transition",
                        active
                          ? "border-sky-200/70 bg-sky-500/10 text-sky-700 dark:border-sky-500/25 dark:text-sky-300"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                      ].join(" ")}
                      aria-pressed={active}
                      title={option.label}
                    >
                      <i className={`fa ${option.iconClass} text-[12px]`} aria-hidden="true" />
                      <span className="sr-only">{option.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-1.5">
              <p className="mb-0.5 text-[9px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Language</p>
              <div className="grid grid-cols-2 gap-0.5">
                {LANGUAGE_OPTIONS.map((option) => {
                  const active = uiLanguage === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onLanguageChange(option.value)}
                      className={[
                        "inline-flex min-h-[24px] items-center justify-center gap-0.5 rounded-md border px-0.5 text-[9px] font-medium transition",
                        active
                          ? "border-sky-200/70 bg-sky-500/10 text-sky-700 dark:border-sky-500/25 dark:text-sky-300"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                      ].join(" ")}
                      aria-pressed={active}
                    >
                      <i className="fa fa-language text-[10px]" aria-hidden="true" />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => onThemeChange(getNextThemePreference(themePreference))}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition hover:text-sky-700 dark:hover:text-sky-300"
              aria-label="Toggle theme"
              title={`Theme: ${themePreference}`}
            >
              <i className={`fa ${getThemeIconClass(themePreference)} text-[13px]`} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => onLanguageChange(uiLanguage === "vi" ? "en" : "vi")}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[11px] font-semibold text-[var(--text-secondary)] transition hover:text-sky-700 dark:hover:text-sky-300"
              aria-label="Toggle language"
              title={`Language: ${uiLanguage.toUpperCase()}`}
            >
              <i className="fa fa-language text-[13px]" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      <div className={["mt-4 border-t border-slate-200/70 pt-4 dark:border-slate-800", collapsed ? "px-0" : "px-2"].join(" ")}>
        <div className={["flex items-center", collapsed ? "justify-center" : "gap-3"].join(" ")}>
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-300/70 text-xs font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {ROLE_LABELS[role].slice(0, 1)}
          </div>
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">CLARA Operator</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{ROLE_LABELS[role]}</p>
            </div>
          ) : null}
        </div>
        <div className={["mt-3", collapsed ? "flex justify-center" : ""].join(" ")}>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className={[
              "inline-flex min-h-[40px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]",
              collapsed ? "w-10 px-0" : "w-full gap-2 px-3",
            ].join(" ")}
            title="Dang xuat"
            aria-label="Dang xuat"
          >
            <span className="material-symbols-outlined text-[17px]">logout</span>
            {!collapsed ? <span>{isLoggingOut ? "Dang thoat..." : "Dang xuat"}</span> : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
