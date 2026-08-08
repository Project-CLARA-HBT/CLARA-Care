"use client";

import Link from "next/link";
import { isAxiosError } from "axios";
import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import AppTopbar from "@/components/navigation/app-topbar";
import NavItem from "@/components/navigation/nav-item";
import Icon from "@/components/ui/icon";
import TransparencyNoticeGate from "@/components/compliance/transparency-notice-gate";
import {
  clearTokens,
  getRole,
  setRole as setStoredRole,
} from "@/lib/auth-store";
import api from "@/lib/http-client";
import { beginLogout } from "@/lib/logout";
import {
  getRoleHomePath,
  isActiveRoute,
  isAuthenticatedUtilityRoute,
  isPublicRoute,
  isRouteAllowedForRole,
  type UserRole,
} from "@/lib/navigation.config";
import {
  getAvailableWorkspaces,
  getWorkspaceForPath,
  getWorkspaceNavigation,
  isWorkspaceAvailable,
  type WorkspaceId,
} from "@/lib/navigation.workspaces";
import {
  applyThemePreference,
  getStoredThemePreference,
  saveThemePreference,
  type ThemePreference,
} from "@/lib/theme";
import {
  hydrateUILanguagePreference,
  saveUILanguage,
  type UILanguage,
} from "@/lib/ui-language";
import {
  getActiveProfileId,
  setActiveProfileId,
  type ProfileContext,
} from "@/lib/profile-context";
import {
  activateOwnedProfile,
  getProfileContext,
} from "@/lib/profile-context-api";
import { listFamilyNotifications } from "@/lib/visit-family";
import { getPhrOnboarding } from "@/lib/phr-onboarding";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";

type Props = {
  children: ReactNode;
};

const THEME_OPTIONS: Array<{
  value: ThemePreference;
  labelKey: UITranslationKey;
  icon: "light_mode" | "dark_mode" | "desktop_windows";
}> = [
  { value: "light", labelKey: "theme.light", icon: "light_mode" },
  { value: "dark", labelKey: "theme.dark", icon: "dark_mode" },
  { value: "system", labelKey: "theme.system", icon: "desktop_windows" },
];

const LANGUAGE_OPTIONS: Array<{
  value: UILanguage;
  label: string;
  labelKey: UITranslationKey;
}> = [
  { value: "vi", label: "VI", labelKey: "language.vi" },
  { value: "en", label: "EN", labelKey: "language.en" },
];

const IMMERSIVE_LAYOUT_PREFIXES = ["/chat", "/research", "/council", "/scribe"];
const SIDEBAR_COLLAPSE_STORAGE_KEY = "clara_sidebar_collapsed";
const WORKSPACE_STORAGE_KEY = "clara_active_workspace";

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();

  const [role, setRole] = useState<UserRole>("normal");
  const [themePreference, setThemePreference] =
    useState<ThemePreference>("light");
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isRoleHydrated, setIsRoleHydrated] = useState(false);
  const [isSessionChecked, setIsSessionChecked] = useState(false);
  const [profileContext, setProfileContext] = useState<ProfileContext | null>(
    null,
  );
  const [isProfileChanging, setIsProfileChanging] = useState(false);
  const [familyNotificationCount, setFamilyNotificationCount] = useState(0);
  const [workspace, setWorkspace] = useState<WorkspaceId>("personal");
  const mobileDialogRef = useRef<HTMLDivElement>(null);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  const hideSidebar =
    isPublicRoute(pathname) || isAuthenticatedUtilityRoute(pathname);
  const isImmersiveLayout = IMMERSIVE_LAYOUT_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isChatLayout = pathname === "/chat" || pathname.startsWith("/chat/");

  useEffect(() => {
    let active = true;
    const hydrateSession = async () => {
      if (isPublicRoute(pathname)) {
        setRole(getRole());
        setIsRoleHydrated(true);
        setIsSessionChecked(true);
        return;
      }
      // Local storage is only a presentation hint. The API session is
      // authoritative so a stale cookie or a new browser cannot silently
      // downgrade a doctor/researcher/admin to the normal route guard.
      try {
        const response = await api.get<{ role?: UserRole }>("/auth/me", {
          timeout: 15000,
        });
        const serverRole = response.data?.role;
        if (
          active &&
          (serverRole === "normal" ||
            serverRole === "researcher" ||
            serverRole === "doctor" ||
            serverRole === "admin")
        ) {
          setStoredRole(serverRole);
          setRole(serverRole);
        } else if (active) {
          setRole(getRole());
        }
      } catch (error) {
        const status = isAxiosError(error)
          ? Number(error.response?.status ?? 0)
          : 0;
        if (active && status === 401) {
          clearTokens();
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        if (active) setRole(getRole());
      } finally {
        if (active) {
          setIsRoleHydrated(true);
          setIsSessionChecked(true);
        }
      }
    };
    void hydrateSession();
    return () => {
      active = false;
    };
  }, [pathname, router]);

  useEffect(() => {
    if (hideSidebar || !isSessionChecked) {
      if (hideSidebar) {
        setProfileContext(null);
        setFamilyNotificationCount(0);
      }
      return;
    }
    let active = true;
    const loadProfileContext = async () => {
      try {
        const [context, notifications] = await Promise.all([
          getProfileContext(),
          listFamilyNotifications().catch(() => []),
        ]);
        if (!active) return;
        // A revoked/expired shared profile is resolved by the server back to a
        // safe context. Persist exactly that answer and discard old UI caches.
        if (
          context.reset_required ||
          context.active_profile_id !== getActiveProfileId()
        ) {
          setActiveProfileId(context.active_profile_id);
        }
        setProfileContext(context);
        setFamilyNotificationCount(notifications.length);
      } catch {
        // Profile context is additive. The existing authenticated shell stays
        // usable if an older API deployment does not expose this endpoint.
        if (active) {
          setProfileContext(null);
          setFamilyNotificationCount(0);
        }
      }
    };
    void loadProfileContext();
    return () => {
      active = false;
    };
  }, [hideSidebar, isSessionChecked]);

  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!isMobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    if (!isMobileNavOpen) return;
    const dialog = mobileDialogRef.current;
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]):not([data-mobile-backdrop]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMobileNavOpen(false);
        requestAnimationFrame(() => mobileTriggerRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") return;
      const controls = focusable();
      if (controls.length === 0) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isMobileNavOpen]);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setIsMobileNavOpen(false);
      }
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }

    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, []);

  useEffect(() => {
    const stored = getStoredThemePreference();
    setThemePreference(stored);
    applyThemePreference(stored);
  }, []);

  useEffect(() => {
    const stored = hydrateUILanguagePreference();
    setUiLanguage(stored);
  }, []);

  useEffect(() => {
    document.documentElement.lang = uiLanguage;
  }, [uiLanguage]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SIDEBAR_COLLAPSE_STORAGE_KEY);
      setIsSidebarCollapsed(raw === "1");
    } catch {
      setIsSidebarCollapsed(false);
    }
  }, []);

  useEffect(() => {
    if (!isRoleHydrated) return;
    let stored: WorkspaceId | undefined;
    try {
      const raw = window.localStorage.getItem(`${WORKSPACE_STORAGE_KEY}:${role}`);
      if (raw === "personal" || raw === "clinical" || raw === "research" || raw === "admin") {
        stored = raw;
      }
    } catch {
      stored = undefined;
    }
    setWorkspace(getWorkspaceForPath(pathname, role, stored));
  }, [isRoleHydrated, pathname, role]);

  useEffect(() => {
    if (themePreference !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyThemePreference("system");

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }

    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, [themePreference]);

  const workspaces = useMemo(
    () => getAvailableWorkspaces(role, uiLanguage),
    [role, uiLanguage],
  );
  const workspaceNavigation = useMemo(
    () => getWorkspaceNavigation(role, workspace, uiLanguage),
    [role, uiLanguage, workspace],
  );

  useEffect(() => {
    if (isPublicRoute(pathname)) return;
    if (!isRoleHydrated || !isSessionChecked) return;
    const allowed =
      isAuthenticatedUtilityRoute(pathname) ||
      isRouteAllowedForRole(pathname, role);
    if (allowed) return;
    router.replace(getRoleHomePath(role));
  }, [isRoleHydrated, isSessionChecked, pathname, role, router]);

  useEffect(() => {
    if (isPublicRoute(pathname)) return;
    if (!isRoleHydrated || !isSessionChecked) return;
    let active = true;
    const enforceFirstRunSetup = async () => {
      try {
        const onboarding = await getPhrOnboarding();
        if (!active) return;
        const inWelcomeFlow =
          pathname === "/welcome" || pathname.startsWith("/welcome/");
        if (onboarding.needs_onboarding && !inWelcomeFlow) {
          router.replace("/welcome/start");
          return;
        }
        if (!onboarding.needs_onboarding && inWelcomeFlow) {
          router.replace(getRoleHomePath(role));
        }
      } catch {
        // Fail open when the additive onboarding endpoint is temporarily
        // unavailable; established product surfaces remain usable.
      }
    };
    void enforceFirstRunSetup();
    return () => {
      active = false;
    };
  }, [isRoleHydrated, isSessionChecked, pathname, role, router]);

  const handleThemeChange = (nextTheme: ThemePreference) => {
    setThemePreference(nextTheme);
    saveThemePreference(nextTheme);
    applyThemePreference(nextTheme);
  };

  const handleLanguageChange = (nextLanguage: UILanguage) => {
    setUiLanguage(nextLanguage);
    saveUILanguage(nextLanguage);
  };

  const closeMobileNavigation = () => {
    setIsMobileNavOpen(false);
    requestAnimationFrame(() => mobileTriggerRef.current?.focus());
  };

  const toggleSidebarCollapse = () => {
    setIsSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(
          SIDEBAR_COLLAPSE_STORAGE_KEY,
          next ? "1" : "0",
        );
      } catch {
        // noop
      }
      return next;
    });
  };

  const handleWorkspaceChange = (nextWorkspace: WorkspaceId) => {
    if (!isWorkspaceAvailable(role, nextWorkspace)) return;
    setWorkspace(nextWorkspace);
    try {
      window.localStorage.setItem(`${WORKSPACE_STORAGE_KEY}:${role}`, nextWorkspace);
    } catch {
      // Preference persistence is optional.
    }
    setIsMobileNavOpen(false);
    const target = getWorkspaceNavigation(role, nextWorkspace, uiLanguage).workspace.homeHref;
    if (!isActiveRoute(pathname, target)) router.push(target);
  };

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    setIsMobileNavOpen(false);
    beginLogout();
  };

  const handleProfileChange = async (profileId: string) => {
    if (
      !profileId ||
      profileId === profileContext?.active_profile_id ||
      isProfileChanging
    )
      return;
    const target = profileContext?.profiles.find(
      (profile) => profile.id === profileId,
    );
    // Shared profiles are display contexts only in this release. A selection
    // cannot turn a narrow Family grant into a whole-record workspace.
    if (!target || target.kind !== "self") return;
    setIsProfileChanging(true);
    try {
      const activation = await activateOwnedProfile(profileId);
      setActiveProfileId(activation.active_profile_id);
      const context = await getProfileContext();
      setProfileContext(context);
      setIsMobileNavOpen(false);
      // Route replacement remounts feature pages, so component-local arrays
      // cannot paint the previous profile while the new context is active.
      router.replace("/today");
      router.refresh();
    } finally {
      setIsProfileChanging(false);
    }
  };

  const activeProfile = useMemo(
    () =>
      profileContext?.profiles.find(
        (profile) => profile.id === profileContext.active_profile_id,
      ) ?? null,
    [profileContext],
  );

  if (hideSidebar) {
    return (
      <main
        id="main-content"
        className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      >
        {children}
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <a href="#main-content" className="skip-link">
        {t(uiLanguage, "navigation.skipToContent")}
      </a>
      <TransparencyNoticeGate />
      <div
        className={[
          "relative z-[1] mx-auto flex min-h-screen w-full max-w-[1920px]",
        ].join(" ")}
      >
        <SidebarNav
          role={role}
          collapsed={isSidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapse}
          themePreference={themePreference}
          onThemeChange={handleThemeChange}
          uiLanguage={uiLanguage}
          onLanguageChange={handleLanguageChange}
          activeProfile={activeProfile}
          workspace={workspace}
          onWorkspaceChange={handleWorkspaceChange}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopbar
            role={role}
            themePreference={themePreference}
            onThemeChange={handleThemeChange}
            uiLanguage={uiLanguage}
            onLanguageChange={handleLanguageChange}
            profiles={profileContext?.profiles}
            activeProfileId={profileContext?.active_profile_id}
            onProfileChange={handleProfileChange}
            isProfileChanging={isProfileChanging}
            familyNotificationCount={familyNotificationCount}
            onLogout={handleLogout}
            isLoggingOut={isLoggingOut}
          />

          <header className="app-command-bar sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[color:var(--shell-border)] px-4 lg:hidden">
            <button
              ref={mobileTriggerRef}
              type="button"
              onClick={() => setIsMobileNavOpen(true)}
              aria-label={t(uiLanguage, "navigation.openMobile")}
              aria-expanded={isMobileNavOpen}
              className="app-topbar-icon shrink-0"
            >
              <span className="material-symbols-outlined text-lg">menu</span>
            </button>

            <Link
              href={getRoleHomePath(role)}
              className="flex min-w-0 items-center gap-2.5"
            >
              <span className="app-brand-mark !h-9 !w-9">
                <span
                  className="material-symbols-outlined text-[16px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  clinical_notes
                </span>
              </span>
              <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                {activeProfile?.display_name ?? "CLARA"}
              </span>
            </Link>

            <Link
              href="/family"
              className="app-topbar-icon relative"
              aria-label={familyNotificationCount > 0 ? t(uiLanguage, "family.pendingTasks", { count: familyNotificationCount }) : t(uiLanguage, "family.title")}
            >
              <Icon name="notifications" size={18} />
              {familyNotificationCount > 0 ? <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-[var(--danger-500)]" aria-hidden="true" /> : null}
            </Link>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className={[
              "app-content-canvas flex-1",
              isImmersiveLayout
                ? isChatLayout
                  ? "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+4.2rem)] pt-0 sm:px-0 sm:pb-20 sm:pt-0 lg:px-0 lg:pb-0 lg:pt-0"
                  : "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+4.2rem)] pt-0 sm:px-0.5 sm:pb-20 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
                : "px-4 pb-[calc(env(safe-area-inset-bottom,0px)+7rem)] pt-5 sm:px-6 sm:pb-32 sm:pt-7 lg:px-12 lg:pb-12 lg:pt-8",
            ].join(" ")}
          >
            <div
              className={[
                "w-full",
                // Immersive surfaces (chat/research/council/scribe) manage their
                // own full-bleed layout. Every other page shares ONE consistent
                // centered content column so page width never jumps between
                // routes.
                isImmersiveLayout ? "max-w-none" : "mx-auto max-w-[1120px]",
              ].join(" ")}
            >
              {children}
            </div>
          </main>
        </div>
      </div>

      {isMobileNavOpen ? (
        <div
          ref={mobileDialogRef}
          className="fixed inset-0 z-[70] lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={t(uiLanguage, "navigation.mobileDialog")}
        >
          <button
            type="button"
            onClick={closeMobileNavigation}
            aria-label={t(uiLanguage, "navigation.closeMobile")}
            data-mobile-backdrop="true"
            className="absolute inset-0 bg-[rgba(15,23,42,0.45)] backdrop-blur-sm"
          />
          <aside className="absolute left-0 top-0 h-full w-[min(90vw,390px)] border-r border-[color:var(--shell-border)] bg-[var(--surface-sidebar)] px-4 pb-5 pt-4 shadow-2xl">
            <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className="app-brand-mark shrink-0">
                  <span
                    className="material-symbols-outlined text-[18px]"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                    aria-hidden="true"
                  >
                    clinical_notes
                  </span>
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                    CLARA
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    {t(uiLanguage, "brand.healthAssistant")}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeMobileNavigation}
                aria-label={t(uiLanguage, "action.closeMenu")}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
              >
                <span className="material-symbols-outlined text-base">
                  close
                </span>
              </button>
            </div>

            <div className="mt-4 h-[calc(100%-126px)] space-y-5 overflow-y-auto pr-1 clara-scrollbar">
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-[var(--text-secondary)]">
                  {t(uiLanguage, "navigation.workspace.label")}
                </span>
                <select
                  value={workspace}
                  onChange={(event) => handleWorkspaceChange(event.target.value as WorkspaceId)}
                  className="min-h-11 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-sm font-semibold text-[var(--text-primary)]"
                >
                  {workspaces.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
                </select>
              </label>

              {profileContext?.profiles?.length ? (
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold text-[var(--text-secondary)]">
                    {t(uiLanguage, "profile.active")}
                  </span>
                  <select
                    value={profileContext.active_profile_id ?? ""}
                    onChange={(event) => void handleProfileChange(event.target.value)}
                    disabled={isProfileChanging}
                    className="min-h-11 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-sm font-semibold text-[var(--text-primary)]"
                  >
                    {profileContext.profiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>{profile.display_name}</option>
                    ))}
                  </select>
                </label>
              ) : null}

              <section>
                <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{workspaceNavigation.workspace.label}</p>
                <nav className="space-y-1" aria-label={workspaceNavigation.workspace.label}>
                  {workspaceNavigation.primary.map((item) => (
                    <NavItem key={item.href} item={item} active={isActiveRoute(pathname, item.href)} variant="drawer" onNavigate={closeMobileNavigation} />
                  ))}
                </nav>
              </section>

              {workspaceNavigation.secondary.length > 0 ? (
                <section>
                  <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(uiLanguage, "navigation.more")}</p>
                  <nav className="space-y-1" aria-label={t(uiLanguage, "navigation.more")}>
                    {workspaceNavigation.secondary.map((item) => (
                      <NavItem key={item.href} item={item} active={isActiveRoute(pathname, item.href)} variant="drawer" onNavigate={closeMobileNavigation} />
                    ))}
                  </nav>
                </section>
              ) : null}
            </div>

            <div className="mt-4 space-y-3 border-t border-[color:var(--shell-border)] pt-4">
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                  {t(uiLanguage, "preferences.title")}
                </p>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <div
                    className="inline-flex items-center gap-0.5 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5"
                    role="group"
                    aria-label={t(uiLanguage, "theme.preference")}
                  >
                    <span className="sr-only">
                      {t(uiLanguage, "theme.preference")}
                    </span>
                    {THEME_OPTIONS.map((option) => {
                      const active = themePreference === option.value;
                      const optionLabel = t(uiLanguage, option.labelKey);
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => handleThemeChange(option.value)}
                          className={[
                            "inline-flex h-7 w-7 items-center justify-center rounded-[6px] text-[11px] transition",
                            active
                              ? "bg-[var(--surface-panel)] text-sky-700 shadow-sm dark:text-sky-300"
                              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                          ].join(" ")}
                          aria-label={optionLabel}
                          aria-pressed={active}
                          title={optionLabel}
                        >
                          <span className="material-symbols-outlined text-[15px]" aria-hidden="true">{option.icon}</span>
                          <span className="sr-only">{optionLabel}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div
                    className="inline-flex items-center gap-0.5 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5"
                    role="group"
                    aria-label={t(uiLanguage, "language.preference")}
                  >
                    <span className="sr-only">
                      {t(uiLanguage, "language.preference")}
                    </span>
                    {LANGUAGE_OPTIONS.map((option) => {
                      const active = uiLanguage === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => handleLanguageChange(option.value)}
                          className={[
                            "inline-flex min-h-[28px] min-w-[38px] items-center justify-center rounded-[6px] px-2 text-[11px] font-semibold transition",
                            active
                              ? "bg-[var(--surface-panel)] text-sky-700 shadow-sm dark:text-sky-300"
                              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                          ].join(" ")}
                          aria-label={t(uiLanguage, option.labelKey)}
                          aria-pressed={active}
                          title={t(uiLanguage, option.labelKey)}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl border border-rose-300/70 bg-rose-500/10 px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-500/15 disabled:cursor-not-allowed disabled:opacity-70 dark:border-rose-700/70 dark:text-rose-300"
              >
                <span className="material-symbols-outlined text-[18px]">
                  logout
                </span>
                <span>
                  {isLoggingOut
                    ? t(uiLanguage, "action.signingOut")
                    : t(uiLanguage, "action.signOut")}
                </span>
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      <MobileBottomNav role={role} workspace={workspace} onOpenMore={() => setIsMobileNavOpen(true)} />
    </div>
  );
}
