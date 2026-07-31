"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getPageMeta, type UserRole } from "@/lib/navigation.config";
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
}: AppTopbarProps) {
  const pathname = usePathname();
  const page = getPageMeta(pathname, uiLanguage);
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
        <p className="truncate text-lg font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
          {page.title}
        </p>
        <p className="mt-0.5 truncate text-xs text-[var(--text-muted)]">
          {roleLabel}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-[min(0.5rem,8px)]">
        {profiles.length > 0 ? (
          <label className="hidden max-w-[17rem] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 xl:flex">
            <span className="material-symbols-outlined text-[18px] text-[var(--brand-600)]" aria-hidden="true">
              person_pin_circle
            </span>
            <span className="sr-only">{t(uiLanguage, "profile.active")}</span>
            <select
              aria-label={t(uiLanguage, "profile.active")}
              value={activeProfileId ?? ""}
              disabled={isProfileChanging || !onProfileChange}
              onChange={(event) => onProfileChange?.(event.target.value)}
              className="max-w-[12.5rem] bg-transparent text-xs font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
            >
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id} disabled={profile.kind !== "self"}>
                  {profile.kind === "shared" ? t(uiLanguage, "profile.shared") : ""}{profile.display_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <Link
          href="/chat"
          className="app-ask-button"
          aria-label={t(uiLanguage, "action.askClara")}
        >
          <span
            className="material-symbols-outlined text-[19px]"
            aria-hidden="true"
          >
            auto_awesome
          </span>
          <span>{t(uiLanguage, "action.askClara")}</span>
        </Link>

        <Link
          href="/huong-dan"
          className="app-topbar-icon"
          aria-label={t(uiLanguage, "help.open")}
          title={t(uiLanguage, "help.title")}
        >
          <span
            className="material-symbols-outlined text-[20px]"
            aria-hidden="true"
          >
            help
          </span>
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
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            family_restroom
          </span>
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
          <span
            className="material-symbols-outlined text-[20px]"
            aria-hidden="true"
          >
            {themePreference === "dark" ? "light_mode" : "dark_mode"}
          </span>
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

        <div
          className="app-profile-chip"
          aria-label={t(uiLanguage, "profile.currentRole", { role: roleLabel })}
        >
          <span className="app-profile-avatar" aria-hidden="true">
            {roleLabel.slice(0, 1)}
          </span>
          <span className="hidden text-left xl:block">
            <span className="block text-xs font-semibold text-[var(--text-primary)]">
              {profiles.find((profile) => profile.id === activeProfileId)?.display_name ?? t(uiLanguage, "profile.account")}
            </span>
            <span className="block text-[11px] text-[var(--text-muted)]">
              {roleLabel}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
