"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { beginLogout } from "@/lib/logout";
import {
  getGroupedNavItems,
  isActiveRoute,
  type UserRole,
} from "@/lib/navigation.config";
import type { ThemePreference } from "@/lib/theme";
import type { UILanguage } from "@/lib/ui-language";
import type { ProfileContextProfile } from "@/lib/profile-context";

type SidebarNavProps = {
  role: UserRole;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  themePreference: ThemePreference;
  onThemeChange: (value: ThemePreference) => void;
  uiLanguage: UILanguage;
  onLanguageChange: (value: UILanguage) => void;
  activeProfile?: ProfileContextProfile | null;
};

const GROUP_TRANSLATIONS: Record<string, Record<UILanguage, string>> = {
  core: { vi: "Chăm sóc của bạn", en: "Your care" },
  research: { vi: "Nghiên cứu", en: "Research" },
  clinical: { vi: "Lâm sàng", en: "Clinical" },
  medication: { vi: "Thuốc & an toàn", en: "Medication & safety" },
  admin: { vi: "Vận hành", en: "Operations" },
  support: { vi: "Hỗ trợ", en: "Support" },
};

const ROLE_LABELS: Record<UILanguage, Record<UserRole, string>> = {
  vi: {
    normal: "Cá nhân",
    researcher: "Nhà nghiên cứu",
    doctor: "Bác sĩ",
    admin: "Quản trị viên",
  },
  en: {
    normal: "Personal",
    researcher: "Researcher",
    doctor: "Doctor",
    admin: "Administrator",
  },
};

export default function SidebarNav({
  role,
  collapsed = false,
  onToggleCollapse,
  uiLanguage,
  activeProfile = null,
}: SidebarNavProps) {
  const pathname = usePathname();
  const groups = getGroupedNavItems(role);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const isEnglish = uiLanguage === "en";

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  };

  return (
    <aside
      className={[
        "app-navigation sticky top-0 hidden h-screen shrink-0 border-r border-[color:var(--shell-border)] lg:flex lg:flex-col",
        collapsed ? "w-[5rem] px-2" : "w-[17.5rem] px-3",
      ].join(" ")}
      aria-label={isEnglish ? "Primary navigation" : "Điều hướng chính"}
    >
      <div
        className={[
          "flex h-[4.5rem] shrink-0 items-center border-b border-[color:var(--shell-border)]",
          collapsed ? "justify-center" : "gap-3 px-2",
        ].join(" ")}
      >
        <Link href="/chat" className="app-brand-mark" aria-label="CLARA">
          <span
            className="material-symbols-outlined text-[21px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
            aria-hidden="true"
          >
            health_and_safety
          </span>
        </Link>
        {!collapsed ? (
          <Link href="/chat" className="min-w-0">
            <span className="block text-[17px] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
              CLARA
            </span>
            <span className="block truncate text-[11px] font-medium text-[var(--text-muted)]">
              Trợ lý y tế của bạn
            </span>
          </Link>
        ) : null}
      </div>

      <div className="py-4">
        <Link
          href="/chat"
          className={collapsed ? "app-new-chat !px-0" : "app-new-chat"}
          title={isEnglish ? "New conversation" : "Cuộc trò chuyện mới"}
        >
          <span
            className="material-symbols-outlined text-[19px]"
            aria-hidden="true"
          >
            add_comment
          </span>
          {!collapsed ? (
            <span>
              {isEnglish ? "New conversation" : "Cuộc trò chuyện mới"}
            </span>
          ) : null}
        </Link>
      </div>

      <div className="clara-scrollbar flex-1 space-y-5 overflow-y-auto pb-4">
        {groups.map((group) => (
          <section key={group.key}>
            {!collapsed ? (
              <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                {GROUP_TRANSLATIONS[group.key]?.[uiLanguage] ?? group.label}
              </p>
            ) : null}
            <nav
              className="space-y-1"
              aria-label={
                GROUP_TRANSLATIONS[group.key]?.[uiLanguage] ?? group.label
              }
            >
              {group.items.map((item) => {
                const active = isActiveRoute(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={[
                      "app-nav-item",
                      collapsed ? "justify-center px-0" : "gap-3 px-3",
                      active ? "app-nav-item-active" : "",
                    ].join(" ")}
                    title={item.label}
                  >
                    <span
                      className="material-symbols-outlined shrink-0 text-[20px]"
                      style={
                        active
                          ? { fontVariationSettings: "'FILL' 1" }
                          : undefined
                      }
                      aria-hidden="true"
                    >
                      {item.icon}
                    </span>
                    {!collapsed ? (
                      <span className="truncate">{item.label}</span>
                    ) : null}
                    {!collapsed && active ? (
                      <span
                        className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--brand-600)]"
                        aria-hidden="true"
                      />
                    ) : null}
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>

      <div className="border-t border-[color:var(--shell-border)] py-3">
        <div className={collapsed ? "flex justify-center" : "px-1"}>
          <div
            className={[
              "flex items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
              collapsed ? "h-11 w-11 justify-center" : "gap-3 p-2.5",
            ].join(" ")}
          >
            <span className="app-profile-avatar shrink-0" aria-hidden="true">
              {ROLE_LABELS[uiLanguage][role].slice(0, 1)}
            </span>
            {!collapsed ? (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold text-[var(--text-primary)]">
                  {activeProfile?.display_name ?? "Tài khoản của bạn"}
                </span>
                <span className="block truncate text-[11px] text-[var(--text-muted)]">
                  {activeProfile?.kind === "shared"
                    ? isEnglish
                      ? "Shared access"
                      : "Quyền được chia sẻ"
                    : ROLE_LABELS[uiLanguage][role]}
                </span>
              </span>
            ) : null}
          </div>
        </div>

        <div
          className={[
            "mt-2 flex items-center",
            collapsed ? "flex-col gap-1" : "justify-between px-1",
          ].join(" ")}
        >
          <button
            type="button"
            onClick={onToggleCollapse}
            className="app-sidebar-action"
            aria-label={
              collapsed
                ? "Mở rộng thanh điều hướng"
                : "Thu gọn thanh điều hướng"
            }
            title={collapsed ? "Mở rộng" : "Thu gọn"}
          >
            <span
              className="material-symbols-outlined text-[18px]"
              aria-hidden="true"
            >
              {collapsed ? "right_panel_open" : "left_panel_close"}
            </span>
            {!collapsed ? (
              <span>{isEnglish ? "Collapse" : "Thu gọn"}</span>
            ) : null}
          </button>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="app-sidebar-action hover:!text-[var(--status-danger-text)]"
            aria-label={isEnglish ? "Sign out" : "Đăng xuất"}
            title={isEnglish ? "Sign out" : "Đăng xuất"}
          >
            <span
              className="material-symbols-outlined text-[18px]"
              aria-hidden="true"
            >
              logout
            </span>
            {!collapsed ? (
              <span>
                {isLoggingOut ? "..." : isEnglish ? "Sign out" : "Đăng xuất"}
              </span>
            ) : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
