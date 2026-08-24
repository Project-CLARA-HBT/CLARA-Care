"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";
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
import {
  useShellMode,
  type ShellActiveEntity,
} from "./shell-mode-provider";

export interface ContextHeaderProps {
  className?: string;
  onOpenCommandPalette?: () => void;
  onOpenSearch?: () => void;
  showBrand?: boolean;
  showWorkspaceSwitcher?: boolean;
  showSearchTrigger?: boolean;
  showQuickToggles?: boolean;
  showProfile?: boolean;
  customEntity?: ShellActiveEntity | null;
  workspace?: WorkspaceId;
  role?: UserRole;
  adminPreviewMode?: AdminPreviewMode | null;
}

export function ContextHeader({
  className = "",
  onOpenCommandPalette,
  onOpenSearch,
  showBrand = true,
  showWorkspaceSwitcher = true,
  showSearchTrigger = true,
  showQuickToggles = true,
  showProfile = true,
  customEntity,
  workspace: propWorkspace,
  role: propRole,
  adminPreviewMode: propAdminPreviewMode,
}: ContextHeaderProps) {
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
  const activeEntity = customEntity ?? shell.activeEntity;

  const role: UserRole = propRole ?? sessionRole ?? "normal";
  const effectiveRole: UserRole =
    propRole ?? sessionEffectiveRole ?? role;
  const adminPreviewMode: AdminPreviewMode | null =
    propAdminPreviewMode !== undefined
      ? propAdminPreviewMode
      : sessionAdminPreviewMode ?? null;

  // Profile dropdown state
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

  // Derive active workspace
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
        setAdminPreviewMode(null);
      } else if (role === "admin" && wsId !== "admin") {
        setAdminPreviewMode(wsId as AdminPreviewMode);
      }

      setIsProfileMenuOpen(false);
      router.push(option.homeHref);
    },
    [role, adminPreviewMode, setAdminPreviewMode, router],
  );

  return (
    <ChromeSurface
      as="header"
      variant="header"
      blur="medium"
      elevation="raised"
      role="banner"
      aria-label="Thanh ngữ cảnh toàn cục"
      data-testid="context-header"
      className={[
        "sticky top-0 z-40 flex h-14 min-h-[52px] max-h-[60px] w-full items-center justify-between gap-3 px-4 sm:px-6 lg:px-8",
        className,
      ].join(" ")}
    >
      {/* Left: Brand Mark + WorkspaceSwitcher + Active Entity Chip */}
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
        {showBrand && showWorkspaceSwitcher && (
          <div
            className="hidden sm:block h-6 w-px bg-[color:var(--shell-border)]"
            aria-hidden="true"
          />
        )}

        {/* Workspace Switcher (Prominent 4-workspace pill with active workspace badge) */}
        {showWorkspaceSwitcher && (
          <WorkspaceSwitcher
            role={effectiveRole}
            currentWorkspace={activeWorkspaceId}
            adminPreviewMode={adminPreviewMode}
            onAdminPreviewChange={setAdminPreviewMode}
          />
        )}

        {/* Active Entity Context Chip */}
        {activeEntity && (
          <div className="hidden lg:flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-full border border-[color:var(--brand-500)]/40 bg-[var(--surface-brand-soft)] px-3 py-1 text-xs">
              <span
                className="h-2 w-2 rounded-full bg-[var(--brand-500)] animate-pulse"
                aria-hidden="true"
              />
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
          </div>
        )}
      </div>

      {/* Center: Omni-Search trigger / Cmd+K command palette trigger */}
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

      {/* Right: Help guide link, Notification indicator, Theme toggle, Language switch, Profile chip & dropdown */}
      <div className="flex shrink-0 items-center gap-2">
        {showQuickToggles && (
          <>
            {/* Help Guide Link (/huong-dan) */}
            <Link
              href="/huong-dan"
              className="app-topbar-icon"
              aria-label={t(uiLanguage, "help.open")}
              title={t(uiLanguage, "help.title")}
            >
              <Icon name="help" size={18} aria-hidden="true" />
            </Link>

            {/* Notification Bell / Indicator */}
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

            {/* Theme Toggle (Light/Dark) */}
            <button
              type="button"
              onClick={() => handleThemeChange(nextTheme)}
              className="app-topbar-icon"
              aria-label={themeLabel}
              title={themeLabel}
            >
              <Icon name="theme" size={18} aria-hidden="true" />
            </button>

            {/* Language Switch (VI/EN) */}
            <button
              type="button"
              onClick={() =>
                handleLanguageChange(uiLanguage === "vi" ? "en" : "vi")
              }
              className="app-topbar-language"
              aria-label={t(uiLanguage, "language.change")}
              title={t(uiLanguage, "language.change")}
            >
              {uiLanguage.toUpperCase()}
            </button>
          </>
        )}

        {/* Profile Chip & Dropdown */}
        {showProfile && (
          <div ref={profileContainerRef} className="relative">
            <button
              ref={profileTriggerRef}
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              aria-haspopup="menu"
              aria-expanded={isProfileMenuOpen}
              aria-label={activeProfileDisplay}
              data-testid="context-header-profile-trigger"
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

            {/* Dropdown Menu */}
            {isProfileMenuOpen && (
              <ChromeSurface
                variant="menu"
                elevation="overlay"
                role="menu"
                aria-label="Menu hồ sơ người dùng"
                data-testid="context-header-profile-menu"
                className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 sm:w-80 rounded-2xl p-3 border border-[color:var(--shell-border)] shadow-2xl"
              >
                {/* Profile Info Header */}
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

                {/* Multi-profile Context Switcher (if >1 profiles exist) */}
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

export default ContextHeader;
