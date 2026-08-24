"use client";

import React, {
  useEffect,
  useState,
  type ReactNode,
} from "react";
import Icon from "./icon";

export type SectionIndexStatus =
  | "completed"
  | "current"
  | "pending"
  | "error"
  | "warning";

export type SectionIndexDensity = "comfortable" | "compact" | "dense";

export interface SectionIndexItem {
  id: string;
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  level?: 1 | 2 | 3;
  status?: SectionIndexStatus;
  disabled?: boolean;
  count?: number;
}

export interface SectionIndexProps {
  items: SectionIndexItem[];
  activeId?: string;
  onSectionSelect?: (id: string) => void;
  title?: string;
  description?: string;
  showProgress?: boolean;
  sticky?: boolean;
  density?: SectionIndexDensity;
  className?: string;
  ariaLabel?: string;
  autoScrollSpy?: boolean;
}

const DENSITY_STYLES: Record<
  SectionIndexDensity,
  {
    container: string;
    itemPadding: string;
    textSize: string;
    subtitleSize: string;
    indicatorSize: string;
    levelIndent: Record<number, string>;
  }
> = {
  comfortable: {
    container: "p-4 space-y-2",
    itemPadding: "px-3.5 py-2.5",
    textSize: "text-sm",
    subtitleSize: "text-xs",
    indicatorSize: "h-4 w-4",
    levelIndent: { 1: "pl-0", 2: "pl-4", 3: "pl-8" },
  },
  compact: {
    container: "p-3 space-y-1.5",
    itemPadding: "px-3 py-2",
    textSize: "text-xs sm:text-sm",
    subtitleSize: "text-[0.6875rem]",
    indicatorSize: "h-3.5 w-3.5",
    levelIndent: { 1: "pl-0", 2: "pl-3.5", 3: "pl-7" },
  },
  dense: {
    container: "p-2 space-y-1",
    itemPadding: "px-2 py-1",
    textSize: "text-xs",
    subtitleSize: "text-[0.625rem]",
    indicatorSize: "h-3 w-3",
    levelIndent: { 1: "pl-0", 2: "pl-2.5", 3: "pl-5" },
  },
};

function StatusIndicator({
  status,
  isActive,
}: {
  status?: SectionIndexStatus;
  isActive: boolean;
}) {
  if (status === "completed") {
    return (
      <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]">
        <Icon name="check" size={10} />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]">
        <Icon name="warning" size={10} />
      </span>
    );
  }
  if (status === "warning") {
    return (
      <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]">
        <Icon name="warning" size={10} />
      </span>
    );
  }
  if (isActive || status === "current") {
    return (
      <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="h-2 w-2 rounded-full bg-[var(--brand-500)] shadow-sm animate-pulse" />
      </span>
    );
  }
  return (
    <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-[var(--text-tertiary)]">
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
    </span>
  );
}

export function SectionIndex({
  items,
  activeId: controlledActiveId,
  onSectionSelect,
  title = "Mục lục",
  description,
  showProgress = true,
  sticky = true,
  density = "compact",
  className = "",
  ariaLabel = "Mục lục điều hướng",
  autoScrollSpy = false,
}: SectionIndexProps) {
  const [internalActiveId, setInternalActiveId] = useState<string>(
    controlledActiveId || items[0]?.id || "",
  );

  const activeId = controlledActiveId ?? internalActiveId;
  const config = DENSITY_STYLES[density] ?? DENSITY_STYLES.compact;

  // Optional ScrollSpy using IntersectionObserver
  useEffect(() => {
    if (
      !autoScrollSpy ||
      typeof window === "undefined" ||
      typeof IntersectionObserver === "undefined"
    ) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const intersecting = entries.find((e) => e.isIntersecting);
        if (intersecting) {
          const matchingId = intersecting.target.id;
          setInternalActiveId(matchingId);
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );

    items.forEach((item) => {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [autoScrollSpy, items]);

  const handleJump = (id: string, item: SectionIndexItem) => {
    if (item.disabled) return;
    setInternalActiveId(id);
    if (onSectionSelect) {
      onSectionSelect(id);
    }

    if (typeof document !== "undefined") {
      const targetElement = document.getElementById(id);
      if (targetElement) {
        targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
        targetElement.focus?.({ preventScroll: true });
      }
    }
  };

  const completedCount = items.filter(
    (item) => item.status === "completed",
  ).length;
  const progressPercent =
    items.length > 0 ? Math.round((completedCount / items.length) * 100) : 0;

  return (
    <nav
      aria-label={ariaLabel}
      className={`flex flex-col rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm ${
        sticky ? "sticky top-4 z-10" : ""
      } ${className}`}
    >
      {/* Header */}
      {(title || description) && (
        <div className="border-b border-[color:var(--shell-border)] px-4 py-3.5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              {title}
            </h3>
            {showProgress && items.length > 0 && (
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                {completedCount}/{items.length}
              </span>
            )}
          </div>
          {description ? (
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {description}
            </p>
          ) : null}

          {/* Progress Bar */}
          {showProgress && items.length > 0 && (
            <div
              className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]"
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Tiến độ hoàn thành mục"
            >
              <div
                className="h-full bg-[var(--brand-500)] transition-all duration-300 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Sections List */}
      <ul className={`flex flex-col ${config.container}`}>
        {items.map((item) => {
          const isActive = item.id === activeId;
          const level = item.level ?? 1;
          const indentClass = config.levelIndent[level] ?? "";

          return (
            <li key={item.id} className={indentClass}>
              <button
                type="button"
                onClick={() => handleJump(item.id, item)}
                disabled={item.disabled}
                aria-current={isActive ? "location" : undefined}
                className={`group flex w-full items-center justify-between gap-2.5 rounded-[var(--radius-md)] text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)] ${
                  config.itemPadding
                } ${
                  isActive
                    ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-semibold border-l-2 border-l-[var(--brand-500)] pl-2.5"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                } ${
                  item.disabled
                    ? "opacity-40 cursor-not-allowed pointer-events-none"
                    : "cursor-pointer"
                }`}
              >
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                  <StatusIndicator
                    status={item.status}
                    isActive={isActive}
                  />
                  <div className="min-w-0 flex-1">
                    <span
                      className={`block truncate ${config.textSize} ${
                        isActive
                          ? "text-[var(--text-brand)]"
                          : "text-[var(--text-primary)] group-hover:text-[var(--text-primary)]"
                      }`}
                    >
                      {item.title}
                    </span>
                    {item.subtitle && (
                      <span
                        className={`block truncate text-[var(--text-tertiary)] ${config.subtitleSize}`}
                      >
                        {item.subtitle}
                      </span>
                    )}
                  </div>
                </div>

                {(item.badge || item.count !== undefined) && (
                  <div className="shrink-0">
                    {item.badge ? (
                      item.badge
                    ) : (
                      <span className="inline-flex min-h-[16px] min-w-[16px] items-center justify-center rounded-full bg-[var(--surface-muted)] px-1 text-[0.625rem] font-medium text-[var(--text-secondary)]">
                        {item.count}
                      </span>
                    )}
                  </div>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default SectionIndex;
