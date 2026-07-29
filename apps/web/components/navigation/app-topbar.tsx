"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getPageMeta, type UserRole } from "@/lib/navigation.config";
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

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Cá nhân",
  researcher: "Nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị",
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
  const page = getPageMeta(pathname);
  const nextTheme: ThemePreference =
    themePreference === "dark" ? "light" : "dark";
  const themeLabel =
    nextTheme === "dark"
      ? "Chuyển sang giao diện tối"
      : "Chuyển sang giao diện sáng";

  return (
    <header className="app-command-bar sticky top-0 z-40 hidden h-[4.5rem] items-center justify-between gap-5 border-b border-[color:var(--shell-border)] px-6 lg:flex xl:px-8">
      <div className="min-w-0">
        <p className="truncate text-lg font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
          {page.title}
        </p>
        <p className="mt-0.5 truncate text-xs text-[var(--text-muted)]">
          {ROLE_LABELS[role]}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-[min(0.5rem,8px)]">
        {profiles.length > 0 ? (
          <label className="hidden max-w-[17rem] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 xl:flex">
            <span className="material-symbols-outlined text-[18px] text-[var(--brand-600)]" aria-hidden="true">
              person_pin_circle
            </span>
            <span className="sr-only">Hồ sơ đang dùng</span>
            <select
              aria-label="Hồ sơ đang dùng"
              value={activeProfileId ?? ""}
              disabled={isProfileChanging || !onProfileChange}
              onChange={(event) => onProfileChange?.(event.target.value)}
              className="max-w-[12.5rem] bg-transparent text-xs font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
            >
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id} disabled={profile.kind !== "self"}>
                  {profile.kind === "shared" ? "Được chia sẻ · " : ""}{profile.display_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <Link
          href="/chat"
          className="app-ask-button"
          aria-label="Mở CLARA Chat"
        >
          <span
            className="material-symbols-outlined text-[19px]"
            aria-hidden="true"
          >
            auto_awesome
          </span>
          <span>Hỏi CLARA</span>
        </Link>

        <Link
          href="/huong-dan"
          className="app-topbar-icon"
          aria-label="Mở trung tâm hướng dẫn"
          title="Hướng dẫn"
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
              ? `${familyNotificationCount} nhiệm vụ chăm sóc được chia sẻ đang chờ`
              : "Family Circle"
          }
          title="Family Circle"
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
          aria-label="Đổi ngôn ngữ"
          title="Đổi ngôn ngữ"
        >
          {uiLanguage.toUpperCase()}
        </button>

        <div
          className="app-profile-chip"
          aria-label={`Vai trò hiện tại: ${ROLE_LABELS[role]}`}
        >
          <span className="app-profile-avatar" aria-hidden="true">
            {ROLE_LABELS[role].slice(0, 1)}
          </span>
          <span className="hidden text-left xl:block">
            <span className="block text-xs font-semibold text-[var(--text-primary)]">
              {profiles.find((profile) => profile.id === activeProfileId)?.display_name ?? "Tài khoản"}
            </span>
            <span className="block text-[11px] text-[var(--text-muted)]">
              {ROLE_LABELS[role]}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
