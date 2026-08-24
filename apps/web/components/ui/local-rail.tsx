"use client";

import React, {
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import Icon, { resolveIconName } from "./icon";

export type LocalRailDensity = "comfortable" | "compact" | "dense";

export interface LocalRailItem {
  key: string;
  label: string;
  icon?: string | ReactNode;
  badge?: ReactNode | string | number;
  href?: string;
  disabled?: boolean;
  tooltip?: string;
  onClick?: (key: string) => void;
}

export interface LocalRailProps {
  items: LocalRailItem[];
  activeKey?: string;
  onChange?: (key: string) => void;
  density?: LocalRailDensity;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  header?: ReactNode;
  footer?: ReactNode;
  className?: string;
  ariaLabel?: string;
  showLabels?: boolean;
}

const DENSITY_STYLES: Record<
  LocalRailDensity,
  {
    widthCollapsed: string;
    widthExpanded: string;
    itemPadding: string;
    iconSize: number;
    gap: string;
    textSize: string;
  }
> = {
  comfortable: {
    widthCollapsed: "w-16",
    widthExpanded: "w-60",
    itemPadding: "p-3",
    iconSize: 22,
    gap: "gap-2.5",
    textSize: "text-sm",
  },
  compact: {
    widthCollapsed: "w-13 sm:w-14",
    widthExpanded: "w-52",
    itemPadding: "px-3 py-2.5",
    iconSize: 18,
    gap: "gap-2",
    textSize: "text-xs sm:text-sm",
  },
  dense: {
    widthCollapsed: "w-11",
    widthExpanded: "w-44",
    itemPadding: "px-2 py-1.5",
    iconSize: 16,
    gap: "gap-1.5",
    textSize: "text-xs",
  },
};

export function LocalRail({
  items,
  activeKey,
  onChange,
  density = "compact",
  collapsed = true,
  onToggleCollapse,
  header,
  footer,
  className = "",
  ariaLabel = "Thanh điều hướng cục bộ",
  showLabels = false,
}: LocalRailProps) {
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const isExpanded = !collapsed || showLabels;
  const config = DENSITY_STYLES[density] ?? DENSITY_STYLES.compact;

  const handleSelect = (key: string, item: LocalRailItem) => {
    if (item.disabled) return;
    if (item.onClick) {
      item.onClick(key);
    }
    if (onChange) {
      onChange(key);
    }
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLElement>,
    currentIndex: number,
  ) => {
    const enabledItems = items.filter((item) => !item.disabled);
    const enabledKeys = enabledItems.map((item) => item.key);
    const currentEnabledIndex = enabledKeys.indexOf(items[currentIndex]?.key);

    let nextKey: string | undefined;

    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        event.preventDefault();
        nextKey =
          enabledKeys[(currentEnabledIndex + 1) % enabledKeys.length];
        break;
      case "ArrowUp":
      case "ArrowLeft":
        event.preventDefault();
        nextKey =
          enabledKeys[
            (currentEnabledIndex - 1 + enabledKeys.length) % enabledKeys.length
          ];
        break;
      case "Home":
        event.preventDefault();
        nextKey = enabledKeys[0];
        break;
      case "End":
        event.preventDefault();
        nextKey = enabledKeys[enabledKeys.length - 1];
        break;
      default:
        break;
    }

    if (nextKey && itemRefs.current[nextKey]) {
      itemRefs.current[nextKey]?.focus();
      const targetItem = items.find((i) => i.key === nextKey);
      if (targetItem) {
        handleSelect(nextKey, targetItem);
      }
    }
  };

  return (
    <nav
      aria-label={ariaLabel}
      className={`flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-3 shadow-sm transition-all duration-200 ${
        isExpanded ? config.widthExpanded : config.widthCollapsed
      } ${className}`}
    >
      {/* Header Slot */}
      <div className="flex flex-col gap-2 px-2">
        {header}
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={isExpanded ? "Thu gọn thanh điều hướng" : "Mở rộng thanh điều hướng"}
            className="flex h-8 w-full items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
          >
            <Icon
              name={isExpanded ? "arrow-left" : "arrow-right"}
              size={16}
            />
          </button>
        )}
      </div>

      {/* Item List */}
      <div className={`my-auto flex flex-col ${config.gap} px-2 py-2`}>
        {items.map((item, index) => {
          const isActive = item.key === activeKey;
          const isItemDisabled = Boolean(item.disabled);

          const itemContent = (
            <>
              {/* Icon */}
              <div
                className={`flex shrink-0 items-center justify-center ${
                  isActive
                    ? "text-[var(--text-brand)]"
                    : "text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]"
                }`}
              >
                {typeof item.icon === "string" ? (
                  <Icon
                    name={resolveIconName(item.icon)}
                    size={config.iconSize}
                  />
                ) : item.icon ? (
                  item.icon
                ) : (
                  <span className="h-2 w-2 rounded-full bg-current" />
                )}
              </div>

              {/* Label in expanded mode */}
              {isExpanded && (
                <span
                  className={`min-w-0 flex-1 truncate font-medium ${
                    isActive
                      ? "text-[var(--text-brand)] font-semibold"
                      : "text-[var(--text-primary)]"
                  }`}
                >
                  {item.label}
                </span>
              )}

              {/* Badge */}
              {item.badge !== undefined && item.badge !== null && (
                <div
                  className={`shrink-0 ${
                    isExpanded
                      ? "ml-auto"
                      : "absolute -top-1 -right-1"
                  }`}
                >
                  {typeof item.badge === "string" ||
                  typeof item.badge === "number" ? (
                    <span className="inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[var(--brand-600)] px-1.5 text-[0.6875rem] font-bold leading-none text-white">
                      {item.badge}
                    </span>
                  ) : (
                    item.badge
                  )}
                </div>
              )}
            </>
          );

          const commonClasses = `group relative flex items-center ${
            isExpanded ? "justify-start gap-2.5" : "justify-center"
          } ${
            config.itemPadding
          } ${config.textSize} rounded-[var(--radius-lg)] border border-transparent transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)] ${
            isActive
              ? "bg-[var(--surface-brand-soft)] border-[color:var(--brand-500)]/30 text-[var(--text-brand)] shadow-sm"
              : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          } ${isItemDisabled ? "opacity-40 cursor-not-allowed pointer-events-none" : "cursor-pointer"}`;

          if (item.href && !isItemDisabled) {
            return (
              <Link
                key={item.key}
                href={item.href}
                ref={(node) => {
                  itemRefs.current[item.key] = node;
                }}
                title={item.tooltip || item.label}
                aria-current={isActive ? "page" : undefined}
                aria-label={item.label}
                aria-disabled={isItemDisabled || undefined}
                onClick={() => handleSelect(item.key, item)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                className={commonClasses}
              >
                {itemContent}
              </Link>
            );
          }

          return (
            <button
              key={item.key}
              type="button"
              ref={(node) => {
                itemRefs.current[item.key] = node;
              }}
              title={item.tooltip || item.label}
              aria-current={isActive ? "page" : undefined}
              aria-label={item.label}
              disabled={isItemDisabled}
              onClick={() => handleSelect(item.key, item)}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={commonClasses}
            >
              {itemContent}
            </button>
          );
        })}
      </div>

      {/* Footer Slot */}
      {footer ? <div className="mt-auto px-2 pt-2 border-t border-[color:var(--shell-border)]">{footer}</div> : null}
    </nav>
  );
}

export default LocalRail;
