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

const ROLE_LABELS: Record<UILanguage, Record<UserRole, string>> = {
  vi: {
    normal: "Ng\u01B0\u1EDDi d\u00F9ng",
    researcher: "Nghi\u00EAn c\u1EE9u",
    doctor: "B\u00E1c s\u0129",
    admin: "Qu\u1EA3n tr\u1ECB",
  },
  en: {
    normal: "User",
    researcher: "Researcher",
    doctor: "Doctor",
    admin: "Admin",
  },
};

const THEME_OPTIONS: Array<{ value: ThemePreference; label: Record<UILanguage, string>; iconClass: string }> = [
  { value: "light", label: { vi: "S\u00E1ng", en: "Light" }, iconClass: "fa-sun-o" },
  { value: "dark", label: { vi: "T\u1ED1i", en: "Dark" }, iconClass: "fa-moon-o" },
  { value: "system", label: { vi: "H\u1EC7 th\u1ED1ng", en: "System" }, iconClass: "fa-desktop" },
];

const LANGUAGE_OPTIONS: Array<{ value: UILanguage; label: string }> = [
  { value: "vi", label: "VI" },
  { value: "en", label: "EN" },
];

const LEGACY_ACTIONS: Array<{ id: string; iconClass: string; ariaLabel: Record<UILanguage, string>; href: string }> = [
  { id: "notifications", iconClass: "fa-bell-o", ariaLabel: { vi: "Th\u00F4ng b\u00E1o", en: "Notifications" }, href: "/chat" },
  { id: "settings", iconClass: "fa-cog", ariaLabel: { vi: "C\u00E0i \u0111\u1EB7t", en: "Settings" }, href: "/role-select" },
  { id: "help", iconClass: "fa-life-ring", ariaLabel: { vi: "Tr\u1EE3 gi\u00FAp", en: "Help" }, href: "/huong-dan" },
];

const GROUP_LABEL_TRANSLATIONS: Record<string, Record<UILanguage, string>> = {
  core: { vi: "Kh\u00F4ng gian l\u00E0m vi\u1EC7c", en: "Workspace" },
  clinical: { vi: "L\u00E2m s\u00E0ng", en: "Clinical" },
  medication: { vi: "Thu\u1ED1c v\u00E0 an to\u00E0n", en: "Medication & Safety" },
  admin: { vi: "Qu\u1EA3n tr\u1ECB h\u1EC7 th\u1ED1ng", en: "System Admin" },
  support: { vi: "H\u1ED7 tr\u1EE3", en: "Support" },
};

const NAV_LABEL_TRANSLATIONS: Record<string, Record<UILanguage, string>> = {
  "/chat": { vi: "Chat", en: "Chat" },
  "/dashboard": { vi: "T\u1ED5ng quan", en: "Dashboard" },
  "/phr": { vi: "PHR", en: "PHR" },
  "/selfmed": { vi: "T\u1EE7 thu\u1ED1c", en: "Medicine Cabinet" },
  "/careguard": { vi: "Ki\u1EC3m tra t\u01B0\u01A1ng t\u00E1c", en: "DDI Check" },
  "/council": { vi: "H\u1ED9i ch\u1EA9n AI", en: "AI Council" },
  "/scribe": { vi: "Medical Scribe", en: "Medical Scribe" },
  "/admin/overview": { vi: "Qu\u1EA3n tr\u1ECB h\u1EC7 th\u1ED1ng", en: "System Admin" },
  "/admin/knowledge-sources": { vi: "Ngu\u1ED3n tri th\u1EE9c", en: "Knowledge Sources" },
  "/admin/answer-flow": { vi: "Lu\u1ED3ng tr\u1EA3 l\u1EDDi", en: "Answer Flow" },
  "/admin/observability": { vi: "Gi\u00E1m s\u00E1t v\u1EADn h\u00E0nh", en: "Observability" },
  "/huong-dan": { vi: "H\u01B0\u1EDBng d\u1EABn", en: "Guides" },
};

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
  const isEnglishUI = uiLanguage === "en";
  const roleLabel = ROLE_LABELS[uiLanguage][role];
  const collapseLabel = isEnglishUI ? "Collapse sidebar" : "Thu g\u1ECDn sidebar";
  const expandLabel = isEnglishUI ? "Expand sidebar" : "M\u1EDF r\u1ED9ng sidebar";
  const sidebarTitle = isEnglishUI ? "Care workspace" : "Kh\u00F4ng gian ch\u0103m s\u00F3c";
  const logoutLabel = isEnglishUI ? "Log out" : "\u0110\u0103ng xu\u1EA5t";
  const loggingOutLabel = isEnglishUI ? "Logging out..." : "\u0110ang tho\u00E1t...";
  const themeGroupLabel = isEnglishUI ? "Theme preferences" : "T\u00F9y ch\u1ECDn giao di\u1EC7n";
  const languageGroupLabel = isEnglishUI ? "Language preferences" : "T\u00F9y ch\u1ECDn ng\u00F4n ng\u1EEF";
  const localizeGroupLabel = (groupKey: string, fallback: string) =>
    GROUP_LABEL_TRANSLATIONS[groupKey]?.[uiLanguage] ?? fallback;
  const localizeItemLabel = (href: string, fallback: string) =>
    NAV_LABEL_TRANSLATIONS[href]?.[uiLanguage] ?? fallback;

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  };

  return (
    <aside
      className={[
        "sticky top-0 hidden h-screen shrink-0 border-r border-cyan-500/15 bg-[radial-gradient(120%_140%_at_10%_-10%,rgba(34,211,238,0.12)_0%,rgba(4,11,28,0.96)_44%,rgba(3,8,20,0.98)_100%)] py-4 transition-[width,padding] lg:flex lg:flex-col",
        collapsed ? "w-[5.5rem] px-2" : "w-64 px-4",
      ].join(" ")}
    >
      <div className={["mb-8 flex items-center", collapsed ? "justify-center" : "gap-3 px-2"].join(" ")}>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-cyan-400/35 bg-slate-900/60 text-cyan-100 shadow-[0_10px_28px_-22px_rgba(34,211,238,0.85)]">
          <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            clinical_notes
          </span>
        </div>
        {!collapsed ? (
          <div>
            <h1 className="text-[1.3rem] leading-none font-semibold tracking-[-0.02em] text-white">ClaraCare</h1>
            <p className="mt-1 text-sm text-slate-300">{sidebarTitle}</p>
          </div>
        ) : null}
      </div>

      <div className={["mb-4 px-2", collapsed ? "flex justify-center" : "flex items-center justify-between gap-2"].join(" ")}>
        {!collapsed ? (
          <div className="inline-flex items-center gap-1.5">
            <div className="inline-flex items-center gap-0.5 rounded-xl border border-cyan-500/20 bg-slate-700/45 p-0.5" role="group" aria-label={themeGroupLabel}>
              <span className="sr-only">Theme</span>
              {THEME_OPTIONS.map((option) => {
                const active = themePreference === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onThemeChange(option.value)}
                    className={[
                      "inline-flex h-5 w-5 items-center justify-center rounded-[5px] text-[9px] transition",
                      active ? "bg-slate-900/80 text-cyan-100 shadow-sm" : "text-slate-300 hover:text-white",
                    ].join(" ")}
                    aria-label={`Theme ${option.label[uiLanguage]}`}
                    aria-pressed={active}
                    title={`Theme: ${option.label[uiLanguage]}`}
                  >
                    <i className={`fa ${option.iconClass} text-[11px]`} aria-hidden="true" />
                    <span className="sr-only">{option.label[uiLanguage]}</span>
                  </button>
                );
              })}
            </div>

            <div className="inline-flex items-center gap-0.5 rounded-xl border border-cyan-500/20 bg-slate-700/45 p-0.5" role="group" aria-label={languageGroupLabel}>
              <span className="sr-only">Language</span>
              {LANGUAGE_OPTIONS.map((option) => {
                const active = uiLanguage === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onLanguageChange(option.value)}
                    className={[
                      "inline-flex min-h-[20px] min-w-[28px] items-center justify-center rounded-[5px] px-1 text-[9px] font-semibold transition",
                      active ? "bg-slate-900/80 text-cyan-100 shadow-sm" : "text-slate-300 hover:text-white",
                    ].join(" ")}
                    aria-label={`Language ${option.label}`}
                    aria-pressed={active}
                    title={`Language: ${option.label}`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        <button
          type="button"
          onClick={onToggleCollapse}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-cyan-500/25 bg-slate-900/60 text-slate-200 transition hover:border-cyan-300/70 hover:text-cyan-100"
          aria-label={collapsed ? expandLabel : collapseLabel}
          title={collapsed ? expandLabel : collapseLabel}
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
              <p className="mb-2 flex items-center gap-1.5 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                <span className="material-symbols-outlined text-[14px]">{getGroupMeta(group.key).icon}</span>
                {localizeGroupLabel(group.key, group.label)}
              </p>
            ) : null}
            <nav className="space-y-1">
              {group.items.map((item) => {
                const active = isActiveRoute(pathname, item.href);
                const itemLabel = localizeItemLabel(item.href, item.label);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={itemLabel}
                    className={[
                      "group flex items-center rounded-2xl py-2 text-sm transition-colors",
                      collapsed ? "justify-center px-2" : "gap-3 px-3",
                      active
                        ? "bg-cyan-400/16 font-semibold text-cyan-100 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.45)]"
                        : "text-slate-300 hover:bg-slate-800/55 hover:text-white",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-lg">{item.icon}</span>
                    {!collapsed ? <span className="truncate">{itemLabel}</span> : null}
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>

      <div className={["mt-4 border-t border-cyan-500/12 pt-4", collapsed ? "px-0" : "px-2"].join(" ")}>
        {!collapsed ? (
          <div className="flex items-center gap-1.5">
            {LEGACY_ACTIONS.map((action) => (
              <Link
                key={action.id}
                href={action.href}
                className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-cyan-500/20 bg-slate-800/55 text-slate-300 transition hover:border-cyan-300/60 hover:text-cyan-100"
                aria-label={action.ariaLabel[uiLanguage]}
                title={action.ariaLabel[uiLanguage]}
              >
                <i className={`fa ${action.iconClass} text-[12px]`} aria-hidden="true" />
              </Link>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => onThemeChange(getNextThemePreference(themePreference))}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-500/22 bg-slate-800/55 text-slate-300 transition hover:border-cyan-300/60 hover:text-cyan-100"
              aria-label={isEnglishUI ? "Toggle theme" : "\u0110\u1ED5i giao di\u1EC7n"}
              title={`${isEnglishUI ? "Theme" : "Giao di\u1EC7n"}: ${themePreference}`}
            >
              <i className={`fa ${getThemeIconClass(themePreference)} text-[13px]`} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => onLanguageChange(uiLanguage === "vi" ? "en" : "vi")}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-500/22 bg-slate-800/55 text-[11px] font-semibold text-slate-300 transition hover:border-cyan-300/60 hover:text-cyan-100"
              aria-label={isEnglishUI ? "Toggle language" : "\u0110\u1ED5i ng\u00F4n ng\u1EEF"}
              title={`${isEnglishUI ? "Language" : "Ng\u00F4n ng\u1EEF"}: ${uiLanguage.toUpperCase()}`}
            >
              <i className="fa fa-language text-[13px]" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      <div className={["mt-4 border-t border-cyan-500/12 pt-4", collapsed ? "px-0" : "px-2"].join(" ")}>
        <div className={["flex items-center", collapsed ? "justify-center" : "gap-3"].join(" ")}>
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700/75 text-xs font-bold text-cyan-100">
            {roleLabel.slice(0, 1)}
          </div>
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-100">CLARA Operator</p>
              <p className="truncate text-xs text-slate-400">{roleLabel}</p>
            </div>
          ) : null}
        </div>
        <div className={["mt-3", collapsed ? "flex justify-center" : ""].join(" ")}>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className={[
              "inline-flex min-h-[42px] items-center justify-center rounded-full border border-cyan-500/20 bg-slate-800/55 text-xs font-semibold text-slate-200 transition hover:border-cyan-300/60 hover:bg-slate-800/85",
              collapsed ? "w-10 px-0" : "w-full gap-2 px-3",
            ].join(" ")}
            title={logoutLabel}
            aria-label={logoutLabel}
          >
            <span className="material-symbols-outlined text-[17px]">logout</span>
            {!collapsed ? <span>{isLoggingOut ? loggingOutLabel : logoutLabel}</span> : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
