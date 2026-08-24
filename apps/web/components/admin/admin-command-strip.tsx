"use client";

import Link from "next/link";
import { useState } from "react";
import Icon from "@/components/ui/icon";
import AdminAppLauncherModal from "./admin-app-launcher-modal";
import {
  PRIMARY_ADMIN_TABS,
  getAdminToolById,
} from "./admin-tools-registry";

export interface AdminCommandStripProps {
  activeTab?: string;
  className?: string;
}

export default function AdminCommandStrip({
  activeTab,
  className = "",
}: AdminCommandStripProps) {
  const [isLauncherOpen, setIsLauncherOpen] = useState(false);

  // Check if activeTab is a secondary module (not in primary tabs)
  const isPrimaryTabActive = PRIMARY_ADMIN_TABS.some((tab) => {
    if (tab.key === activeTab) return true;
    if (tab.key === "product-analytics" && activeTab === "analytics") return true;
    return false;
  });

  const secondaryActiveTool = !isPrimaryTabActive && activeTab
    ? getAdminToolById(activeTab)
    : undefined;

  return (
    <>
      <nav
        aria-label="Admin command strip"
        className={[
          "rounded-[var(--radius-xl)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-1.5 shadow-sm",
          className,
        ].join(" ")}
      >
        <div className="flex flex-wrap items-center justify-between gap-1.5">
          {/* Primary Nav Tabs */}
          <ul className="flex flex-wrap items-center gap-1">
            {PRIMARY_ADMIN_TABS.map((tab) => {
              const isActive =
                tab.key === activeTab ||
                (tab.key === "product-analytics" && activeTab === "analytics");

              return (
                <li key={tab.key}>
                  <Link
                    href={tab.href}
                    aria-current={isActive ? "page" : undefined}
                    title={tab.hint}
                    className={[
                      "group inline-flex min-h-[38px] items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40",
                      isActive
                        ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[#cdd7ff] shadow-xs"
                        : "border-transparent bg-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <Icon
                      name={tab.icon}
                      size={15}
                      className={isActive ? "text-[#cdd7ff]" : "text-[var(--text-muted)] group-hover:text-[var(--text-brand)]"}
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

            {/* More ▾ Button */}
            <li>
              <button
                type="button"
                onClick={() => setIsLauncherOpen(true)}
                aria-expanded={isLauncherOpen}
                aria-haspopup="dialog"
                className={[
                  "inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40",
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

          {/* Right Action: App Launcher Quick Search Button */}
          <div className="flex items-center gap-1.5 pl-1">
            <button
              type="button"
              onClick={() => setIsLauncherOpen(true)}
              aria-label="Mở trình khởi chạy tất cả ứng dụng quản trị"
              className="inline-flex min-h-[38px] items-center gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]/40"
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
