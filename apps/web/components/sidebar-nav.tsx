"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { beginLogout } from "@/lib/logout";
import { getGroupMeta, getGroupedNavItems, isActiveRoute, type UserRole } from "@/lib/navigation.config";

type SidebarNavProps = {
  role: UserRole;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị",
};

export default function SidebarNav({ role, collapsed = false, onToggleCollapse }: SidebarNavProps) {
  const pathname = usePathname();
  const groups = getGroupedNavItems(role);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    beginLogout();
  };

  return (
    <aside
      className={[
        "sticky top-0 hidden h-screen shrink-0 border-r border-slate-200/70 bg-[#eceef0] py-6 shadow-[inset_-1px_0_0_rgba(0,0,0,0.05)] transition-[width,padding] dark:border-slate-800 dark:bg-slate-900 lg:flex lg:flex-col",
        collapsed ? "w-[5.5rem] px-2" : "w-64 px-4",
      ].join(" ")}
    >
      <div className={["mb-8 flex items-center", collapsed ? "justify-center" : "gap-3 px-2"].join(" ")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-gradient-to-br from-cyan-400 to-cyan-700 text-slate-900">
          <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
            clinical_notes
          </span>
        </div>
        {!collapsed ? (
          <div>
            <h1 className="text-xl font-bold tracking-tighter text-[#003461] dark:text-blue-400">The Clara Care</h1>
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-500">Digital Surgeon AI</p>
          </div>
        ) : null}
      </div>

      <div className={collapsed ? "mb-4 flex justify-center" : "mb-4 flex justify-end px-2"}>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition hover:text-cyan-300"
          aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
        >
          <span className="material-symbols-outlined text-base">{collapsed ? "keyboard_double_arrow_right" : "keyboard_double_arrow_left"}</span>
        </button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto pr-1 clara-scrollbar">
        {groups.map((group) => (
          <section key={group.key}>
            {!collapsed ? (
              <p className="mb-2 flex items-center gap-1.5 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-500">
                <span className="material-symbols-outlined text-[14px]">{getGroupMeta(group.key).icon}</span>
                {group.label}
              </p>
            ) : null}
            <nav className="space-y-1">
              {group.items.map((item) => {
                const active = isActiveRoute(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={item.label}
                    className={[
                      "group flex items-center rounded-lg py-2 text-sm transition-colors",
                      collapsed ? "justify-center px-2" : "gap-3 px-3",
                      active
                        ? "bg-white font-semibold text-[#003461] shadow-sm dark:bg-slate-800 dark:text-blue-300"
                        : "text-[#424750] hover:bg-[#e0e3e5] hover:text-[#003461] dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-200",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-lg">{item.icon}</span>
                    {!collapsed ? <span className="truncate">{item.label}</span> : null}
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
      </div>

      <div className={["mt-6 border-t border-slate-200/70 pt-4 dark:border-slate-800", collapsed ? "px-0" : "px-2"].join(" ")}>
        <div className={["flex items-center", collapsed ? "justify-center" : "gap-3"].join(" ")}>
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-300/70 text-xs font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {ROLE_LABELS[role].slice(0, 1)}
          </div>
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">CLARA Operator</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{ROLE_LABELS[role]}</p>
            </div>
          ) : null}
        </div>
        <div className={["mt-3", collapsed ? "flex justify-center" : ""].join(" ")}>
          <button
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
            className={[
              "inline-flex min-h-[40px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]",
              collapsed ? "w-10 px-0" : "w-full gap-2 px-3"
            ].join(" ")}
            title="Đăng xuất"
            aria-label="Đăng xuất"
          >
            <span className="material-symbols-outlined text-[17px]">logout</span>
            {!collapsed ? <span>{isLoggingOut ? "Đang thoát..." : "Đăng xuất"}</span> : null}
          </button>
        </div>
      </div>
    </aside>
  );
}
