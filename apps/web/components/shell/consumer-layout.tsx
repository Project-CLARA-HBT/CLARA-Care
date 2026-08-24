"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import TransparencyNoticeGate from "@/components/compliance/transparency-notice-gate";
import Icon, { type IconName } from "@/components/ui/icon";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { isActiveRoute } from "@/lib/navigation.config";
import { usePreferences } from "./preference-provider";
import { useProfileContext } from "./profile-boundary";
import { useSession } from "./session-boundary";
import { ShellLayoutContext } from "./shell-context";

type ConsumerNavItem = {
  href: string;
  labelKey: UITranslationKey;
  icon: IconName;
  activeMatchPrefix?: string[];
};

const CANONICAL_CONSUMER_NAV: ConsumerNavItem[] = [
  {
    href: "/home",
    labelKey: "navigation.item.home.label",
    icon: "calendar",
    activeMatchPrefix: ["/home", "/today"],
  },
  {
    href: "/health",
    labelKey: "navigation.item.health.label",
    icon: "body",
    activeMatchPrefix: ["/health", "/phr", "/medicines", "/lifemap", "/selfmed", "/careguard"],
  },
  {
    href: "/care",
    labelKey: "navigation.item.care.label",
    icon: "clinical-notes",
    activeMatchPrefix: ["/care", "/visits"],
  },
  {
    href: "/you",
    labelKey: "navigation.item.you.label",
    icon: "user-card",
    activeMatchPrefix: ["/you", "/family", "/account"],
  },
];

export function ConsumerLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { themePreference, handleThemeChange, uiLanguage, handleLanguageChange } =
    usePreferences();
  const { role, isLoggingOut, handleLogout } = useSession();
  const {
    profileContext,
    activeProfile,
    activeProfileId,
    handleProfileChange,
    isProfileChanging,
    familyNotificationCount,
  } = useProfileContext();

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const isProfessionalRole =
    role === "doctor" || role === "researcher" || role === "admin";

  const nextTheme = themePreference === "dark" ? "light" : "dark";
  const themeLabel =
    nextTheme === "dark"
      ? t(uiLanguage, "theme.switchToDark")
      : t(uiLanguage, "theme.switchToLight");

  const isItemActive = (item: ConsumerNavItem) => {
    if (isActiveRoute(pathname, item.href)) return true;
    if (item.activeMatchPrefix) {
      return item.activeMatchPrefix.some((prefix) => isActiveRoute(pathname, prefix));
    }
    return false;
  };

  const isAskActive = isActiveRoute(pathname, "/ask") || isActiveRoute(pathname, "/chat");

  const activeProfileDisplay = activeProfile?.display_name ?? "CLARA";

  return (
    <ShellLayoutContext.Provider value="consumer">
      <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <a href="#main-content" className="skip-link">
        {t(uiLanguage, "navigation.skipToContent")}
      </a>
      <TransparencyNoticeGate />

      <div className="relative z-[1] mx-auto flex min-h-screen w-full max-w-[1920px]">
        {/* Desktop Sidebar */}
        <aside
          className={[
            "app-navigation sticky top-0 hidden h-screen shrink-0 border-r border-[color:var(--shell-border)] lg:flex lg:flex-col",
            isSidebarCollapsed ? "w-[4.5rem] px-2" : "w-64 px-3",
          ].join(" ")}
          aria-label={t(uiLanguage, "navigation.primary")}
        >
          {/* Brand Header */}
          <div
            className={[
              "flex h-[4.5rem] shrink-0 items-center border-b border-[color:var(--shell-border)]",
              isSidebarCollapsed ? "justify-center" : "gap-3 px-2",
            ].join(" ")}
          >
            <Link href="/home" className="app-brand-mark" aria-label="CLARA">
              <Icon name="clinical-notes" size={21} aria-hidden="true" />
            </Link>
            {!isSidebarCollapsed ? (
              <Link href="/home" className="min-w-0">
                <span className="block text-[17px] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                  CLARA-Care
                </span>
                <span className="block truncate text-[11px] font-medium text-[var(--text-muted)]">
                  {t(uiLanguage, "brand.healthAssistant")}
                </span>
              </Link>
            ) : null}
          </div>

          {/* Prominent Ask Button */}
          <div className="py-3">
            <Link
              href="/ask"
              className={[
                "flex items-center justify-center gap-2.5 rounded-xl font-semibold transition shadow-sm",
                isAskActive
                  ? "bg-[var(--interactive-primary-active)] text-[var(--on-primary)] ring-2 ring-[var(--interactive-primary-focus-ring)]"
                  : "bg-[var(--interactive-primary-idle)] text-[var(--on-primary)] hover:bg-[var(--interactive-primary-hover)]",
                isSidebarCollapsed ? "h-11 w-11 mx-auto" : "h-11 w-full px-4",
              ].join(" ")}
              aria-label={t(uiLanguage, "action.askClara")}
              title={t(uiLanguage, "action.askClara")}
            >
              <Icon name="chat" size={19} aria-hidden="true" />
              {!isSidebarCollapsed ? <span>{t(uiLanguage, "action.askClara")}</span> : null}
            </Link>
          </div>

          {/* Canonical 4 Nav Items */}
          <div className="clara-scrollbar flex-1 overflow-y-auto pb-4">
            <nav className="space-y-1" aria-label={t(uiLanguage, "navigation.primary")}>
              {CANONICAL_CONSUMER_NAV.map((item) => {
                const active = isItemActive(item);
                const label = t(uiLanguage, item.labelKey);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={[
                      "app-nav-item flex items-center rounded-xl transition font-medium",
                      isSidebarCollapsed ? "justify-center h-11 w-11 mx-auto px-0" : "gap-3 px-3 h-11",
                      active
                        ? "app-nav-item-active font-semibold text-[var(--text-primary)] bg-[var(--surface-active)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]",
                    ].join(" ")}
                    aria-current={active ? "page" : undefined}
                    title={label}
                  >
                    <Icon
                      name={item.icon}
                      size={20}
                      className={active ? "text-[var(--text-brand)]" : undefined}
                      aria-hidden="true"
                    />
                    {!isSidebarCollapsed ? <span className="truncate">{label}</span> : null}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Sidebar Footer */}
          <div className="border-t border-[color:var(--shell-border)] py-3">
            <div className={isSidebarCollapsed ? "flex justify-center" : "px-1"}>
              <button
                type="button"
                onClick={() => setIsSidebarCollapsed((prev) => !prev)}
                className="app-sidebar-action"
                aria-label={
                  isSidebarCollapsed
                    ? t(uiLanguage, "action.expand")
                    : t(uiLanguage, "action.collapse")
                }
                title={isSidebarCollapsed ? t(uiLanguage, "action.expand") : t(uiLanguage, "action.collapse")}
              >
                <Icon
                  name={isSidebarCollapsed ? "arrow-right" : "arrow-left"}
                  size={18}
                  aria-hidden="true"
                />
                {!isSidebarCollapsed ? (
                  <span>{t(uiLanguage, "action.collapse")}</span>
                ) : null}
              </button>
            </div>
          </div>
        </aside>

        {/* Content Canvas + Desktop Topbar */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Desktop Topbar */}
          <header className="app-command-bar sticky top-0 z-40 hidden h-[4.5rem] items-center justify-between gap-5 border-b border-[color:var(--shell-border)] px-6 lg:flex xl:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <span className="truncate text-base font-semibold text-[var(--text-primary)]">
                {activeProfileDisplay}
              </span>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <Link
                href="/huong-dan"
                className="app-topbar-icon"
                aria-label={t(uiLanguage, "help.open")}
                title={t(uiLanguage, "help.title")}
              >
                <Icon name="help" size={20} aria-hidden="true" />
              </Link>

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
                <Icon name="notifications" size={20} aria-hidden="true" />
                {familyNotificationCount > 0 ? (
                  <span
                    className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[var(--danger-500)] px-1 text-center text-[10px] font-bold leading-4 text-[var(--on-error-container)]"
                    aria-hidden="true"
                  >
                    {familyNotificationCount > 9 ? "9+" : familyNotificationCount}
                  </span>
                ) : null}
              </Link>

              <button
                type="button"
                onClick={() => handleThemeChange(nextTheme)}
                className="app-topbar-icon"
                aria-label={themeLabel}
                title={themeLabel}
              >
                <Icon name="theme" size={20} aria-hidden="true" />
              </button>

              <button
                type="button"
                onClick={() => handleLanguageChange(uiLanguage === "vi" ? "en" : "vi")}
                className="app-topbar-language"
                aria-label={t(uiLanguage, "language.change")}
                title={t(uiLanguage, "language.change")}
              >
                {uiLanguage.toUpperCase()}
              </button>

              <details className="group relative">
                <summary
                  className="app-profile-chip cursor-pointer list-none"
                  aria-label={activeProfileDisplay}
                >
                  <span className="app-profile-avatar" aria-hidden="true">
                    {activeProfileDisplay.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden text-left xl:block">
                    <span className="block max-w-36 truncate text-xs font-semibold text-[var(--text-primary)]">
                      {activeProfileDisplay}
                    </span>
                    <span className="block text-[11px] text-[var(--text-muted)]">
                      {activeProfile?.kind === "shared" ? t(uiLanguage, "profile.shared") : t(uiLanguage, "profile.account")}
                    </span>
                  </span>
                  <Icon
                    name="chevron-down"
                    size={16}
                    className="hidden text-[var(--text-muted)] transition group-open:rotate-180 xl:block"
                    aria-hidden="true"
                  />
                </summary>
                <div className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-lg">
                  <p className="px-1 text-xs font-semibold text-[var(--text-primary)]">
                    {activeProfileDisplay}
                  </p>
                  <p className="mt-0.5 px-1 text-[11px] text-[var(--text-muted)]">
                    {t(uiLanguage, "profile.account")}
                  </p>

                  {profileContext?.profiles && profileContext.profiles.length > 1 ? (
                    <label className="mt-3 block">
                      <span className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                        {t(uiLanguage, "profile.active")}
                      </span>
                      <select
                        aria-label={t(uiLanguage, "profile.active")}
                        value={activeProfileId ?? ""}
                        disabled={isProfileChanging}
                        onChange={(event) => void handleProfileChange(event.target.value)}
                        className="min-h-11 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-semibold text-[var(--text-primary)] outline-none disabled:cursor-wait"
                      >
                        {profileContext.profiles.map((p) => (
                          <option key={p.id} value={p.id} disabled={p.kind !== "self"}>
                            {p.kind === "shared" ? `${t(uiLanguage, "profile.shared")} ` : ""}
                            {p.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {isProfessionalRole ? (
                    <div className="mt-3 border-t border-[color:var(--shell-border)] pt-2">
                      <Link
                        href="/dashboard"
                        className="flex min-h-10 items-center gap-2 rounded-xl px-3 text-xs font-semibold text-[var(--text-brand)] hover:bg-[var(--surface-hover)] transition"
                      >
                        <Icon name="clinical-notes" size={16} aria-hidden="true" />
                        <span>{t(uiLanguage, "navigation.workspace.clinical")} / {t(uiLanguage, "navigation.admin")}</span>
                      </Link>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={isLoggingOut}
                    className="mt-3 flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-sm font-semibold text-[var(--status-danger-text)] transition hover:bg-[var(--status-danger-soft)] disabled:opacity-60"
                  >
                    <Icon name="arrow-right" size={18} aria-hidden="true" />
                    {isLoggingOut
                      ? t(uiLanguage, "action.signingOut")
                      : t(uiLanguage, "action.signOut")}
                  </button>
                </div>
              </details>
            </div>
          </header>

          {/* Mobile Top Header */}
          <header className="app-command-bar sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[color:var(--shell-border)] px-4 lg:hidden">
            <Link href="/home" className="flex min-w-0 items-center gap-2.5">
              <span className="app-brand-mark !h-9 !w-9">
                <Icon name="clinical-notes" size={16} aria-hidden="true" />
              </span>
              <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                {activeProfileDisplay}
              </span>
            </Link>

            <div className="flex items-center gap-1.5">
              <Link
                href="/you/sharing"
                className="app-topbar-icon relative"
                aria-label={
                  familyNotificationCount > 0
                    ? t(uiLanguage, "family.pendingTasks", { count: familyNotificationCount })
                    : t(uiLanguage, "family.title")
                }
              >
                <Icon name="notifications" size={18} aria-hidden="true" />
                {familyNotificationCount > 0 ? (
                  <span
                    className="absolute right-1 top-1 h-2 w-2 rounded-full bg-[var(--danger-500)]"
                    aria-hidden="true"
                  />
                ) : null}
              </Link>
              <Link
                href="/you"
                className="app-topbar-icon"
                aria-label={t(uiLanguage, "navigation.item.you.label")}
              >
                <Icon name="user-card" size={18} aria-hidden="true" />
              </Link>
            </div>
          </header>

          {/* Content Canvas */}
          <main
            id="main-content"
            tabIndex={-1}
            className="app-content-canvas flex-1 px-4 pb-[calc(env(safe-area-inset-bottom,0px)+5.5rem)] pt-5 sm:px-6 sm:pb-28 sm:pt-7 lg:px-12 lg:pb-12 lg:pt-8"
          >
            <div className="mx-auto w-full max-w-[1120px]">{children}</div>
          </main>
        </div>
      </div>

      {/* Mobile Bottom Navigation (5 destinations: Home, Health, Ask Center, Care, You) */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 border-t border-[color:var(--shell-border)] bg-[var(--surface-header)] pb-[env(safe-area-inset-bottom,0px)] lg:hidden"
        aria-label={t(uiLanguage, "navigation.primary")}
      >
        <div className="mx-auto max-w-2xl px-1 py-1">
          <ul className="grid grid-cols-5 gap-1">
            {/* Home */}
            <li>
              <Link
                href="/home"
                className={[
                  "focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1 text-center transition",
                  isItemActive(CANONICAL_CONSUMER_NAV[0])
                    ? "font-semibold text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-current={isItemActive(CANONICAL_CONSUMER_NAV[0]) ? "page" : undefined}
              >
                <Icon name="calendar" size={19} aria-hidden="true" />
                <span className="max-w-full truncate text-[11px] leading-tight">
                  {t(uiLanguage, "navigation.item.home.label")}
                </span>
              </Link>
            </li>

            {/* Health */}
            <li>
              <Link
                href="/health"
                className={[
                  "focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1 text-center transition",
                  isItemActive(CANONICAL_CONSUMER_NAV[1])
                    ? "font-semibold text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-current={isItemActive(CANONICAL_CONSUMER_NAV[1]) ? "page" : undefined}
              >
                <Icon name="body" size={19} aria-hidden="true" />
                <span className="max-w-full truncate text-[11px] leading-tight">
                  {t(uiLanguage, "navigation.item.health.label")}
                </span>
              </Link>
            </li>

            {/* Ask (Center Action) */}
            <li>
              <Link
                href="/ask"
                className={[
                  "focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1 text-center transition",
                  isAskActive
                    ? "font-bold text-[var(--text-brand)] bg-[var(--surface-active)]"
                    : "text-[var(--text-primary)] hover:bg-[var(--surface-muted)]",
                ].join(" ")}
                aria-current={isAskActive ? "page" : undefined}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--interactive-primary-idle)] text-[var(--on-primary)] shadow-sm">
                  <Icon name="chat" size={15} aria-hidden="true" />
                </span>
                <span className="max-w-full truncate text-[11px] font-semibold leading-tight">
                  {t(uiLanguage, "navigation.item.ask.label")}
                </span>
              </Link>
            </li>

            {/* Care */}
            <li>
              <Link
                href="/care"
                className={[
                  "focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1 text-center transition",
                  isItemActive(CANONICAL_CONSUMER_NAV[2])
                    ? "font-semibold text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-current={isItemActive(CANONICAL_CONSUMER_NAV[2]) ? "page" : undefined}
              >
                <Icon name="clinical-notes" size={19} aria-hidden="true" />
                <span className="max-w-full truncate text-[11px] leading-tight">
                  {t(uiLanguage, "navigation.item.care.label")}
                </span>
              </Link>
            </li>

            {/* You */}
            <li>
              <Link
                href="/you"
                className={[
                  "focus-ring flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1 text-center transition",
                  isItemActive(CANONICAL_CONSUMER_NAV[3])
                    ? "font-semibold text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
                aria-current={isItemActive(CANONICAL_CONSUMER_NAV[3]) ? "page" : undefined}
              >
                <Icon name="user-card" size={19} aria-hidden="true" />
                <span className="max-w-full truncate text-[11px] leading-tight">
                  {t(uiLanguage, "navigation.item.you.label")}
                </span>
              </Link>
            </li>
          </ul>
        </div>
      </nav>
    </div>
    </ShellLayoutContext.Provider>
  );
}

export default ConsumerLayout;
