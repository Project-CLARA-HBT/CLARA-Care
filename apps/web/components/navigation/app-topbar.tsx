"use client";

import Link from "next/link";
import Icon from "@/components/ui/icon";
import { type UserRole } from "@/lib/navigation.config";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { ThemePreference } from "@/lib/theme";
import type { UILanguage } from "@/lib/ui-language";
import type { ProfileContextProfile } from "@/lib/profile-context";

type AppTopbarProps = {
  role: UserRole;
  themePreference: ThemePreference;
  onThemeChange: (value: ThemePreference) => void;
  uiLanguage: UILanguage;
  onLanguageChange: (value: UILanguage) => void;
  profiles?: ProfileContextProfile[];
  activeProfileId?: string | null;
  onProfileChange?: (profileId: string) => void;
  isProfileChanging?: boolean;
  familyNotificationCount?: number;
  onLogout?: () => void;
  isLoggingOut?: boolean;
};

const ROLE_LABEL_KEYS: Record<UserRole, UITranslationKey> = {
  normal: "role.normal",
  researcher: "role.researcher",
  doctor: "role.doctor",
  admin: "role.admin",
};

export default function AppTopbar({
  role,
  themePreference,
  onThemeChange,
  uiLanguage,
  onLanguageChange,
  profiles = [],
  activeProfileId = null,
  onProfileChange,
  isProfileChanging = false,
  familyNotificationCount = 0,
  onLogout,
  isLoggingOut = false,
}: AppTopbarProps) {
  const roleLabel = t(uiLanguage, ROLE_LABEL_KEYS[role]);
  const nextTheme: ThemePreference =
    themePreference === "dark" ? "light" : "dark";
  const themeLabel =
    nextTheme === "dark"
      ? t(uiLanguage, "theme.switchToDark")
      : t(uiLanguage, "theme.switchToLight");

  return (
    <header className="app-command-bar sticky top-0 z-40 hidden h-[4.5rem] items-center justify-between gap-5 border-b border-[color:var(--shell-border)] px-6 lg:flex xl:px-8">
      <div className="min-w-0">
        <p className="truncate text-xl font-semibold tracking-[-0.02em] text-[var(--text-brand)]">
          CLARA-Care
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-[min(0.5rem,8px)]">
        <Link
          href="/huong-dan"
          className="app-topbar-icon"
          aria-label={t(uiLanguage, "help.open")}
          title={t(uiLanguage, "help.title")}
        >
          <Icon name="help" size={20} aria-hidden="true" />
        </Link>

        <Link
          href="/family"
          className="app-topbar-icon relative"
          aria-label={
            familyNotificationCount > 0
              ? t(uiLanguage, "family.pendingTasks", { count: familyNotificationCount })
              : t(uiLanguage, "family.title")
          }
          title={t(uiLanguage, "family.title")}
        >
          <Icon name="notifications" size={20} aria-hidden="true" />
          {familyNotificationCount > 0 ? (
            <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[10px] font-bold leading-4 text-white" aria-hidden="true">
              {familyNotificationCount > 9 ? "9+" : familyNotificationCount}
            </span>
          ) : null}
        </Link>

        <button
          type="button"
          onClick={() => onThemeChange(nextTheme)}
          className="app-topbar-icon"
          aria-label={themeLabel}
          title={themeLabel}
        >
          <Icon name="theme" size={20} aria-hidden="true" />
        </button>

        <button
          type="button"
          onClick={() => onLanguageChange(uiLanguage === "vi" ? "en" : "vi")}
          className="app-topbar-language"
          aria-label={t(uiLanguage, "language.change")}
          title={t(uiLanguage, "language.change")}
        >
          {uiLanguage.toUpperCase()}
        </button>

        <details className="group relative">
          <summary
            className="app-profile-chip cursor-pointer list-none"
            aria-label={t(uiLanguage, "profile.currentRole", { role: roleLabel })}
          >
            <span className="app-profile-avatar" aria-hidden="true">
              {roleLabel.slice(0, 1)}
            </span>
            <span className="hidden text-left xl:block">
              <span className="block max-w-36 truncate text-xs font-semibold text-[var(--text-primary)]">
                {profiles.find((profile) => profile.id === activeProfileId)?.display_name ?? t(uiLanguage, "profile.account")}
              </span>
              <span className="block text-[11px] text-[var(--text-muted)]">{roleLabel}</span>
            </span>
            <Icon name="chevron-down" size={16} className="hidden text-[var(--text-muted)] transition group-open:rotate-180 xl:block" aria-hidden="true" />
          </summary>
          <div className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
            <p className="px-1 text-xs font-semibold text-[var(--text-primary)]">{t(uiLanguage, "profile.account")}</p>
            <p className="mt-0.5 px-1 text-[11px] text-[var(--text-muted)]">{roleLabel}</p>
            {profiles.length > 0 ? (
              <label className="mt-3 block">
                <span className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">{t(uiLanguage, "profile.active")}</span>
                <select
                  aria-label={t(uiLanguage, "profile.active")}
                  value={activeProfileId ?? ""}
                  disabled={isProfileChanging || !onProfileChange}
                  onChange={(event) => onProfileChange?.(event.target.value)}
                  className="min-h-11 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id} disabled={profile.kind !== "self"}>
                      {profile.kind === "shared" ? `${t(uiLanguage, "profile.shared")} ` : ""}{profile.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button
              type="button"
              onClick={onLogout}
              disabled={!onLogout || isLoggingOut}
              className="mt-3 flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-sm font-semibold text-[var(--status-danger-text)] transition hover:bg-[var(--status-danger-soft)] disabled:opacity-60"
            >
              <Icon name="arrow-right" size={18} aria-hidden="true" />
              {isLoggingOut ? t(uiLanguage, "action.signingOut") : t(uiLanguage, "action.signOut")}
            </button>
          </div>
        </details>
      </div>
    </header>
  );
}
