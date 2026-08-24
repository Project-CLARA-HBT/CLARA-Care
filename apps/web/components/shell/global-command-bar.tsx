"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Icon from "@/components/ui/icon";
import {
  getDefaultWorkspace,
  getRoleHomePath,
  getWorkspaceForPath,
  type UserRole,
  type WorkspaceId,
} from "@/lib/navigation.config";
import { t } from "@/lib/i18n/catalog";
import { ChromeSurface } from "./chrome-surface";
import { WorkspaceSwitcher, WORKSPACE_OPTIONS } from "./workspace-switcher";
import { usePreferences } from "./preference-provider";
import { useProfileContext } from "./profile-boundary";
import { useSession, type AdminPreviewMode } from "./session-boundary";
import { useShellMode } from "./shell-mode-provider";

/**
 * GlobalCommandBar dimensions & specs (Spec v8 §4.2 & 5.1):
 * - Vertical chrome height: 52–58px.
 * - LEFT: CLARA brand mark + WorkspaceSwitcher (Personal, Clinical, Research, Admin).
 * - CENTER: Global search / Cmd+K command palette trigger.
 * - RIGHT: Help link (/huong-dan), notifications indicator, theme switcher, language switcher, Profile chip & dropdown.
 * - NO page-specific actions.
 */
export const GLOBAL_COMMAND_BAR_HEIGHT_RANGE = "52–58px";
export const GLOBAL_COMMAND_BAR_DESKTOP_HEIGHT_CLASS = "h-[54px] min-h-[52px] max-h-[58px]";

export interface GlobalCommandBarProps {
  className?: string;
  workspace?: WorkspaceId;
  role?: UserRole;
  adminPreviewMode?: AdminPreviewMode | null;
  onOpenSearch?: () => void;
  onOpenCommandPalette?: () => void;
  onWorkspaceChange?: (workspace: WorkspaceId) => void;
  onAdminPreviewChange?: (mode: AdminPreviewMode | null) => void;
  showBrand?: boolean;
  showWorkspaceSwitcher?: boolean;
  showSearchTrigger?: boolean;
  showQuickToggles?: boolean;
  showProfile?: boolean;
  showHelp?: boolean;
  showNotifications?: boolean;
  showThemeSwitcher?: boolean;
  showLanguageSwitcher?: boolean;
}

export function GlobalCommandBar({
  className = "",
  workspace: propWorkspace,
  role: propRole,
  adminPreviewMode: propAdminPreviewMode,
  onOpenSearch,
  onOpenCommandPalette,
  onWorkspaceChange,
  onAdminPreviewChange,
  showBrand = true,
  showWorkspaceSwitcher = true,
  showSearchTrigger = true,
  showQuickToggles = true,
  showProfile = true,
  showHelp = true,
  showNotifications = true,
  showThemeSwitcher = true,
  showLanguageSwitcher = true,
}: GlobalCommandBarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const { themePreference, handleThemeChange, uiLanguage, handleLanguageChange } =
    usePreferences();
  const {
    role: sessionRole,
    effectiveRole: sessionEffectiveRole,
    isLoggingOut,
    handleLogout,
    adminPreviewMode: sessionAdminPreviewMode,
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

  const role: UserRole = propRole ?? sessionRole ?? "normal";
  const effectiveRole: UserRole = propRole ?? sessionEffectiveRole ?? role;
  const adminPreviewMode: AdminPreviewMode | null =
    propAdminPreviewMode !== undefined
      ? propAdminPreviewMode
      : sessionAdminPreviewMode ?? null;

  // Profile dropdown menu state
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileContainerRef = useRef<HTMLDivElement>(null);
  const profileTriggerRef = useRef<HTMLButtonElement>(null);

  // Close profile dropdown on click outside
  useEffect(() => {
    if (!isProfileMenuOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (
        profileContainerRef.current &&
        !profileContainerRef.current.contains(event.target as Node)
      ) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isProfileMenuOpen]);

  // Close profile dropdown on Escape key
  useEffect(() => {
    if (!isProfileMenuOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsProfileMenuOpen(false);
        profileTriggerRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isProfileMenuOpen]);

  // Resolve active workspace
  const activeWorkspaceId: WorkspaceId = useMemo(() => {
    if (propWorkspace) return propWorkspace;
    if (adminPreviewMode) return adminPreviewMode;
    if (propRole) return getDefaultWorkspace(propRole);
    return getWorkspaceForPath(pathname, effectiveRole);
  }, [propWorkspace, adminPreviewMode, propRole, pathname, effectiveRole]);

  const activeWorkspaceOption =
    WORKSPACE_OPTIONS[activeWorkspaceId] ?? WORKSPACE_OPTIONS.personal;

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

  const handleSelectQuickWorkspace = useCallback(
    (wsId: WorkspaceId) => {
      const option = WORKSPACE_OPTIONS[wsId];
      if (!option) return;

      if (role === "admin" && adminPreviewMode && wsId === "admin") {
        if (onAdminPreviewChange) {
          onAdminPreviewChange(null);
        } else {
          setAdminPreviewMode(null);
        }
      } else if (role === "admin" && wsId !== "admin") {
        if (onAdminPreviewChange) {
          onAdminPreviewChange(wsId as AdminPreviewMode);
        } else {
          setAdminPreviewMode(wsId as AdminPreviewMode);
        }
      }

      onWorkspaceChange?.(wsId);
      setIsProfileMenuOpen(false);
      router.push(option.homeHref);
    },
    [role, adminPreviewMode, onAdminPreviewChange, setAdminPreviewMode, onWorkspaceChange, router],
  );

  return (
    <ChromeSurface
      as="header"
      variant="header"
      blur="medium"
      elevation="raised"
      role="banner"
      aria-label="Thanh lệnh toàn cục"
      data-testid="global-command-bar"
      className={[
        "sticky top-0 z-40 flex h-14 min-h-[52px] max-h-[58px] w-full items-center justify-between gap-3 px-4 sm:px-6 lg:px-8 border-b border-[color:var(--shell-border)] bg-[var(--surface-header)]/94 backdrop-blur-xl",
        className,
      ].join(" ")}
    >
      {/* LEFT: CLARA Brand Mark + WorkspaceSwitcher (Personal, Clinical, Research, Admin) */}
      <div className="flex min-w-0 items-center gap-3">
        {showBrand && (
          <Link
            href={getRoleHomePath(role)}
            className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
            aria-label="CLARA Care Trang chủ"
            data-testid="global-command-bar-brand"
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

        {showBrand && showWorkspaceSwitcher && (
          <div
            className="hidden sm:block h-6 w-px bg-[color:var(--shell-border)]"
            aria-hidden="true"
          />
        )}

        {showWorkspaceSwitcher && (
          <WorkspaceSwitcher
            role={effectiveRole}
            currentWorkspace={activeWorkspaceId}
            adminPreviewMode={adminPreviewMode}
            onAdminPreviewChange={onAdminPreviewChange ?? setAdminPreviewMode}
            onWorkspaceChange={onWorkspaceChange}
          />
        )}
      </div>

      {/* CENTER: Global Search / Cmd+K Command Palette Trigger */}
      {showSearchTrigger && (
        <div className="flex-1 max-w-md mx-2">
          <button
            type="button"
            onClick={triggerSearch}
            data-testid="global-command-bar-search-trigger"
            className="flex h-9 w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-xs text-[var(--text-muted)] shadow-sm hover:border-[color:var(--brand-500)]/50 hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
            aria-label="Mở tìm kiếm nhanh hoặc bảng lệnh (Ctrl+K)"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Icon name="search" size={15} aria-hidden="true" />
              <span className="truncate text-left">
                {uiLanguage === "vi"
                  ? "Tìm kiếm hoặc lệnh..."
                  : "Search or command..."}
              </span>
            </div>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
              <span>⌘</span>
              <span>K</span>
            </kbd>
          </button>
        </div>
      )}

      {/* RIGHT: Help Link (/huong-dan), Notifications Indicator, Theme Switcher, Language Switcher, Profile Chip & Dropdown */}
      <div className="flex shrink-0 items-center gap-2">
        {showQuickToggles && (
          <>
            {/* Help Link (/huong-dan) */}
            {showHelp && (
              <Link
                href="/huong-dan"
                className="app-topbar-icon"
                aria-label={t(uiLanguage, "help.open")}
                title={t(uiLanguage, "help.title")}
                data-testid="global-command-bar-help-link"
              >
                <Icon name="help" size={18} aria-hidden="true" />
              </Link>
            )}

            {/* Notifications Indicator */}
            {showNotifications && (
              <Link
                href="/you/sharing"
                className="app-topbar-icon relative"
                aria-label={
                  familyNotificationCount > 0
                    ? t(uiLanguage, "family.pendingTasks", {
                        count: familyNotificationCount,
                      })
                    : t(uiLanguage, "family.title")
                }
                title={t(uiLanguage, "family.title")}
                data-testid="global-command-bar-notifications-link"
              >
                <Icon name="notifications" size={18} aria-hidden="true" />
                {familyNotificationCount > 0 ? (
                  <span
                    className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[10px] font-bold leading-4 text-[var(--on-error-container)]"
                    aria-hidden="true"
                    data-testid="global-command-bar-notification-badge"
                  >
                    {familyNotificationCount > 9 ? "9+" : familyNotificationCount}
                  </span>
                ) : null}
              </Link>
            )}

            {/* Theme Switcher */}
            {showThemeSwitcher && (
              <button
                type="button"
                onClick={() => handleThemeChange(nextTheme)}
                className="app-topbar-icon"
                aria-label={themeLabel}
                title={themeLabel}
                data-testid="global-command-bar-theme-toggle"
              >
                <Icon name="theme" size={18} aria-hidden="true" />
              </button>
            )}

            {/* Language Switcher */}
            {showLanguageSwitcher && (
              <button
                type="button"
                onClick={() =>
                  handleLanguageChange(uiLanguage === "vi" ? "en" : "vi")
                }
                className="app-topbar-language"
                aria-label={t(uiLanguage, "language.change")}
                title={t(uiLanguage, "language.change")}
                data-testid="global-command-bar-language-toggle"
              >
                {uiLanguage.toUpperCase()}
              </button>
            )}
          </>
        )}

        {/* User Profile Chip & Dropdown */}
        {showProfile && (
          <div ref={profileContainerRef} className="relative">
            <button
              ref={profileTriggerRef}
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              aria-haspopup="menu"
              aria-expanded={isProfileMenuOpen}
              aria-label={activeProfileDisplay}
              data-testid="global-command-bar-profile-trigger"
              className="app-profile-chip cursor-pointer !py-1 !px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]"
            >
              <span
                className="app-profile-avatar !h-7 !w-7 !text-xs"
                aria-hidden="true"
              >
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
                className={[
                  "hidden text-[var(--text-muted)] transition-transform duration-200 xl:block",
                  isProfileMenuOpen ? "rotate-180 text-[var(--text-primary)]" : "",
                ].join(" ")}
                aria-hidden="true"
              />
            </button>

            {/* Dropdown Menu Panel */}
            {isProfileMenuOpen && (
              <ChromeSurface
                variant="menu"
                elevation="overlay"
                role="menu"
                aria-label="Menu hồ sơ người dùng"
                data-testid="global-command-bar-profile-menu"
                className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 sm:w-80 rounded-2xl p-3 border border-[color:var(--shell-border)] shadow-2xl"
              >
                {/* Profile Header */}
                <div className="flex items-center gap-2.5 pb-2.5 border-b border-[color:var(--shell-border)]">
                  <span
                    className="app-profile-avatar !h-9 !w-9 !text-sm shrink-0"
                    aria-hidden="true"
                  >
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
                          adminPreviewMode
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-[var(--surface-muted)] text-[var(--text-brand)] border border-[color:var(--shell-border)]/60",
                        ].join(" ")}
                      >
                        {adminPreviewMode
                          ? `Preview · ${activeWorkspaceOption.badge}`
                          : activeWorkspaceOption.badge}
                      </span>
                    </div>
                    <p className="truncate text-[11px] text-[var(--text-muted)] mt-0.5">
                      {activeProfile?.kind === "shared"
                        ? t(uiLanguage, "profile.shared")
                        : role === "admin" && adminPreviewMode
                          ? uiLanguage === "vi"
                            ? `Admin (Xem trước: ${activeWorkspaceOption.shortLabel})`
                            : `Admin (Preview: ${activeWorkspaceOption.shortLabel})`
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

                {/* Profile Context Switcher (when multiple profiles exist) */}
                {profileContext?.profiles &&
                  profileContext.profiles.length > 1 && (
                    <label className="mt-3 block">
                      <span className="mb-1.5 block text-xs font-semibold text-[var(--text-secondary)]">
                        {t(uiLanguage, "profile.active")}
                      </span>
                      <select
                        aria-label={t(uiLanguage, "profile.active")}
                        value={activeProfileId ?? ""}
                        disabled={isProfileChanging}
                        onChange={(event) =>
                          void handleProfileChange(event.target.value)
                        }
                        className="min-h-10 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
                      >
                        {profileContext.profiles.map((p) => (
                          <option
                            key={p.id}
                            value={p.id}
                            disabled={p.kind !== "self"}
                          >
                            {p.kind === "shared"
                              ? `${t(uiLanguage, "profile.shared")} `
                              : ""}
                            {p.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                {/* Quick Workspace Switcher Shortcuts */}
                <div className="mt-3 border-t border-[color:var(--shell-border)]/60 pt-2.5">
                  <div className="flex items-center justify-between px-1 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)] mb-1.5">
                    <span>
                      {uiLanguage === "vi"
                        ? "Chuyển không gian"
                        : "Quick Workspaces"}
                    </span>
                    <span className="text-[10px] font-medium text-[var(--text-muted)]">
                      {activeWorkspaceOption.badge}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {Object.values(WORKSPACE_OPTIONS).map((opt) => {
                      const isSelected =
                        role === "admin"
                          ? adminPreviewMode === opt.id ||
                            (adminPreviewMode === null && opt.id === "admin")
                          : activeWorkspaceId === opt.id;
                      const isAllowed =
                        role === "admin" || opt.allowedRoles.includes(role);

                      return (
                        <button
                          key={`quick-${opt.id}`}
                          type="button"
                          disabled={!isAllowed}
                          onClick={() => handleSelectQuickWorkspace(opt.id)}
                          className={[
                            "flex items-center gap-1.5 rounded-lg p-2 text-left text-xs transition",
                            isSelected
                              ? "bg-[var(--surface-active)] text-[var(--text-brand)] font-semibold border border-[color:var(--brand-500)]/30 shadow-xs"
                              : isAllowed
                                ? "bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/60 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                                : "opacity-40 cursor-not-allowed bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/30 text-[var(--text-muted)]",
                          ].join(" ")}
                          title={opt.label}
                          aria-label={`Chuyển tới ${opt.label}`}
                        >
                          <Icon
                            name={opt.icon}
                            size={14}
                            className={
                              isSelected
                                ? "text-[var(--text-brand)]"
                                : "text-[var(--text-muted)]"
                            }
                            aria-hidden="true"
                          />
                          <span className="truncate flex-1 text-[11px] font-medium">
                            {opt.shortLabel}
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
              </ChromeSurface>
            )}
          </div>
        )}
      </div>
    </ChromeSurface>
  );
}

export default GlobalCommandBar;
