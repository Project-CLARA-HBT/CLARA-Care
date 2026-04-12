"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import { getRole } from "@/lib/auth-store";
import {
  getNavItemsByRole,
  getGroupMeta,
  getGroupedNavItems,
  getRoleHomePath,
  getPageMeta,
  getTopNavLinks,
  isActiveRoute,
  isPublicRoute,
  type UserRole
} from "@/lib/navigation.config";
import {
  applyThemePreference,
  getStoredThemePreference,
  saveThemePreference,
  type ThemePreference
} from "@/lib/theme";
import {
  hydrateUILanguagePreference,
  saveUILanguage,
  type UILanguage,
} from "@/lib/ui-language";

type Props = {
  children: ReactNode;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống",
};

const THEME_OPTIONS: Array<{ value: ThemePreference; label: string }> = [
  { value: "light", label: "Sáng" },
  { value: "dark", label: "Tối" },
  { value: "system", label: "Hệ thống" },
];

const LANGUAGE_OPTIONS: Array<{ value: UILanguage; label: string }> = [
  { value: "vi", label: "VI" },
  { value: "en", label: "EN" },
];

const NAVBAR_ACTIONS: Array<{ id: string; iconClass: string; ariaLabel: string }> = [
  { id: "notifications", iconClass: "fa-bell-o", ariaLabel: "Thông báo" },
  { id: "settings", iconClass: "fa-cog", ariaLabel: "Cài đặt" },
  { id: "help", iconClass: "fa-life-ring", ariaLabel: "Trợ giúp" },
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
const SIDEBAR_COLLAPSE_STORAGE_KEY = "clara_sidebar_collapsed";

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<UserRole>("normal");
  const [themePreference, setThemePreference] = useState<ThemePreference>("dark");
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const hideSidebar = isPublicRoute(pathname);
  const isWideWorkspace = WIDE_WORKSPACE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  useEffect(() => {
    setRole(getRole());
  }, [pathname]);

  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!isMobileNavOpen) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    if (!isMobileNavOpen) {
      return;
    }
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
    if (themePreference !== "system") {
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyThemePreference("system");

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }

    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, [themePreference]);

  const currentPage = useMemo(() => getPageMeta(pathname), [pathname]);
  const mobileNavGroups = useMemo(() => getGroupedNavItems(role), [role]);

  const topNavLinks = useMemo(() => getTopNavLinks(role), [role]);
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

  if (hideSidebar) {
    return <main className="h-[100dvh] min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">{children}</main>;
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div
        className={[
          "relative z-[1] mx-auto flex min-h-screen w-full",
          isWideWorkspace ? "max-w-[2520px]" : "max-w-[1840px]"
        ].join(" ")}
      >
        <SidebarNav role={role} collapsed={isSidebarCollapsed} onToggleCollapse={toggleSidebarCollapse} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[#c2c6d1]/20 bg-[#f7f9fb]/85 px-4 backdrop-blur-xl dark:bg-slate-950/80 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-4 lg:gap-8">
              <button
                type="button"
                onClick={() => setIsMobileNavOpen(true)}
                aria-label="Mở menu điều hướng"
                aria-expanded={isMobileNavOpen}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-white text-[var(--text-primary)] dark:bg-slate-900 lg:hidden"
              >
                <span className="material-symbols-outlined text-lg">menu</span>
              </button>
              <div className="min-w-0">
                <p className="truncate text-lg font-black text-[#003461] dark:text-blue-400">Không gian làm việc</p>
                <p className="hidden truncate text-xs text-[var(--text-muted)] md:block">
                  {currentPage.title}
                </p>
              </div>
              <nav className="hidden items-center gap-6 lg:flex">
                {topNavLinks.map((item) => {
                  const active = isActiveRoute(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={[
                        "inline-flex items-center gap-2 py-5 text-sm transition-all",
                        active
                          ? "border-b-2 border-[#003461] text-[#003461] dark:border-blue-300 dark:text-blue-300"
                          : "text-[#424750] hover:text-[#004b87] dark:text-slate-400 dark:hover:text-blue-200"
                      ].join(" ")}
                    >
                      <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                        {item.icon}
                      </span>
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
              <button
                type="button"
                onClick={toggleSidebarCollapse}
                className="hidden h-9 w-9 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition hover:text-cyan-300 lg:inline-flex"
                aria-label={isSidebarCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
                title={isSidebarCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
              >
                <span className="material-symbols-outlined text-base">{isSidebarCollapsed ? "left_panel_open" : "left_panel_close"}</span>
              </button>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <div className="relative hidden md:block">
                <i className="fa fa-search absolute left-3 top-1/2 -translate-y-1/2 text-[13px] text-[var(--text-muted)]" aria-hidden="true" />
                <input
                  placeholder="Tìm kiếm tài liệu y khoa..."
                  className="h-9 w-64 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] pl-10 pr-4 text-sm text-[var(--text-primary)] outline-none focus:border-cyan-300/70"
                />
              </div>

              <div className="hidden items-center gap-1 sm:flex">
                {NAVBAR_ACTIONS.map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--text-muted)] transition hover:bg-[var(--surface-panel)] hover:text-cyan-400"
                    aria-label={action.ariaLabel}
                  >
                    <i className={`fa ${action.iconClass} text-[15px]`} aria-hidden="true" />
                  </button>
                ))}
              </div>

              <select
                value={themePreference}
                onChange={(event) => handleThemeChange(event.target.value as ThemePreference)}
                className="h-9 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 text-xs text-[var(--text-secondary)] outline-none"
                aria-label="Đổi giao diện"
              >
                {THEME_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <select
                value={uiLanguage}
                onChange={(event) => handleLanguageChange(event.target.value as UILanguage)}
                className="h-9 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 text-xs font-semibold text-[var(--text-secondary)] outline-none"
                aria-label="Đổi ngôn ngữ"
                title="Language"
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </header>

          <main className="flex-1 px-4 pb-[calc(env(safe-area-inset-bottom,0px)+7.5rem)] pt-4 sm:px-6 sm:pb-32 sm:pt-6 lg:px-8 lg:pb-10 lg:pt-6">
            <div className={["w-full", isWideWorkspace ? "max-w-none" : "mx-auto max-w-[1360px]"].join(" ")}>
              {children}
            </div>
            <div className="mt-3 text-xs text-[var(--text-muted)]">{ROLE_LABELS[role]}</div>
          </main>
        </div>
      </div>

      <div
        className={`fixed inset-0 z-[70] transition duration-200 lg:hidden ${
          isMobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Menu điều hướng di động"
      >
        <button
          type="button"
          onClick={() => setIsMobileNavOpen(false)}
          aria-label="Đóng menu"
          className="absolute inset-0 bg-slate-900/50 backdrop-blur-[1.5px]"
        />
        <aside
          className={`absolute left-0 top-0 h-full w-[min(88vw,380px)] border-r border-[color:var(--shell-border)] bg-[#eceef0] px-4 pb-5 pt-4 transition duration-250 dark:bg-slate-900 ${
            isMobileNavOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.19em] text-[var(--text-brand)]">
                The Clara Care
              </p>
              <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Điều hướng nhanh</p>
            </div>
            <button
              type="button"
              onClick={() => setIsMobileNavOpen(false)}
              aria-label="Đóng menu điều hướng"
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
                            ? "border-cyan-300/70 bg-cyan-500/10"
                            : "border-transparent bg-[var(--surface-panel)] hover:border-[color:var(--shell-border)]"
                        ].join(" ")}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-2">
                            <span className={active ? "material-symbols-outlined text-[18px] text-cyan-300" : "material-symbols-outlined text-[18px] text-[var(--text-muted)]"}>
                              {item.icon}
                            </span>
                            <span className={active ? "text-sm font-semibold text-cyan-300" : "text-sm font-semibold text-[var(--text-primary)]"}>
                              {item.label}
                            </span>
                          </span>
                          <span className={`h-2 w-2 rounded-full ${active ? "bg-cyan-300" : "bg-[var(--text-muted)]/55"}`} />
                        </div>
                        <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-muted)]">{item.desc}</p>
                      </Link>
                    );
                  })}
                </nav>
              </section>
            ))}
          </div>

          <div className="mt-4 border-t border-[color:var(--shell-border)] pt-4">
            <Link
              href="/role-select"
              onClick={() => setIsMobileNavOpen(false)}
              className="flex min-h-[46px] items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
            >
              Đổi vai trò
            </Link>
          </div>
        </aside>
      </div>

      <MobileBottomNav role={role} />
    </div>
  );
}
