"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { getRoleHomePath, type UserRole } from "@/lib/navigation.config";
import { t } from "@/lib/i18n/catalog";
import { usePreferences } from "./preference-provider";
import { useProfileContext } from "./profile-boundary";
import { useSession, type AdminPreviewMode } from "./session-boundary";
import { ClaraOrb } from "./clara-orb";
import {
  useShellMode,
  SHELL_MODES_CONFIG,
  SHELL_DISPLAY_MODES,
  type ShellDisplayMode,
  type ShellActiveEntity,
} from "./shell-mode-provider";

interface AdminPreviewOption {
  key: string;
  value: AdminPreviewMode | null;
  labelVi: string;
  labelEn: string;
  shortLabelVi: string;
  shortLabelEn: string;
  descVi: string;
  descEn: string;
  icon: IconName;
}

const ADMIN_PREVIEW_OPTIONS: AdminPreviewOption[] = [
  {
    key: "admin",
    value: null,
    labelVi: "Quản trị viên (Administration)",
    labelEn: "Administration",
    shortLabelVi: "Quản trị",
    shortLabelEn: "Administration",
    descVi: "Bàn làm việc quản trị & điều phối gốc",
    descEn: "Standard administration workbench",
    icon: "settings",
  },
  {
    key: "clinical",
    value: "clinical",
    labelVi: "Lâm sàng (Clinical)",
    labelEn: "Clinical",
    shortLabelVi: "Lâm sàng",
    shortLabelEn: "Clinical",
    descVi: "Trải nghiệm bác sĩ, Scribe & Council",
    descEn: "Doctor, Scribe & Council workspace",
    icon: "clinical-notes",
  },
  {
    key: "research",
    value: "research",
    labelVi: "Nghiên cứu (Research)",
    labelEn: "Research",
    shortLabelVi: "Nghiên cứu",
    shortLabelEn: "Research",
    descVi: "Trải nghiệm tra cứu y văn & bằng chứng",
    descEn: "Living evidence & research workspace",
    icon: "search",
  },
  {
    key: "personal",
    value: "personal",
    labelVi: "Cá nhân (Personal)",
    labelEn: "Personal",
    shortLabelVi: "Cá nhân",
    shortLabelEn: "Personal",
    descVi: "Trải nghiệm người dùng cá nhân & LifeMap",
    descEn: "Consumer health & LifeMap workspace",
    icon: "user-card",
  },
];

export interface GlobalContextBarProps {
  className?: string;
  onOpenCommandPalette?: () => void;
  onOpenSearch?: () => void;
  showBrand?: boolean;
  showModeSwitcher?: boolean;
  showEntityContext?: boolean;
  showSearchTrigger?: boolean;
  showProfile?: boolean;
  showQuickToggles?: boolean;
  customEntity?: ShellActiveEntity | null;
}

export function GlobalContextBar({
  className = "",
  onOpenCommandPalette,
  onOpenSearch,
  showBrand = true,
  showModeSwitcher = true,
  showEntityContext = true,
  showSearchTrigger = true,
  showProfile = true,
  showQuickToggles = true,
  customEntity,
}: GlobalContextBarProps) {
  const pathname = usePathname();
  const menuId = useId();

  const { themePreference, handleThemeChange, uiLanguage, handleLanguageChange } =
    usePreferences();
  const { role, isLoggingOut, handleLogout, adminPreviewMode, setAdminPreviewMode } =
    useSession();
  const {
    profileContext,
    activeProfile,
    activeProfileId,
    handleProfileChange,
    isProfileChanging,
    familyNotificationCount,
  } = useProfileContext();

  const shell = useShellMode();
  const activeEntity = customEntity ?? shell.activeEntity;

  const currentModeMeta = SHELL_MODES_CONFIG[shell.mode] ?? SHELL_MODES_CONFIG.explore;
  const isProfessionalRole =
    role === "doctor" || role === "researcher" || role === "admin";

  const activePreviewOption = useMemo(() => {
    if (role !== "admin" || !adminPreviewMode) return null;
    return ADMIN_PREVIEW_OPTIONS.find((opt) => opt.value === adminPreviewMode) ?? null;
  }, [role, adminPreviewMode]);

  const activePillIcon = activePreviewOption ? activePreviewOption.icon : currentModeMeta.icon;
  const activePillLabel = activePreviewOption
    ? uiLanguage === "vi"
      ? `Xem trước: ${activePreviewOption.shortLabelVi}`
      : `Preview: ${activePreviewOption.shortLabelEn}`
    : uiLanguage === "vi"
      ? currentModeMeta.labelVi
      : currentModeMeta.labelEn;

  const activePillAriaLabel = activePreviewOption
    ? uiLanguage === "vi"
      ? `Chế độ xem trước: ${activePreviewOption.labelVi}`
      : `Admin preview mode: ${activePreviewOption.labelEn}`
    : `Chế độ hiển thị: ${uiLanguage === "vi" ? currentModeMeta.labelVi : currentModeMeta.labelEn}`;

  const nextTheme = themePreference === "dark" ? "light" : "dark";
  const themeLabel =
    nextTheme === "dark"
      ? t(uiLanguage, "theme.switchToDark")
      : t(uiLanguage, "theme.switchToLight");

  const activeProfileDisplay = activeProfile?.display_name ?? "CLARA";

  const triggerSearch = useCallback(() => {
    if (onOpenSearch) {
      onOpenSearch();
    } else if (onOpenCommandPalette) {
      onOpenCommandPalette();
    } else {
      shell.openCommandPalette();
    }
  }, [onOpenSearch, onOpenCommandPalette, shell]);

  return (
    <header
      className={[
        "app-command-bar sticky top-0 z-40 flex h-14 min-h-[52px] max-h-[60px] w-full items-center justify-between gap-3 border-b border-[color:var(--shell-border)] bg-[var(--surface-header)]/94 px-4 backdrop-blur-xl sm:px-6 lg:px-8",
        className,
      ].join(" ")}
      role="banner"
      aria-label="Thanh ngữ cảnh toàn cục"
    >
      {/* Left: Brand Mark & Shell Mode Switcher */}
      <div className="flex min-w-0 items-center gap-3">
        {/* Brand Mark */}
        {showBrand && (
          <Link
            href={getRoleHomePath(role)}
            className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
            aria-label="CLARA Care Trang chủ"
          >
            <span className="app-brand-mark !h-9 !w-9 shrink-0">
              <Icon name="clinical-notes" size={18} aria-hidden="true" />
            </span>
            <div className="hidden sm:block min-w-0">
              <span className="block text-sm font-bold tracking-tight text-[var(--text-primary)]">
                CLARA
              </span>
              <span className="block truncate text-[10px] font-medium text-[var(--text-muted)]">
                Care Platform
              </span>
            </div>
          </Link>
        )}

        {/* Separator */}
        {showBrand && showModeSwitcher && (
          <div className="hidden sm:block h-6 w-px bg-[color:var(--shell-border)]" aria-hidden="true" />
        )}

        {/* Mode Switcher Dropdown */}
        {showModeSwitcher && (
          <details className="group relative">
            <summary
              className={[
                "flex items-center gap-2 rounded-xl border px-2.5 py-1 text-xs font-semibold cursor-pointer list-none transition focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]",
                activePreviewOption
                  ? "border-amber-500/50 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] hover:bg-[var(--surface-muted)]",
              ].join(" ")}
              aria-label={activePillAriaLabel}
            >
              <Icon
                name={activePillIcon}
                size={15}
                className={activePreviewOption ? "text-amber-400" : "text-[var(--text-brand)]"}
                aria-hidden="true"
              />
              <span className="hidden md:inline-block">
                {activePillLabel}
              </span>
              <Icon
                name="chevron-down"
                size={14}
                className="text-[var(--text-muted)] transition-transform group-open:rotate-180"
                aria-hidden="true"
              />
            </summary>

            {/* Dropdown Menu */}
            <div className="absolute left-0 top-[calc(100%+0.5rem)] z-50 w-72 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/98 p-2 shadow-2xl backdrop-blur-2xl">
              <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] border-b border-[color:var(--shell-border)]/60 mb-1">
                {uiLanguage === "vi" ? "Chế độ giao diện (5 Shell Modes)" : "Shell Display Modes"}
              </div>

              <div className="space-y-1">
                {SHELL_DISPLAY_MODES.map((modeKey) => {
                  const meta = SHELL_MODES_CONFIG[modeKey];
                  const isSelected = shell.mode === modeKey;

                  return (
                    <button
                      key={modeKey}
                      type="button"
                      onClick={() => {
                        shell.setMode(modeKey);
                        // Close details dropdown by finding parent details
                        const detailsEl = document.activeElement?.closest("details");
                        if (detailsEl) detailsEl.open = false;
                      }}
                      className={[
                        "flex w-full items-start gap-2.5 rounded-lg p-2 text-left text-xs transition",
                        isSelected
                          ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                      ].join(" ")}
                    >
                      <Icon
                        name={meta.icon}
                        size={16}
                        className={isSelected ? "text-[var(--text-brand)] mt-0.5" : "text-[var(--text-muted)] mt-0.5"}
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[var(--text-primary)]">
                            {uiLanguage === "vi" ? meta.labelVi : meta.labelEn}
                          </span>
                          {isSelected && (
                            <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" aria-hidden="true" />
                          )}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)] font-normal mt-0.5 line-clamp-1">
                          {uiLanguage === "vi" ? meta.descVi : meta.descEn}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Admin Preview Experience Switcher Section */}
              {role === "admin" && (
                <div className="mt-2 border-t border-[color:var(--shell-border)]/60 pt-1">
                  <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] mb-1">
                    {uiLanguage === "vi"
                      ? "Chế độ xem trước (Admin Preview)"
                      : "Admin Preview"}
                  </div>

                  <div className="space-y-1">
                    {ADMIN_PREVIEW_OPTIONS.map((opt) => {
                      const isSelected = adminPreviewMode === opt.value;

                      return (
                        <button
                          key={opt.key}
                          type="button"
                          onClick={() => {
                            setAdminPreviewMode(opt.value);
                            const detailsEl = document.activeElement?.closest("details");
                            if (detailsEl) detailsEl.open = false;
                          }}
                          className={[
                            "flex w-full items-start gap-2.5 rounded-lg p-2 text-left text-xs transition",
                            isSelected
                              ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold"
                              : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                          ].join(" ")}
                        >
                          <Icon
                            name={opt.icon}
                            size={16}
                            className={
                              isSelected
                                ? "text-[var(--text-brand)] mt-0.5"
                                : "text-[var(--text-muted)] mt-0.5"
                            }
                            aria-hidden="true"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-[var(--text-primary)]">
                                {uiLanguage === "vi" ? opt.labelVi : opt.labelEn}
                              </span>
                              {isSelected && (
                                <span
                                  className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]"
                                  aria-hidden="true"
                                />
                              )}
                            </div>
                            <p className="text-[11px] text-[var(--text-muted)] font-normal mt-0.5 line-clamp-1">
                              {uiLanguage === "vi" ? opt.descVi : opt.descEn}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </details>
        )}

        {/* Active Entity Context Chip */}
        {showEntityContext && (
          <div className="hidden lg:flex items-center gap-2">
            {activeEntity ? (
              <div className="flex items-center gap-2 rounded-full border border-[color:var(--brand-500)]/40 bg-[var(--surface-brand-soft)] px-3 py-1 text-xs">
                <span className="h-2 w-2 rounded-full bg-[var(--brand-500)] animate-pulse" aria-hidden="true" />
                <span className="font-semibold text-[var(--text-brand)]">
                  {activeEntity.label}
                </span>
                {activeEntity.badge && (
                  <span className="rounded bg-[var(--surface-panel)] px-1.5 py-0.2 text-[10px] font-bold text-[var(--text-secondary)]">
                    {activeEntity.badge}
                  </span>
                )}
                <button
                  type="button"
                  onClick={shell.clearActiveEntity}
                  aria-label="Xóa ngữ cảnh hiện tại"
                  className="ml-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition"
                >
                  <Icon name="close" size={13} aria-hidden="true" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]">
                <Icon name="user-card" size={14} className="text-[var(--text-muted)]" aria-hidden="true" />
                <span className="truncate max-w-32">{activeProfileDisplay}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Center: Search / Ctrl+K Trigger */}
      {showSearchTrigger && (
        <div className="flex-1 max-w-md mx-2">
          <button
            type="button"
            onClick={triggerSearch}
            className="flex h-9 w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs text-[var(--text-muted)] shadow-sm hover:border-[color:var(--brand-500)]/50 hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
            aria-label="Mở tìm kiếm nhanh hoặc bảng lệnh (Ctrl+K)"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Icon name="search" size={15} aria-hidden="true" />
              <span className="truncate text-left">
                {uiLanguage === "vi" ? "Tìm kiếm hoặc lệnh..." : "Search or command..."}
              </span>
            </div>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
              <span>⌘</span>
              <span>K</span>
            </kbd>
          </button>
        </div>
      )}

      {/* Right: Quick Toggles, Notification & Profile */}
      <div className="flex shrink-0 items-center gap-2">
        {showQuickToggles && (
          <>
            {/* Help / Guide */}
            <Link
              href="/huong-dan"
              className="app-topbar-icon"
              aria-label={t(uiLanguage, "help.open")}
              title={t(uiLanguage, "help.title")}
            >
              <Icon name="help" size={18} aria-hidden="true" />
            </Link>

            {/* Notification Bell */}
            <Link
              href="/you/sharing"
              className="app-topbar-icon relative"
              aria-label={
                familyNotificationCount > 0
                  ? t(uiLanguage, "family.pendingTasks", { count: familyNotificationCount })
                  : t(uiLanguage, "family.title")
              }
              title={t(uiLanguage, "family.title")}
            >
              <Icon name="notifications" size={18} aria-hidden="true" />
              {familyNotificationCount > 0 ? (
                <span
                  className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[10px] font-bold leading-4 text-[var(--on-error-container)]"
                  aria-hidden="true"
                >
                  {familyNotificationCount > 9 ? "9+" : familyNotificationCount}
                </span>
              ) : null}
            </Link>

            {/* Theme Switcher */}
            <button
              type="button"
              onClick={() => handleThemeChange(nextTheme)}
              className="app-topbar-icon"
              aria-label={themeLabel}
              title={themeLabel}
            >
              <Icon name="theme" size={18} aria-hidden="true" />
            </button>

            {/* Language Switcher */}
            <button
              type="button"
              onClick={() => handleLanguageChange(uiLanguage === "vi" ? "en" : "vi")}
              className="app-topbar-language"
              aria-label={t(uiLanguage, "language.change")}
              title={t(uiLanguage, "language.change")}
            >
              {uiLanguage.toUpperCase()}
            </button>
          </>
        )}

        {/* User Profile Menu */}
        {showProfile && (
          <details className="group relative">
            <summary
              className="app-profile-chip cursor-pointer list-none !py-1 !px-2"
              aria-label={activeProfileDisplay}
            >
              <span className="app-profile-avatar !h-7 !w-7 !text-xs" aria-hidden="true">
                {activeProfileDisplay.slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden xl:block text-left">
                <span className="block max-w-28 truncate text-xs font-semibold text-[var(--text-primary)]">
                  {activeProfileDisplay}
                </span>
              </span>
              <Icon
                name="chevron-down"
                size={14}
                className="hidden text-[var(--text-muted)] transition-transform group-open:rotate-180 xl:block"
                aria-hidden="true"
              />
            </summary>

            <div className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/98 p-3 shadow-2xl backdrop-blur-2xl">
              <div className="flex items-center gap-2.5 pb-2 border-b border-[color:var(--shell-border)]">
                <span className="app-profile-avatar !h-9 !w-9 !text-sm" aria-hidden="true">
                  {activeProfileDisplay.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-[var(--text-primary)]">
                    {activeProfileDisplay}
                  </p>
                  <p className="truncate text-[11px] text-[var(--text-muted)] capitalize">
                    {activeProfile?.kind === "shared"
                      ? t(uiLanguage, "profile.shared")
                      : role === "normal"
                        ? "Người dùng cá nhân"
                        : `Vai trò: ${role}`}
                  </p>
                </div>
              </div>

              {/* Profile Context Switcher */}
              {profileContext?.profiles && profileContext.profiles.length > 1 && (
                <label className="mt-3 block">
                  <span className="mb-1.5 block text-xs font-semibold text-[var(--text-secondary)]">
                    {t(uiLanguage, "profile.active")}
                  </span>
                  <select
                    aria-label={t(uiLanguage, "profile.active")}
                    value={activeProfileId ?? ""}
                    disabled={isProfileChanging}
                    onChange={(event) => void handleProfileChange(event.target.value)}
                    className="min-h-10 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
                  >
                    {profileContext.profiles.map((p) => (
                      <option key={p.id} value={p.id} disabled={p.kind !== "self"}>
                        {p.kind === "shared" ? `${t(uiLanguage, "profile.shared")} ` : ""}
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {/* Professional Workspace Switcher link */}
              {isProfessionalRole && (
                <div className="mt-3 border-t border-[color:var(--shell-border)] pt-2">
                  <Link
                    href="/dashboard"
                    className="flex min-h-9 items-center gap-2 rounded-xl px-2.5 text-xs font-semibold text-[var(--text-brand)] hover:bg-[var(--surface-hover)] transition"
                  >
                    <Icon name="clinical-notes" size={15} aria-hidden="true" />
                    <span>Bàn làm việc Lâm sàng & Vận hành</span>
                  </Link>
                </div>
              )}

              {/* Logout Button */}
              <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="mt-3 flex min-h-10 w-full items-center gap-2 rounded-xl px-2.5 text-xs font-semibold text-[var(--status-danger-text)] transition hover:bg-[var(--status-danger-soft)] disabled:opacity-60"
              >
                <Icon name="arrow-right" size={16} aria-hidden="true" />
                {isLoggingOut
                  ? t(uiLanguage, "action.signingOut")
                  : t(uiLanguage, "action.signOut")}
              </button>
            </div>
          </details>
        )}
      </div>
    </header>
  );
}

export default GlobalContextBar;
