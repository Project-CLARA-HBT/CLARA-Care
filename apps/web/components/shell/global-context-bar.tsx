"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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

export interface CoreWorkspaceOption {
  key: "admin" | "clinical" | "research" | "personal";
  previewMode: AdminPreviewMode | null;
  role: UserRole;
  labelVi: string;
  labelEn: string;
  shortLabelVi: string;
  shortLabelEn: string;
  descVi: string;
  descEn: string;
  icon: IconName;
  badge: string;
  homePath: string;
  allowedRoles: UserRole[];
}

export const CORE_WORKSPACES: CoreWorkspaceOption[] = [
  {
    key: "admin",
    previewMode: null,
    role: "admin",
    labelVi: "Quản trị viên (Admin)",
    labelEn: "Administrator (Admin)",
    shortLabelVi: "Quản trị",
    shortLabelEn: "Admin",
    descVi: "Bàn làm việc quản trị & điều phối hệ thống",
    descEn: "Standard administration workbench",
    icon: "settings",
    badge: "Admin",
    homePath: "/admin/overview",
    allowedRoles: ["admin"],
  },
  {
    key: "clinical",
    previewMode: "clinical",
    role: "doctor",
    labelVi: "Bác sĩ Lâm sàng (Doctor / Clinical)",
    labelEn: "Doctor / Clinical",
    shortLabelVi: "Lâm sàng",
    shortLabelEn: "Clinical",
    descVi: "Trải nghiệm bác sĩ, Scribe & Council",
    descEn: "Doctor, Scribe & Council workspace",
    icon: "clinical-notes",
    badge: "Clinical",
    homePath: "/dashboard",
    allowedRoles: ["doctor", "admin"],
  },
  {
    key: "research",
    previewMode: "research",
    role: "researcher",
    labelVi: "Nhà nghiên cứu (Researcher / Evidence)",
    labelEn: "Researcher / Evidence",
    shortLabelVi: "Nghiên cứu",
    shortLabelEn: "Research",
    descVi: "Trải nghiệm tra cứu y văn & bằng chứng",
    descEn: "Living evidence & research workspace",
    icon: "search",
    badge: "Research",
    homePath: "/evidence",
    allowedRoles: ["researcher", "doctor", "admin"],
  },
  {
    key: "personal",
    previewMode: "personal",
    role: "normal",
    labelVi: "Người dùng Cá nhân (Personal / Consumer)",
    labelEn: "Personal / Consumer",
    shortLabelVi: "Cá nhân",
    shortLabelEn: "Personal",
    descVi: "Trải nghiệm người dùng cá nhân & LifeMap",
    descEn: "Consumer health & LifeMap workspace",
    icon: "user-card",
    badge: "Personal",
    homePath: "/today",
    allowedRoles: ["normal", "researcher", "doctor", "admin"],
  },
];

export const ADMIN_PREVIEW_OPTIONS = CORE_WORKSPACES;
export type AdminPreviewOption = CoreWorkspaceOption;

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
  const router = useRouter();
  const menuId = useId();

  const { themePreference, handleThemeChange, uiLanguage, handleLanguageChange } =
    usePreferences();
  const {
    role,
    effectiveRole,
    isLoggingOut,
    handleLogout,
    adminPreviewMode,
    setAdminPreviewMode,
  } = useSession();
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

  const activeWorkspace = useMemo(() => {
    if (role === "admin") {
      if (adminPreviewMode === "clinical") return CORE_WORKSPACES[1];
      if (adminPreviewMode === "research") return CORE_WORKSPACES[2];
      if (adminPreviewMode === "personal") return CORE_WORKSPACES[3];
      return CORE_WORKSPACES[0];
    }
    if (effectiveRole === "doctor") return CORE_WORKSPACES[1];
    if (effectiveRole === "researcher") return CORE_WORKSPACES[2];
    if (effectiveRole === "admin") return CORE_WORKSPACES[0];
    return CORE_WORKSPACES[3];
  }, [role, adminPreviewMode, effectiveRole]);

  const activePreviewOption = useMemo(() => {
    if (role !== "admin" || !adminPreviewMode) return null;
    return CORE_WORKSPACES.find((opt) => opt.previewMode === adminPreviewMode) ?? null;
  }, [role, adminPreviewMode]);

  const activePillIcon = activePreviewOption ? activePreviewOption.icon : activeWorkspace.icon;
  const activePillLabel = activePreviewOption
    ? uiLanguage === "vi"
      ? `Xem trước: ${activePreviewOption.shortLabelVi}`
      : `Preview: ${activePreviewOption.shortLabelEn}`
    : uiLanguage === "vi"
      ? activeWorkspace.shortLabelVi
      : activeWorkspace.shortLabelEn;

  const activePillAriaLabel = activePreviewOption
    ? uiLanguage === "vi"
      ? `Chế độ xem trước: ${activePreviewOption.shortLabelVi}`
      : `Admin preview mode: ${activePreviewOption.shortLabelEn}`
    : `Chế độ hiển thị: ${uiLanguage === "vi" ? currentModeMeta.labelVi : currentModeMeta.labelEn} · Không gian: ${uiLanguage === "vi" ? activeWorkspace.labelVi : activeWorkspace.labelEn}`;

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

  const handleSelectWorkspace = useCallback(
    (opt: CoreWorkspaceOption) => {
      if (role === "admin") {
        setAdminPreviewMode(opt.previewMode);
        router.push(opt.homePath);
      } else if (opt.allowedRoles.includes(role)) {
        router.push(opt.homePath);
      }
      const detailsElements = document.querySelectorAll("details");
      detailsElements.forEach((el) => {
        if (el.open) el.open = false;
      });
    },
    [role, setAdminPreviewMode, router],
  );

  return (
    <header
      className={[
        "app-command-bar sticky top-0 z-40 flex h-14 min-h-[52px] max-h-[60px] w-full items-center justify-between gap-3 border-b border-[color:var(--shell-border)] bg-[var(--surface-header)]/94 px-4 backdrop-blur-xl sm:px-6 lg:px-8",
        className,
      ].join(" ")}
      role="banner"
      aria-label="Thanh ngữ cảnh toàn cục"
    >
      {/* Left: Brand Mark & Workspace / Mode Switcher */}
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

        {/* Workspace & Mode Switcher Dropdown */}
        {showModeSwitcher && (
          <details className="group relative">
            <summary
              className={[
                "flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-xs font-semibold cursor-pointer list-none transition focus-visible:ring-2 focus-visible:ring-[var(--brand-500)] shadow-xs",
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
              <span className="hidden md:inline-block font-semibold">
                {activePillLabel}
              </span>
              <span
                className={[
                  "hidden sm:inline-block rounded-md px-1.5 py-0.5 text-[10px] font-bold tracking-wide",
                  activePreviewOption
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    : "bg-[var(--surface-muted)] text-[var(--text-secondary)] border border-[color:var(--shell-border)]/60",
                ].join(" ")}
              >
                {activePreviewOption ? `Preview · ${activeWorkspace.badge}` : activeWorkspace.badge}
              </span>
              <Icon
                name="chevron-down"
                size={14}
                className="text-[var(--text-muted)] transition-transform group-open:rotate-180"
                aria-hidden="true"
              />
            </summary>

            {/* Dropdown Menu */}
            <div className="absolute left-0 top-[calc(100%+0.5rem)] z-50 w-80 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/98 p-2.5 shadow-2xl backdrop-blur-2xl">
              {/* Workspace / Admin Preview Section */}
              <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] border-b border-[color:var(--shell-border)]/60 mb-1.5 flex items-center justify-between">
                <span>
                  {role === "admin"
                    ? uiLanguage === "vi"
                      ? "Chế độ xem trước (Admin Preview)"
                      : "Admin Preview & Workspaces"
                    : uiLanguage === "vi"
                      ? "Không gian làm việc (Workspaces)"
                      : "Workspaces"}
                </span>
                <span className="text-[10px] font-semibold text-[var(--text-muted)]">
                  4 Workspaces
                </span>
              </div>

              <div className="space-y-1">
                {CORE_WORKSPACES.map((opt) => {
                  const isSelected =
                    role === "admin"
                      ? adminPreviewMode === opt.previewMode
                      : activeWorkspace.key === opt.key;
                  const isAllowed = role === "admin" || opt.allowedRoles.includes(role);

                  return (
                    <button
                      key={opt.key}
                      type="button"
                      disabled={!isAllowed}
                      onClick={() => handleSelectWorkspace(opt)}
                      className={[
                        "flex w-full items-start gap-2.5 rounded-lg p-2 text-left text-xs transition",
                        isSelected
                          ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold border border-[color:var(--brand-500)]/30"
                          : isAllowed
                            ? "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                            : "opacity-40 cursor-not-allowed text-[var(--text-muted)]",
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
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="font-semibold text-[var(--text-primary)]">
                            {uiLanguage === "vi" ? opt.labelVi : opt.labelEn}
                          </span>
                          <div className="flex items-center gap-1 shrink-0">
                            <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--text-muted)] border border-[color:var(--shell-border)]/40">
                              {opt.badge}
                            </span>
                            {isSelected && (
                              <span
                                className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]"
                                aria-hidden="true"
                              />
                            )}
                          </div>
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)] font-normal mt-0.5 line-clamp-1">
                          {uiLanguage === "vi" ? opt.descVi : opt.descEn}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Shell Display Modes (5 Modes) Section */}
              <div className="mt-2.5 border-t border-[color:var(--shell-border)]/60 pt-2">
                <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] mb-1 flex items-center justify-between">
                  <span>
                    {uiLanguage === "vi"
                      ? "Chế độ giao diện (5 Shell Modes)"
                      : "Shell Display Modes"}
                  </span>
                  <span className="text-[10px] font-semibold text-[var(--text-muted)]">
                    {shell.mode.toUpperCase()}
                  </span>
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
                          const detailsElements = document.querySelectorAll("details");
                          detailsElements.forEach((el) => {
                            if (el.open) el.open = false;
                          });
                        }}
                        className={[
                          "flex w-full items-start gap-2.5 rounded-lg p-2 text-left text-xs transition",
                          isSelected
                            ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold border border-[color:var(--brand-500)]/30"
                            : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                        ].join(" ")}
                      >
                        <Icon
                          name={meta.icon}
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
                              {uiLanguage === "vi" ? meta.labelVi : meta.labelEn}
                            </span>
                            {isSelected && (
                              <span
                                className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]"
                                aria-hidden="true"
                              />
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
              </div>
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
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <p className="truncate text-xs font-bold text-[var(--text-primary)]">
                      {activeProfileDisplay}
                    </p>
                    <span
                      className={[
                        "rounded px-1.5 py-0.5 text-[10px] font-bold shrink-0",
                        activePreviewOption
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-[var(--surface-muted)] text-[var(--text-brand)] border border-[color:var(--shell-border)]/60",
                      ].join(" ")}
                    >
                      {activePreviewOption ? `Preview · ${activeWorkspace.badge}` : activeWorkspace.badge}
                    </span>
                  </div>
                  <p className="truncate text-[11px] text-[var(--text-muted)]">
                    {activeProfile?.kind === "shared"
                      ? t(uiLanguage, "profile.shared")
                      : role === "admin" && adminPreviewMode
                        ? uiLanguage === "vi"
                          ? `Admin (Xem trước: ${activeWorkspace.shortLabelVi})`
                          : `Admin (Preview: ${activeWorkspace.shortLabelEn})`
                        : role === "admin"
                          ? "Quản trị viên (Admin)"
                          : role === "doctor"
                            ? "Bác sĩ Lâm sàng (Doctor)"
                            : role === "researcher"
                              ? "Nhà nghiên cứu (Researcher)"
                              : "Người dùng cá nhân (Personal)"}
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

              {/* Quick Workspace Switcher Shortcuts */}
              <div className="mt-3 border-t border-[color:var(--shell-border)]/60 pt-2">
                <div className="flex items-center justify-between px-1 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] mb-1">
                  <span>
                    {uiLanguage === "vi" ? "Chuyển không gian" : "Quick Workspaces"}
                  </span>
                  <span className="text-[10px] font-medium text-[var(--text-muted)]">
                    {activeWorkspace.badge}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  {CORE_WORKSPACES.map((opt) => {
                    const isSelected =
                      role === "admin"
                        ? adminPreviewMode === opt.previewMode
                        : activeWorkspace.key === opt.key;
                    const isAllowed = role === "admin" || opt.allowedRoles.includes(role);

                    return (
                      <button
                        key={`quick-${opt.key}`}
                        type="button"
                        disabled={!isAllowed}
                        onClick={() => handleSelectWorkspace(opt)}
                        className={[
                          "flex items-center gap-1.5 rounded-lg p-2 text-left text-xs transition",
                          isSelected
                            ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold border border-[color:var(--brand-500)]/30 shadow-xs"
                            : isAllowed
                              ? "bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/60 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                              : "opacity-40 cursor-not-allowed bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/30 text-[var(--text-muted)]",
                        ].join(" ")}
                        title={uiLanguage === "vi" ? opt.labelVi : opt.labelEn}
                        aria-label={`Chuyển tới ${uiLanguage === "vi" ? opt.labelVi : opt.labelEn}`}
                      >
                        <Icon
                          name={opt.icon}
                          size={14}
                          className={isSelected ? "text-[var(--text-brand)]" : "text-[var(--text-muted)]"}
                          aria-hidden="true"
                        />
                        <span className="truncate flex-1 text-[11px] font-medium">
                          {uiLanguage === "vi" ? opt.shortLabelVi : opt.shortLabelEn}
                        </span>
                        {isSelected && (
                          <span
                            className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)] shrink-0"
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

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
