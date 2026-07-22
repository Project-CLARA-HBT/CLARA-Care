"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getPageMeta, type UserRole } from "@/lib/navigation.config";
import type { ThemePreference } from "@/lib/theme";
import type { UILanguage } from "@/lib/ui-language";

type AppTopbarProps = {
  role: UserRole;
  themePreference: ThemePreference;
  onThemeChange: (value: ThemePreference) => void;
  uiLanguage: UILanguage;
  onLanguageChange: (value: UILanguage) => void;
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

      <div className="flex shrink-0 items-center gap-2">
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

        <Link
          href="/role-select"
          className="app-profile-chip"
          aria-label={`Vai trò hiện tại: ${ROLE_LABELS[role]}`}
        >
          <span className="app-profile-avatar" aria-hidden="true">
            {ROLE_LABELS[role].slice(0, 1)}
          </span>
          <span className="hidden text-left xl:block">
            <span className="block text-xs font-semibold text-[var(--text-primary)]">
              Tài khoản
            </span>
            <span className="block text-[11px] text-[var(--text-muted)]">
              {ROLE_LABELS[role]}
            </span>
          </span>
          <span
            className="material-symbols-outlined hidden text-[17px] text-[var(--text-muted)] xl:block"
            aria-hidden="true"
          >
            expand_more
          </span>
        </Link>
      </div>
    </header>
  );
}
