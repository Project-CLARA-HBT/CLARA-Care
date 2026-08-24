"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import Icon from "@/components/ui/icon";
import {
  ADMIN_CATEGORIES,
  ADMIN_CATEGORY_ORDER,
  ADMIN_TOOLS,
  searchAdminTools,
  type AdminCategoryKey,
  type AdminToolItem,
} from "./admin-tools-registry";

export interface AdminAppLauncherModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab?: string;
  className?: string;
}

const BADGE_TONE_STYLES: Record<
  NonNullable<AdminToolItem["badgeTone"]>,
  string
> = {
  primary:
    "border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
  info: "border-[#38bdf8]/40 bg-[#0284c7]/15 text-[#38bdf8]",
  warning:
    "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
  success:
    "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
  muted:
    "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
};

export function AdminAppLauncherModal({
  isOpen,
  onClose,
  activeTab,
  className = "",
}: AdminAppLauncherModalProps) {
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<AdminCategoryKey | "all">("all");

  const dialogId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const modalContainerRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Focus trap and lifecycle management
  useEffect(() => {
    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setSelectedCategory("all");

      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);

      // Prevent body scroll while modal is open
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";

      return () => {
        clearTimeout(timer);
        document.body.style.overflow = originalOverflow;
      };
    } else {
      if (
        previouslyFocusedRef.current &&
        typeof previouslyFocusedRef.current.focus === "function"
      ) {
        previouslyFocusedRef.current.focus();
      }
    }
  }, [isOpen]);

  // Global Escape key listener
  useEffect(() => {
    if (!isOpen) return;

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [isOpen, onClose]);

  // Focus trap for Tab key
  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "Tab" || !modalContainerRef.current) return;

      const focusableElements = modalContainerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );

      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (event.shiftKey) {
        if (document.activeElement === firstElement) {
          event.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          event.preventDefault();
          firstElement?.focus();
        }
      }
    },
    [],
  );

  // Filtered tools
  const filteredTools = useMemo(() => {
    return searchAdminTools(query, selectedCategory);
  }, [query, selectedCategory]);

  // Counts per category
  const categoryCounts = useMemo(() => {
    const counts: Record<AdminCategoryKey | "all", number> = {
      all: ADMIN_TOOLS.length,
      platform: 0,
      knowledge: 0,
      ai_systems: 0,
      governance: 0,
    };
    ADMIN_TOOLS.forEach((tool) => {
      counts[tool.category] += 1;
    });
    return counts;
  }, []);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center p-3 pt-[6vh] sm:p-6 sm:pt-[8vh]"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${dialogId}-title`}
      aria-describedby={`${dialogId}-desc`}
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#05080c]/80 backdrop-blur-md transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Container */}
      <div
        ref={modalContainerRef}
        className={[
          "relative z-10 flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden rounded-[var(--radius-2xl)]",
          "border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-header)]/98 shadow-2xl backdrop-blur-2xl",
          "animate-in zoom-in-95 fade-in duration-200",
          className,
        ].join(" ")}
      >
        {/* Header with Title and Close Button */}
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="settings" size={18} aria-hidden="true" />
            </span>
            <div>
              <h2
                id={`${dialogId}-title`}
                className="text-base font-bold text-[var(--text-primary)] sm:text-lg"
              >
                Trình khởi chạy Ứng dụng & Công cụ Quản trị
              </h2>
              <p
                id={`${dialogId}-desc`}
                className="text-xs text-[var(--text-secondary)]"
              >
                Khám phá và truy cập nhanh toàn bộ 14 module quản trị, điều phối AI và tuân thủ
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng trình khởi chạy ứng dụng"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]"
          >
            <Icon name="close" size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Search Bar & Category Filter Strip */}
        <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/40 px-5 py-3 sm:px-6">
          {/* Search Input */}
          <div className="relative flex items-center">
            <Icon
              name="search"
              size={18}
              className="pointer-events-none absolute left-3.5 text-[var(--text-muted)]"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              type="text"
              role="searchbox"
              data-pii-safe="true"
              placeholder="Tìm kiếm theo tên module, mã (A01, PLT, KNW, GOV), từ khóa..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-2.5 pl-10 pr-20 text-sm font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-primary)] focus:bg-[var(--surface-panel)] focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
            />

            <div className="absolute right-2.5 flex items-center gap-1.5">
              {query ? (
                <button
                  type="button"
                  onClick={() => {
                    setQuery("");
                    inputRef.current?.focus();
                  }}
                  className="rounded-md px-1.5 py-0.5 text-xs text-[var(--text-muted)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
                >
                  Xóa
                </button>
              ) : null}
              <kbd className="hidden sm:inline-block rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
                ESC
              </kbd>
            </div>
          </div>

          {/* Category Filter Pills */}
          <div
            className="mt-3 flex flex-wrap items-center gap-1.5"
            role="tablist"
            aria-label="Lọc module theo danh mục"
          >
            <button
              type="button"
              role="tab"
              aria-selected={selectedCategory === "all"}
              onClick={() => setSelectedCategory("all")}
              className={[
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]",
                selectedCategory === "all"
                  ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[#cdd7ff]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]",
              ].join(" ")}
            >
              <span>Tất cả</span>
              <span
                className={[
                  "rounded-full px-1.5 py-0.2 text-[10px] font-bold",
                  selectedCategory === "all"
                    ? "bg-[#00174b]/30 text-[#cdd7ff]"
                    : "bg-[var(--surface-muted)] text-[var(--text-muted)]",
                ].join(" ")}
              >
                {categoryCounts.all}
              </span>
            </button>

            {ADMIN_CATEGORY_ORDER.map((catKey) => {
              const meta = ADMIN_CATEGORIES[catKey];
              const isSelected = selectedCategory === catKey;
              return (
                <button
                  key={catKey}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  onClick={() => setSelectedCategory(catKey)}
                  className={[
                    "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]",
                    isSelected
                      ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[#cdd7ff]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  <Icon name={meta.icon} size={13} aria-hidden="true" />
                  <span>{meta.shortLabel}</span>
                  <span
                    className={[
                      "rounded-full px-1.5 py-0.2 text-[10px] font-bold",
                      isSelected
                        ? "bg-[#00174b]/30 text-[#cdd7ff]"
                        : "bg-[var(--surface-muted)] text-[var(--text-muted)]",
                    ].join(" ")}
                  >
                    {categoryCounts[catKey]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Module Content Grid (Scrollable) */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 clara-scrollbar">
          {filteredTools.length === 0 ? (
            <div className="py-14 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]">
                <Icon name="search" size={24} aria-hidden="true" />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">
                Không tìm thấy công cụ quản trị phù hợp
              </h3>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                Thử thay đổi từ khóa tìm kiếm hoặc chọn danh mục &quot;Tất cả&quot;.
              </p>
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setSelectedCategory("all");
                  inputRef.current?.focus();
                }}
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)]"
              >
                <Icon name="refresh" size={13} aria-hidden="true" />
                <span>Xóa bộ lọc tìm kiếm</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filteredTools.map((tool) => {
                const isActive =
                  activeTab === tool.id ||
                  (activeTab === "product-analytics" && tool.id === "analytics") ||
                  (activeTab === "clinical-analytics" && tool.id === "clinical-analytics");

                return (
                  <Link
                    key={tool.id}
                    href={tool.href}
                    onClick={onClose}
                    className={[
                      "group relative flex flex-col justify-between rounded-xl border p-4 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-primary)]",
                      isActive
                        ? "border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)]/60 shadow-sm"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)]",
                    ].join(" ")}
                  >
                    <div>
                      {/* Top Row: Icon + Badges */}
                      <div className="flex items-start justify-between gap-2">
                        <span
                          className={[
                            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors",
                            isActive
                              ? "border-[color:var(--brand-primary)]/50 bg-[var(--brand-600)] text-[#cdd7ff]"
                              : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:border-[color:var(--brand-primary)]/40 group-hover:bg-[var(--surface-brand-soft)]",
                          ].join(" ")}
                        >
                          <Icon name={tool.icon} size={18} aria-hidden="true" />
                        </span>

                        <div className="flex items-center gap-1.5">
                          {tool.badge ? (
                            <span
                              className={[
                                "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                                tool.badgeTone
                                  ? BADGE_TONE_STYLES[tool.badgeTone]
                                  : BADGE_TONE_STYLES.muted,
                              ].join(" ")}
                            >
                              {tool.badge}
                            </span>
                          ) : null}

                          <span className="inline-flex min-w-[2.2rem] items-center justify-center rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-mono font-bold text-[var(--text-muted)]">
                            {tool.code}
                          </span>
                        </div>
                      </div>

                      {/* Tool Title */}
                      <h4 className="mt-3 text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                        {tool.title}
                      </h4>

                      {/* Tool Description */}
                      <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2">
                        {tool.description}
                      </p>
                    </div>

                    {/* Footer Row: Category Meta & Arrow */}
                    <div className="mt-4 flex items-center justify-between border-t border-[color:var(--shell-border)]/60 pt-2.5 text-[11px] text-[var(--text-muted)]">
                      <span className="truncate">
                        {ADMIN_CATEGORIES[tool.category].label}
                      </span>
                      <span className="flex items-center gap-0.5 font-semibold text-[var(--text-brand)] opacity-0 group-hover:opacity-100 transition-opacity">
                        <span>Mở</span>
                        <Icon name="arrow-right" size={12} aria-hidden="true" />
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Modal Footer with Shortcuts */}
        <div className="flex flex-wrap items-center justify-between border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-3 text-xs text-[var(--text-muted)] sm:px-6">
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold">
                Tab
              </kbd>
              <span>Chuyển mục</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold">
                Enter
              </kbd>
              <span>Mở công cụ</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-semibold">
                ESC
              </kbd>
              <span>Đóng</span>
            </span>
          </div>

          <div className="text-[11px] font-medium text-[var(--text-secondary)]">
            Hiển thị {filteredTools.length} / {ADMIN_TOOLS.length} module quản trị
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminAppLauncherModal;
