"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import AdminAppLauncherModal from "@/components/admin/admin-app-launcher-modal";
import {
  PRIMARY_ADMIN_TABS,
  getAdminToolById,
} from "@/components/admin/admin-tools-registry";

/**
 * AdminCommandStrip dimensions & specs (Spec v8 §4.5 & 5.4):
 * - Compact top navigation (44–48px) replacing old 90px cards:
 *   Tổng quan (/admin/overview) | Nguồn tri thức (/admin/knowledge-sources) | Luồng suy luận (/admin/answer-flow) | Giám sát (/admin/observability) | Phân tích (/admin/analytics) | Thêm (Tất cả công cụ).
 * - Triggers AdminAppLauncherModal / Command Palette on All Tools / Cmd+K.
 */
export const ADMIN_COMMAND_STRIP_HEIGHT_RANGE = "44–48px";
export const ADMIN_COMMAND_STRIP_DESKTOP_HEIGHT_CLASS = "h-[46px] min-h-[44px] max-h-[48px]";

export interface AdminCommandStripTabItem {
  key: string;
  href: string;
  label: string;
  altLabel?: string;
  hint: string;
  code: string;
  icon: IconName;
}

export const ADMIN_PRIMARY_TABS: AdminCommandStripTabItem[] = [
  {
    key: "overview",
    href: "/admin/overview",
    label: "Tổng quan",
    hint: "Toàn cảnh cấu hình và trạng thái",
    code: "A01",
    icon: "calendar",
  },
  {
    key: "knowledge-sources",
    href: "/admin/knowledge-sources",
    label: "Nguồn tri thức",
    hint: "Kho tri thức và connector truy xuất",
    code: "A02",
    icon: "folder",
  },
  {
    key: "answer-flow",
    href: "/admin/answer-flow",
    label: "Luồng suy luận",
    altLabel: "Luồng trả lời",
    hint: "Flow flags và runtime debug",
    code: "A03",
    icon: "scan",
  },
  {
    key: "observability",
    href: "/admin/observability",
    label: "Giám sát",
    hint: "Health, metrics và signal board",
    code: "A04",
    icon: "progress",
  },
  {
    key: "product-analytics",
    href: "/admin/analytics",
    label: "Phân tích",
    hint: "Người dùng, Surface và giữ chân",
    code: "A05",
    icon: "calendar",
  },
];

export interface AdminCommandStripProps {
  activeTab?: string;
  className?: string;
  onOpenLauncher?: () => void;
  onOpenCommandPalette?: () => void;
}

export function AdminCommandStrip({
  activeTab,
  className = "",
  onOpenLauncher,
  onOpenCommandPalette,
}: AdminCommandStripProps) {
  const [isLauncherOpen, setIsLauncherOpen] = useState(false);

  const handleOpenLauncher = useCallback(() => {
    if (onOpenLauncher) {
      onOpenLauncher();
    } else if (onOpenCommandPalette) {
      onOpenCommandPalette();
    } else {
      setIsLauncherOpen(true);
    }
  }, [onOpenLauncher, onOpenCommandPalette]);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        handleOpenLauncher();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleOpenLauncher]);

  // Check if activeTab is a secondary module (not in primary tabs)
  const isPrimaryTabActive = ADMIN_PRIMARY_TABS.some((tab) => {
    if (tab.key === activeTab) return true;
    if (tab.key === "product-analytics" && activeTab === "analytics") return true;
    return false;
  });

  const secondaryActiveTool =
    !isPrimaryTabActive && activeTab ? getAdminToolById(activeTab) : undefined;

  return (
    <>
      <nav
        role="navigation"
        aria-label="Admin command strip"
        data-testid="admin-command-strip"
        className={[
          "h-[46px] min-h-[44px] max-h-[48px] rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 shadow-sm flex items-center justify-between gap-1.5",
          className,
        ].join(" ")}
      >
        <div className="flex flex-1 items-center justify-between gap-1.5 overflow-x-auto min-w-0">
          {/* Primary Nav Tabs */}
          <ul className="flex items-center gap-1 min-w-0" role="menubar">
            {ADMIN_PRIMARY_TABS.map((tab) => {
              const isActive =
                tab.key === activeTab ||
                (tab.key === "product-analytics" && activeTab === "analytics");

              return (
                <li key={tab.key} role="none" className="shrink-0">
                  <Link
                    href={tab.href}
                    role="menuitem"
                    aria-current={isActive ? "page" : undefined}
                    title={tab.hint}
                    data-testid={`admin-command-tab-${tab.key}`}
                    className={[
                      "group inline-flex h-8 min-h-[32px] items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40",
                      isActive
                        ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[#cdd7ff] shadow-xs"
                        : "border-transparent bg-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <Icon
                      name={tab.icon}
                      size={14}
                      className={
                        isActive
                          ? "text-[#cdd7ff]"
                          : "text-[var(--text-muted)] group-hover:text-[var(--text-brand)]"
                      }
                      aria-hidden="true"
                    />
                    <span>{tab.label}</span>
                    <span
                      className={[
                        "inline-flex items-center justify-center rounded px-1.5 py-0.2 text-[10px] font-mono font-bold",
                        isActive
                          ? "bg-[#00174b]/35 text-[#cdd7ff]"
                          : "bg-[var(--surface-muted)] text-[var(--text-muted)] group-hover:bg-[var(--surface-panel)]",
                      ].join(" ")}
                      aria-hidden="true"
                    >
                      {tab.code}
                    </span>
                  </Link>
                </li>
              );
            })}

            {/* More / All Tools ▾ Button */}
            <li role="none" className="shrink-0">
              <button
                type="button"
                role="menuitem"
                onClick={handleOpenLauncher}
                aria-expanded={isLauncherOpen}
                aria-haspopup="dialog"
                data-testid="admin-command-more-button"
                title="Tất cả công cụ quản trị"
                className={[
                  "inline-flex h-8 min-h-[32px] items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40",
                  !isPrimaryTabActive && secondaryActiveTool
                    ? "border-[color:var(--brand-primary)]/60 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                    : "border-transparent bg-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                <span>
                  {!isPrimaryTabActive && secondaryActiveTool
                    ? secondaryActiveTool.title
                    : "Thêm"}
                </span>
                <Icon
                  name="chevron-down"
                  size={13}
                  className="text-[var(--text-muted)]"
                  aria-hidden="true"
                />
              </button>
            </li>
          </ul>

          {/* Right Action: App Launcher Quick Search Button / Cmd+K */}
          <div className="flex items-center gap-1.5 shrink-0 pl-1">
            <button
              type="button"
              onClick={handleOpenLauncher}
              aria-label="Mở trình khởi chạy tất cả ứng dụng quản trị"
              data-testid="admin-command-search-trigger"
              className="inline-flex h-8 min-h-[32px] items-center gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40"
            >
              <Icon
                name="search"
                size={14}
                className="text-[var(--text-brand)]"
                aria-hidden="true"
              />
              <span className="hidden sm:inline">Tìm công cụ...</span>
              <span className="sm:hidden">Tìm</span>
              <kbd className="hidden rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1.5 py-0.2 text-[10px] font-semibold text-[var(--text-muted)] lg:inline-block">
                ⌘K
              </kbd>
            </button>
          </div>
        </div>
      </nav>

      {/* App Launcher Modal Dialog */}
      <AdminAppLauncherModal
        isOpen={isLauncherOpen}
        onClose={() => setIsLauncherOpen(false)}
        activeTab={activeTab}
      />
    </>
  );
}

export default AdminCommandStrip;
