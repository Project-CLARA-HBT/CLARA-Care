"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import { getRole } from "@/lib/auth-store";
import { beginLogout } from "@/lib/logout";
import {
  getNavItemsByRole,
  getGroupMeta,
  getGroupedNavItems,
  getRoleHomePath,
  isActiveRoute,
  isPublicRoute,
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

type Props = {
  children: ReactNode;
};

const THEME_OPTIONS: Array<{ value: ThemePreference; label: string }> = [
  { value: "light", label: "Sang" },
  { value: "dark", label: "Toi" },
  { value: "system", label: "System" },
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
  const [themePreference, setThemePreference] = useState<ThemePreference>("dark");
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const hideSidebar = isPublicRoute(pathname);
  const isWideWorkspace = WIDE_WORKSPACE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  const isImmersiveLayout = IMMERSIVE_LAYOUT_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  useEffect(() => {
    setRole(getRole());
  }, [pathname]);

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
  const roleNavItems = useMemo(() => getNavItemsByRole(role), [role]);

  useEffect(() => {
    if (isPublicRoute(pathname)) return;
    const allowed = roleNavItems.some((item) => isActiveRoute(pathname, item.href));
    if (allowed) return;
    router.replace(getRoleHomePath(role));
  }, [pathname, role, roleNavItems, router]);

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
        window.localStorage.setItem(SIDEBAR_COLLAPSE_STORAGE_KEY, next ? "1" : "0");
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

  if (hideSidebar) {
    return (
      <main className="h-[100dvh] min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
        {children}
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
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
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/92 px-4 backdrop-blur lg:hidden">
            <button
              type="button"
              onClick={() => setIsMobileNavOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={isMobileNavOpen}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
            >
              <span className="material-symbols-outlined text-lg">menu</span>
            </button>

            <Link href={getRoleHomePath(role)} className="flex min-w-0 items-center gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl border border-slate-200/80 bg-white/90 text-[#2f4d67] shadow-sm dark:border-slate-700/80 dark:bg-slate-800/90 dark:text-slate-100">
                <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                  clinical_notes
                </span>
              </span>
              <span className="truncate text-sm font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                Clara Care
              </span>
            </Link>

            <span className="inline-flex min-w-[38px] justify-center rounded-full border border-[color:var(--shell-border)] px-2 py-1 text-[10px] font-semibold text-[var(--text-secondary)]">
              {uiLanguage.toUpperCase()}
            </span>
          </header>

          <main
            className={[
              "flex-1 px-2.5 sm:px-3",
              isImmersiveLayout
                ? "px-0 pb-[calc(env(safe-area-inset-bottom,0px)+4.2rem)] pt-0 sm:px-0.5 sm:pb-20 sm:pt-0 lg:px-0.5 lg:pb-1 lg:pt-0"
                : "pb-[calc(env(safe-area-inset-bottom,0px)+7.5rem)] pt-4 sm:px-6 sm:pb-32 sm:pt-6 lg:px-8 lg:pb-10 lg:pt-6",
            ].join(" ")}
          >
            <div className={["w-full", isWideWorkspace ? "max-w-none" : "mx-auto max-w-[1360px]"].join(" ")}>
              {children}
            </div>
          </main>
        </div>
      </div>

      <div
        className={`fixed inset-0 z-[70] transition duration-200 lg:hidden ${
          isMobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
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
        <aside
          className={`absolute left-0 top-0 h-full w-[min(88vw,380px)] border-r border-[color:var(--shell-border)] bg-[#eceef0] px-4 pb-5 pt-4 transition duration-250 dark:bg-slate-900 ${
            isMobileNavOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-slate-200/80 bg-white/90 text-[#2f4d67] shadow-sm dark:border-slate-700/80 dark:bg-slate-800/90 dark:text-slate-100">
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
                  Clara Care
                </p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">Không gian chăm sóc</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsMobileNavOpen(false)}
              aria-label="Close menu"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>

          <div className="mt-4 h-[calc(100%-126px)] space-y-4 overflow-y-auto pr-1 clara-scrollbar">
            {mobileNavGroups.map((group) => (
              <section key={group.key}>
                <p className="mb-2 flex items-center gap-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                  <span className="material-symbols-outlined text-[15px]">{getGroupMeta(group.key).icon}</span>
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
                          "block rounded-xl border px-3.5 py-2.5 transition",
                          active
                            ? "border-sky-200/80 bg-sky-500/10 dark:border-sky-500/30 dark:bg-sky-500/10"
                            : "border-transparent bg-[var(--surface-panel)] hover:border-[color:var(--shell-border)]",
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
                              active ? "bg-sky-500 dark:bg-sky-300" : "bg-[var(--text-muted)]/55"
                            }`}
                          />
                        </div>
                        <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-muted)]">{item.desc}</p>
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
              <div className="mt-1.5">
                <p className="mb-0.5 text-[9px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Theme</p>
                <select
                  value={themePreference}
                  onChange={(event) => handleThemeChange(event.target.value as ThemePreference)}
                  className="h-8 w-full rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-[11px] text-[var(--text-secondary)] outline-none"
                  aria-label="Theme"
                >
                  {THEME_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="mt-1.5">
                <p className="mb-0.5 text-[9px] uppercase tracking-[0.08em] text-[var(--text-muted)]">Language</p>
                <div className="grid grid-cols-2 gap-0.5">
                  {LANGUAGE_OPTIONS.map((option) => {
                    const active = uiLanguage === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => handleLanguageChange(option.value)}
                        className={[
                          "inline-flex min-h-[30px] items-center justify-center rounded-md border text-[11px] font-medium transition",
                          active
                            ? "border-sky-200/70 bg-sky-500/10 text-sky-700 dark:border-sky-500/25 dark:text-sky-300"
                            : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
                        ].join(" ")}
                        aria-pressed={active}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <Link
              href="/role-select"
              onClick={() => setIsMobileNavOpen(false)}
              className="flex min-h-[46px] items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
            >
              Switch role
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl border border-rose-300/70 bg-rose-500/10 px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-500/15 disabled:cursor-not-allowed disabled:opacity-70 dark:border-rose-700/70 dark:text-rose-300"
            >
              <span className="material-symbols-outlined text-[18px]">logout</span>
              <span>{isLoggingOut ? "Signing out..." : "Sign out"}</span>
            </button>
          </div>
        </aside>
      </div>

      <MobileBottomNav role={role} />
    </div>
  );
}
