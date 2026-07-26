"use client";

import Link from "next/link";
import { isAxiosError } from "axios";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import AppTopbar from "@/components/navigation/app-topbar";
import TransparencyNoticeGate from "@/components/compliance/transparency-notice-gate";
import {
  clearTokens,
  getRole,
  setRole as setStoredRole,
} from "@/lib/auth-store";
import api from "@/lib/http-client";
import { beginLogout } from "@/lib/logout";
import {
  getGroupMeta,
  getGroupedNavItems,
  getRoleHomePath,
  isActiveRoute,
  isAuthenticatedUtilityRoute,
  isPublicRoute,
  isRouteAllowedForRole,
  type UserRole,
} from "@/lib/navigation.config";
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
import { activateOwnedProfile, getProfileContext } from "@/lib/profile-context-api";
import { listFamilyNotifications } from "@/lib/visit-family";
import { getPhrOnboarding } from "@/lib/phr-onboarding";

type Props = {
  children: ReactNode;
};

const THEME_OPTIONS: Array<{
  value: ThemePreference;
  label: string;
  iconClass: string;
}> = [
  { value: "light", label: "Sang", iconClass: "fa-sun-o" },
  { value: "dark", label: "Toi", iconClass: "fa-moon-o" },
  { value: "system", label: "System", iconClass: "fa-desktop" },
];

const LANGUAGE_OPTIONS: Array<{ value: UILanguage; label: string }> = [
  { value: "vi", label: "VI" },
  { value: "en", label: "EN" },
];

const WIDE_WORKSPACE_PREFIXES = [
  "/admin",
  "/research",
  "/selfmed",
  "/careguard",
  "/dashboard",
  "/council",
  "/scribe",
  "/chat",
];

const IMMERSIVE_LAYOUT_PREFIXES = ["/chat", "/research", "/council", "/scribe"];
const SIDEBAR_COLLAPSE_STORAGE_KEY = "clara_sidebar_collapsed";

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
  const [profileContext, setProfileContext] = useState<ProfileContext | null>(null);
  const [isProfileChanging, setIsProfileChanging] = useState(false);
  const [familyNotificationCount, setFamilyNotificationCount] = useState(0);

  const hideSidebar =
    isPublicRoute(pathname) || isAuthenticatedUtilityRoute(pathname);
  const isWideWorkspace = WIDE_WORKSPACE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
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
        if (context.reset_required || context.active_profile_id !== getActiveProfileId()) {
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMobileNavOpen(false);
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

  const mobileNavGroups = useMemo(() => getGroupedNavItems(role), [role]);

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
    if (!isRoleHydrated || !isSessionChecked || role !== "normal") return;
    let active = true;
    const enforceFirstRunSetup = async () => {
      try {
        const onboarding = await getPhrOnboarding();
        if (!active) return;
        if (onboarding.needs_onboarding && pathname !== "/welcome") {
          router.replace("/welcome");
          return;
        }
        if (!onboarding.needs_onboarding && pathname === "/welcome") {
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

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    setIsMobileNavOpen(false);
    beginLogout();
  };

  const handleProfileChange = async (profileId: string) => {
    if (!profileId || profileId === profileContext?.active_profile_id || isProfileChanging) return;
    const target = profileContext?.profiles.find((profile) => profile.id === profileId);
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
        Bỏ qua, tới nội dung chính
      </a>
      <TransparencyNoticeGate />
      <div
        className={[
          "relative z-[1] mx-auto flex min-h-screen w-full",
          isWideWorkspace ? "max-w-[2520px]" : "max-w-[1840px]",
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
          />

          <header className="app-command-bar sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[color:var(--shell-border)] px-4 lg:hidden">
            <button
              type="button"
              onClick={() => setIsMobileNavOpen(true)}
              aria-label="Open navigation menu"
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
              href="/chat"
              className="app-mobile-ask"
              aria-label="Hỏi CLARA"
            >
              <span
                className="material-symbols-outlined text-[18px]"
                aria-hidden="true"
              >
                auto_awesome
              </span>
            </Link>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className={[
              "app-content-canvas flex-1 px-2.5 sm:px-3",
              isImmersiveLayout
                ? isChatLayout
                  ? "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+4.2rem)] pt-0 sm:px-0 sm:pb-20 sm:pt-0 lg:px-0 lg:pb-0 lg:pt-0"
                  : "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+4.2rem)] pt-0 sm:px-0.5 sm:pb-20 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
                : "pb-[calc(env(safe-area-inset-bottom,0px)+7.5rem)] pt-5 sm:px-6 sm:pb-32 sm:pt-7 lg:px-8 lg:pb-12 lg:pt-8 xl:px-10",
            ].join(" ")}
          >
            <div
              className={[
                "w-full",
                isWideWorkspace ? "max-w-none" : "mx-auto max-w-[1440px]",
              ].join(" ")}
            >
              {children}
            </div>
          </main>
        </div>
      </div>

      {isMobileNavOpen ? (
        <div
          className="fixed inset-0 z-[70] lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation"
        >
          <button
            type="button"
            onClick={() => setIsMobileNavOpen(false)}
            aria-label="Close mobile navigation"
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-[1.5px]"
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
                    Trợ lý y tế của bạn
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsMobileNavOpen(false)}
                aria-label="Close menu"
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
              >
                <span className="material-symbols-outlined text-base">
                  close
                </span>
              </button>
            </div>

            <div className="mt-4 h-[calc(100%-126px)] space-y-4 overflow-y-auto pr-1 clara-scrollbar">
              {mobileNavGroups.map((group) => (
                <section key={group.key}>
                  <p className="mb-2 flex items-center gap-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    <span className="material-symbols-outlined text-[15px]">
                      {getGroupMeta(group.key).icon}
                    </span>
                    {group.label}
                  </p>
                  <nav className="space-y-2">
                    {group.items.map((item) => {
                      const active = isActiveRoute(pathname, item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          onClick={() => setIsMobileNavOpen(false)}
                          className={[
                            "block rounded-xl border px-3.5 py-3 transition",
                            active
                              ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)]"
                              : "border-transparent bg-transparent hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)]",
                          ].join(" ")}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="flex items-center gap-2">
                              <span
                                className={
                                  active
                                    ? "material-symbols-outlined text-[18px] text-sky-700 dark:text-sky-200"
                                    : "material-symbols-outlined text-[18px] text-[var(--text-muted)]"
                                }
                              >
                                {item.icon}
                              </span>
                              <span
                                className={
                                  active
                                    ? "text-sm font-semibold text-sky-800 dark:text-sky-100"
                                    : "text-sm font-semibold text-[var(--text-primary)]"
                                }
                              >
                                {item.label}
                              </span>
                            </span>
                            <span
                              className={`h-2 w-2 rounded-full ${
                                active
                                  ? "bg-sky-500 dark:bg-sky-300"
                                  : "bg-[var(--text-muted)]/55"
                              }`}
                            />
                          </div>
                          <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-muted)]">
                            {item.desc}
                          </p>
                        </Link>
                      );
                    })}
                  </nav>
                </section>
              ))}
            </div>

            <div className="mt-4 space-y-3 border-t border-[color:var(--shell-border)] pt-4">
              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                  Preferences
                </p>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <div
                    className="inline-flex items-center gap-0.5 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5"
                    role="group"
                    aria-label="Theme preferences"
                  >
                    <span className="sr-only">Theme</span>
                    {THEME_OPTIONS.map((option) => {
                      const active = themePreference === option.value;
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
                          aria-label={`Theme ${option.label}`}
                          aria-pressed={active}
                          title={`Theme: ${option.label}`}
                        >
                          <i
                            className={`fa ${option.iconClass} text-[13px]`}
                            aria-hidden="true"
                          />
                          <span className="sr-only">{option.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div
                    className="inline-flex items-center gap-0.5 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5"
                    role="group"
                    aria-label="Language preferences"
                  >
                    <span className="sr-only">Language</span>
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
                <span>{isLoggingOut ? "Signing out..." : "Sign out"}</span>
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      <MobileBottomNav role={role} />
    </div>
  );
}
