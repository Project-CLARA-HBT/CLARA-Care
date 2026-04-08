"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import MobileBottomNav from "@/components/navigation/mobile-bottom-nav";
import { getRole } from "@/lib/auth-store";
import {
  getGroupedNavItems,
  getPageMeta,
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

const WIDE_WORKSPACE_PREFIXES = [
  "/admin",
  "/research",
  "/selfmed",
  "/careguard",
  "/dashboard",
  "/council",
  "/scribe",
];
const CHROME_HIDDEN_PREFIXES = ["/chat"];

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const [role, setRole] = useState<UserRole>("normal");
  const [themePreference, setThemePreference] = useState<ThemePreference>("dark");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  const hideSidebar = isPublicRoute(pathname);
  const hideChrome = CHROME_HIDDEN_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
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

  const handleThemeChange = (nextTheme: ThemePreference) => {
    setThemePreference(nextTheme);
    saveThemePreference(nextTheme);
    applyThemePreference(nextTheme);
  };

  if (hideSidebar || hideChrome) {
    return <main className="h-[100dvh] min-h-[100dvh] bg-[var(--color-bg)] text-[var(--text-primary)]">{children}</main>;
  }

  return (
    <div className="chrome-shell min-h-screen bg-[var(--color-bg)] text-[var(--text-primary)]">
      <div
        className={[
          "relative z-[1] mx-auto flex min-h-screen w-full",
          isWideWorkspace ? "max-w-[2520px]" : "max-w-[1840px]"
        ].join(" ")}
      >
        <SidebarNav role={role} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 px-[var(--workspace-gutter)] pb-2 pt-3 sm:px-[var(--workspace-gutter-lg)] sm:pt-4 lg:px-[var(--workspace-gutter-2xl)]">
            <div className="chrome-panel rounded-[22px] px-3.5 py-3.5 sm:px-5 sm:py-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex items-start gap-3">
                  <button
                    type="button"
                    onClick={() => setIsMobileNavOpen(true)}
                    aria-label="Mở menu điều hướng"
                    aria-expanded={isMobileNavOpen}
                    className="chrome-nav-link inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] lg:hidden"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-5 w-5">
                      <path d="M4 7H20" />
                      <path d="M4 12H20" />
                      <path d="M4 17H20" />
                    </svg>
                  </button>

                  <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                    Workspace
                  </p>
                  <h1 className="mt-1.5 text-xl font-semibold leading-tight text-[var(--text-primary)] sm:text-[1.65rem]">
                    {currentPage.title}
                  </h1>
                  <p className="mt-1.5 max-w-[72ch] text-sm leading-relaxed text-[var(--text-secondary)] sm:text-[15px]">
                    {currentPage.subtitle}
                  </p>
                  </div>
                </div>

                <div className="flex w-full flex-wrap items-center justify-between gap-2.5 sm:w-auto sm:justify-end sm:gap-3">
                  <div className="inline-flex min-h-11 items-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.32)] sm:min-h-12 sm:p-1.5">
                    {THEME_OPTIONS.map((option) => {
                      const active = themePreference === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => handleThemeChange(option.value)}
                          aria-pressed={active}
                          className={`min-h-[42px] min-w-[58px] rounded-xl border px-2.5 py-2 text-[13px] font-semibold transition chrome-nav-link sm:min-h-[44px] sm:min-w-[76px] sm:px-3.5 sm:text-sm ${
                            active
                              ? "border-[color:var(--shell-border-strong)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-[0_10px_24px_-18px_rgba(2,132,199,0.95)]"
                              : "border-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>

                  <span className="inline-flex min-h-[42px] w-full items-center justify-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] sm:min-h-[44px] sm:w-auto sm:px-4">
                    {ROLE_LABELS[role]}
                  </span>
                </div>
              </div>
            </div>
          </header>

          <main className="flex-1 px-[var(--workspace-gutter)] pb-[calc(env(safe-area-inset-bottom,0px)+7.5rem)] pt-[var(--workspace-gutter)] sm:px-[var(--workspace-gutter-lg)] sm:pb-32 sm:pt-[var(--workspace-gutter-lg)] lg:px-[var(--workspace-gutter-2xl)] lg:pb-10 lg:pt-[var(--workspace-gutter-lg)]">
            <div
              className={[
                "w-full",
                isWideWorkspace ? "max-w-none" : "mx-auto max-w-[1360px]"
              ].join(" ")}
            >
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
        aria-label="Menu điều hướng di động"
      >
        <button
          type="button"
          onClick={() => setIsMobileNavOpen(false)}
          aria-label="Đóng menu"
          className="absolute inset-0 bg-slate-900/50 backdrop-blur-[1.5px]"
        />
        <aside
          className={`chrome-panel absolute left-0 top-0 h-full w-[min(88vw,380px)] border-r border-[color:var(--shell-border)] px-4 pb-5 pt-4 transition duration-250 ${
            isMobileNavOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="glass-surface-2 rounded-3xl px-4 py-3.5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.19em] text-[var(--text-brand)]">
                  CLARA Care
                </p>
                <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">Điều hướng nhanh</p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">
                  Chọn phân hệ bạn muốn xử lý ngay hôm nay.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsMobileNavOpen(false)}
                aria-label="Đóng menu điều hướng"
                className="chrome-nav-link inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-4 w-4">
                  <path d="M6 6L18 18" />
                  <path d="M18 6L6 18" />
                </svg>
              </button>
            </div>
          </div>

          <div className="mt-4 h-[calc(100%-126px)] space-y-4 overflow-y-auto pr-1">
            {mobileNavGroups.map((group) => (
              <section key={group.key}>
                <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
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
                        className={`chrome-nav-link block rounded-2xl border px-3.5 py-3 transition ${
                          active
                            ? "border-[color:var(--shell-border-strong)] bg-[var(--surface-brand-soft)]"
                            : "border-transparent bg-[var(--surface-panel)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={`text-[14px] font-semibold leading-tight ${
                              active ? "text-[var(--text-brand)]" : "text-[var(--text-primary)]"
                            }`}
                          >
                            {item.label}
                          </span>
                          <span
                            className={`h-2 w-2 rounded-full ${
                              active ? "bg-[var(--text-brand)]" : "bg-[var(--text-muted)]/55"
                            }`}
                          />
                        </div>
                        <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--text-muted)]">{item.desc}</p>
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
              className="chrome-nav-link flex min-h-[46px] items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
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
