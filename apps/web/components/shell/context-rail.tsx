"use client";

import React, {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

export type ContextRailDensity = "comfortable" | "compact" | "dense";
export type ContextRailWidth =
  | "240px"
  | "260px"
  | "280px"
  | "compact"
  | number
  | string;

export interface ContextRailItem {
  /** Unique key or identifier */
  id?: string;
  key?: string;
  /** Primary label text */
  label: string;
  /** Optional subtitle or description */
  subtitle?: string;
  description?: string;
  /** Icon name or custom React node */
  icon?: IconName | string | ReactNode;
  /** Counter, badge label or node */
  badge?: ReactNode | string | number;
  /** Badge color variant */
  badgeVariant?: "default" | "brand" | "warning" | "danger" | "neutral" | "success";
  /** Navigation link target */
  href?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Tooltip or title attribute */
  tooltip?: string;
  /** Group / category identifier or header */
  group?: string;
  /** Trailing metadata or timestamp */
  meta?: ReactNode;
  /** Trailing action button or node */
  trailing?: ReactNode;
  /** Click handler */
  onClick?: (item: ContextRailItem) => void;
}

export interface ContextRailGroup {
  id?: string;
  title: string;
  items: ContextRailItem[];
}

export interface ContextRailProps {
  /** Flat list of navigation items */
  items?: ContextRailItem[];
  /** Grouped navigation items */
  groups?: ContextRailGroup[];
  /** Currently active item key or id */
  activeKey?: string;
  activeId?: string;
  /** Selection callback */
  onSelect?: (key: string, item: ContextRailItem) => void;
  onChange?: (key: string, item: ContextRailItem) => void;
  /** Controlled desktop collapsed state */
  collapsed?: boolean;
  defaultCollapsed?: boolean;
  /** Collapse toggle callback */
  onToggleCollapse?: () => void;
  onCollapseChange?: (collapsed: boolean) => void;
  /** Header slot */
  header?: ReactNode;
  /** Rail title */
  title?: ReactNode;
  /** Rail subtitle */
  subtitle?: ReactNode;
  /** Header action */
  headerAction?: ReactNode;
  /** Footer slot */
  footer?: ReactNode;
  /** Visual density */
  density?: ContextRailDensity;
  /** Desktop rail width: 240px–280px (default 260px) */
  width?: ContextRailWidth;
  /** Mobile open state (drawer/sheet overlay mode) */
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  /** Alias for mobile open / close */
  open?: boolean;
  onClose?: () => void;
  /** Explicitly enforce mobile/drawer layout */
  isMobile?: boolean;
  /** Accessible landmark / dialog label */
  ariaLabel?: string;
  /** Show collapse toggle button on desktop */
  showCollapseToggle?: boolean;
  /** Labels for collapse / expand buttons */
  collapseLabel?: string;
  expandLabel?: string;
  closeLabel?: string;
  /** Custom container styling */
  className?: string;
  headerClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  children?: ReactNode;
  "data-testid"?: string;
  id?: string;
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => {
    if (el.hasAttribute("disabled")) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    if (el.hasAttribute("hidden")) return false;
    if (el.style.display === "none" || el.style.visibility === "hidden") {
      return false;
    }
    return true;
  });
}

const DENSITY_CONFIG: Record<
  ContextRailDensity,
  {
    itemPadding: string;
    itemPaddingCollapsed: string;
    iconSize: number;
    gap: string;
    textSize: string;
    badgeSize: string;
  }
> = {
  comfortable: {
    itemPadding: "px-3 py-2.5",
    itemPaddingCollapsed: "p-2.5",
    iconSize: 20,
    gap: "gap-1.5",
    textSize: "text-sm",
    badgeSize: "text-xs px-2 py-0.5",
  },
  compact: {
    itemPadding: "px-2.5 py-2",
    itemPaddingCollapsed: "p-2",
    iconSize: 18,
    gap: "gap-1",
    textSize: "text-xs sm:text-sm",
    badgeSize: "text-[0.6875rem] px-1.5 py-0.25",
  },
  dense: {
    itemPadding: "px-2 py-1.5",
    itemPaddingCollapsed: "p-1.5",
    iconSize: 16,
    gap: "gap-0.5",
    textSize: "text-xs",
    badgeSize: "text-[0.625rem] px-1 py-0",
  },
};

const WIDTH_CLASSES: Record<string, string> = {
  "240px": "w-[240px]",
  "260px": "w-[260px]",
  "280px": "w-[280px]",
  compact: "w-[240px]",
};

function getItemKey(item: ContextRailItem, fallbackIndex: number): string {
  return item.key ?? item.id ?? `rail-item-${fallbackIndex}`;
}

export function ContextRail({
  items: propItems,
  groups: propGroups,
  activeKey: propActiveKey,
  activeId: propActiveId,
  onSelect,
  onChange,
  collapsed: propCollapsed,
  defaultCollapsed = false,
  onToggleCollapse,
  onCollapseChange,
  header,
  title,
  subtitle,
  headerAction,
  footer,
  density = "compact",
  width = "260px",
  mobileOpen: propMobileOpen,
  onMobileClose: propOnMobileClose,
  open: propOpen,
  onClose: propOnClose,
  isMobile = false,
  ariaLabel = "Thanh điều hướng cục bộ",
  showCollapseToggle = true,
  collapseLabel = "Thu gọn thanh điều hướng",
  expandLabel = "Mở rộng thanh điều hướng",
  closeLabel = "Đóng thanh điều hướng",
  className = "",
  headerClassName = "",
  bodyClassName = "",
  footerClassName = "",
  children,
  "data-testid": dataTestId,
  id: customId,
}: ContextRailProps) {
  const generatedId = useId();
  const railId = customId ?? `context-rail-${generatedId}`;

  // Collapsed state management (desktop)
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed);
  const isCollapsed = propCollapsed !== undefined ? propCollapsed : internalCollapsed;

  const handleToggleCollapse = useCallback(() => {
    const nextState = !isCollapsed;
    if (propCollapsed === undefined) {
      setInternalCollapsed(nextState);
    }
    if (onToggleCollapse) {
      onToggleCollapse();
    }
    if (onCollapseChange) {
      onCollapseChange(nextState);
    }
  }, [isCollapsed, propCollapsed, onToggleCollapse, onCollapseChange]);

  // Mobile open state management
  const isDrawerOpen =
    propMobileOpen !== undefined
      ? propMobileOpen
      : propOpen !== undefined
        ? propOpen
        : false;

  const handleClose = useCallback(() => {
    if (propOnMobileClose) {
      propOnMobileClose();
    }
    if (propOnClose) {
      propOnClose();
    }
  }, [propOnMobileClose, propOnClose]);

  // Flattened item list for navigation & roving tabindex
  const flattenedItems = useMemo<ContextRailItem[]>(() => {
    if (propGroups && propGroups.length > 0) {
      const result: ContextRailItem[] = [];
      propGroups.forEach((g) => {
        g.items.forEach((item) => {
          result.push({ ...item, group: item.group ?? g.title });
        });
      });
      return result;
    }
    return propItems ?? [];
  }, [propGroups, propItems]);

  const effectiveActiveKey = propActiveKey ?? propActiveId;

  // Track currently focused item key for roving tabindex
  const [focusedKey, setFocusedKey] = useState<string>(() => {
    if (effectiveActiveKey) return effectiveActiveKey;
    const firstEnabled = flattenedItems.find((i) => !i.disabled);
    return firstEnabled ? getItemKey(firstEnabled, 0) : "";
  });

  // Sync focused key with activeKey when activeKey changes
  useEffect(() => {
    if (effectiveActiveKey) {
      setFocusedKey(effectiveActiveKey);
    }
  }, [effectiveActiveKey]);

  // DOM node references for roving focus
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const drawerPanelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Enabled items for roving keyboard navigation
  const enabledItems = useMemo(
    () =>
      flattenedItems
        .map((item, idx) => ({ item, key: getItemKey(item, idx), idx }))
        .filter(({ item }) => !item.disabled),
    [flattenedItems],
  );

  const handleItemSelect = useCallback(
    (key: string, item: ContextRailItem) => {
      if (item.disabled) return;
      setFocusedKey(key);
      if (item.onClick) {
        item.onClick(item);
      }
      if (onSelect) {
        onSelect(key, item);
      }
      if (onChange) {
        onChange(key, item);
      }
      if (isMobile || isDrawerOpen) {
        handleClose();
      }
    },
    [isMobile, isDrawerOpen, onSelect, onChange, handleClose],
  );

  // Roving tabindex keyboard navigation handler
  const handleItemKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLElement>, currentIndex: number) => {
      if (enabledItems.length === 0) return;

      const currentKey = getItemKey(flattenedItems[currentIndex], currentIndex);
      const currentEnabledIdx = enabledItems.findIndex((e) => e.key === currentKey);

      let nextKey: string | undefined;

      switch (event.key) {
        case "ArrowDown":
        case "ArrowRight": {
          event.preventDefault();
          const nextIdx = (currentEnabledIdx + 1) % enabledItems.length;
          nextKey = enabledItems[nextIdx]?.key;
          break;
        }
        case "ArrowUp":
        case "ArrowLeft": {
          event.preventDefault();
          const prevIdx =
            (currentEnabledIdx - 1 + enabledItems.length) % enabledItems.length;
          nextKey = enabledItems[prevIdx]?.key;
          break;
        }
        case "Home": {
          event.preventDefault();
          nextKey = enabledItems[0]?.key;
          break;
        }
        case "End": {
          event.preventDefault();
          nextKey = enabledItems[enabledItems.length - 1]?.key;
          break;
        }
        case "Enter":
        case " ": {
          // If not a link, trigger selection
          const currentItem = flattenedItems[currentIndex];
          if (!currentItem.href) {
            event.preventDefault();
            handleItemSelect(currentKey, currentItem);
          }
          return;
        }
        default:
          return;
      }

      if (nextKey) {
        setFocusedKey(nextKey);
        const node = itemRefs.current[nextKey];
        node?.focus();
        const targetItem = enabledItems.find((e) => e.key === nextKey)?.item;
        if (targetItem && (onSelect || onChange)) {
          // Update selection along with roving focus
          if (onSelect) onSelect(nextKey, targetItem);
          if (onChange) onChange(nextKey, targetItem);
        }
      }
    },
    [enabledItems, flattenedItems, handleItemSelect, onSelect, onChange],
  );

  // Focus trap & Escape listener for mobile drawer / sheet mode
  const handleDrawerKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        handleClose();
        return;
      }

      if (event.key !== "Tab") return;
      const panel = drawerPanelRef.current;
      if (!panel) return;

      const focusableNodes = getFocusableElements(panel);
      if (focusableNodes.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }

      const firstNode = focusableNodes[0];
      const lastNode = focusableNodes[focusableNodes.length - 1];
      const activeEl = document.activeElement;

      if (
        event.shiftKey &&
        (activeEl === firstNode || activeEl === panel || !panel.contains(activeEl))
      ) {
        event.preventDefault();
        lastNode.focus();
      } else if (
        !event.shiftKey &&
        (activeEl === lastNode || !panel.contains(activeEl))
      ) {
        event.preventDefault();
        firstNode.focus();
      }
    },
    [handleClose],
  );

  // Manage body scroll & focus on drawer open/close
  useEffect(() => {
    if (!isDrawerOpen) return;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleDrawerKeyDown);

    const timer = setTimeout(() => {
      const panel = drawerPanelRef.current;
      const firstFocusable = panel ? getFocusableElements(panel)[0] : null;
      (firstFocusable ?? panel)?.focus();
    }, 40);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", handleDrawerKeyDown);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isDrawerOpen, handleDrawerKeyDown]);

  const densityStyles = DENSITY_CONFIG[density] ?? DENSITY_CONFIG.compact;

  // Resolve width classes (240px–280px on desktop)
  const desktopWidthClass = isCollapsed
    ? "w-16 min-w-[4rem]"
    : typeof width === "string" && WIDTH_CLASSES[width]
      ? WIDTH_CLASSES[width]
      : "w-[260px] lg:w-[280px]";

  const customWidthStyle =
    !isCollapsed && typeof width === "number" ? { width: `${width}px` } : undefined;

  // Render a single rail item
  const renderItem = (item: ContextRailItem, globalIndex: number) => {
    const key = getItemKey(item, globalIndex);
    const isActive = effectiveActiveKey ? key === effectiveActiveKey : false;
    const isFocused = focusedKey ? key === focusedKey : globalIndex === 0;
    const isDisabled = Boolean(item.disabled);

    // Badge styling
    let badgeColorClass = "bg-[var(--brand-600)] text-white";
    if (item.badgeVariant === "warning") {
      badgeColorClass =
        "bg-[var(--status-warn-bg)] border border-[color:var(--status-warn-border)] text-[var(--status-warn-text)]";
    } else if (item.badgeVariant === "danger") {
      badgeColorClass =
        "bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] text-[var(--status-danger-text)]";
    } else if (item.badgeVariant === "neutral") {
      badgeColorClass =
        "bg-[var(--status-neutral-bg)] border border-[color:var(--status-neutral-border)] text-[var(--status-neutral-text)]";
    } else if (item.badgeVariant === "success" || item.badgeVariant === "brand") {
      badgeColorClass =
        "bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/40 text-[var(--text-brand)]";
    }

    const itemContent = (
      <>
        {/* Icon */}
        <div
          className={`flex shrink-0 items-center justify-center transition-colors ${
            isActive
              ? "text-[var(--text-brand)]"
              : "text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]"
          }`}
        >
          {typeof item.icon === "string" ? (
            <Icon
              name={resolveIconName(item.icon)}
              size={densityStyles.iconSize}
            />
          ) : item.icon ? (
            item.icon
          ) : (
            <span
              className={`h-2 w-2 rounded-full ${
                isActive ? "bg-[var(--brand-500)]" : "bg-current opacity-60"
              }`}
            />
          )}
        </div>

        {/* Labels in expanded mode */}
        {!isCollapsed && (
          <div className="min-w-0 flex-1 text-left">
            <div className="flex items-center justify-between gap-1.5">
              <span
                className={`truncate font-medium leading-tight ${
                  isActive
                    ? "text-[var(--text-brand)] font-semibold"
                    : "text-[var(--text-primary)]"
                }`}
              >
                {item.label}
              </span>
              {item.meta && (
                <span className="shrink-0 text-[0.6875rem] text-[var(--text-secondary)]">
                  {item.meta}
                </span>
              )}
            </div>
            {(item.subtitle || item.description) && (
              <p className="mt-0.5 truncate text-[0.6875rem] text-[var(--text-secondary)]">
                {item.subtitle || item.description}
              </p>
            )}
          </div>
        )}

        {/* Badge */}
        {item.badge !== undefined && item.badge !== null && (
          <div
            className={`shrink-0 ${
              isCollapsed
                ? "absolute -top-1 -right-1"
                : "ml-auto"
            }`}
          >
            {typeof item.badge === "string" || typeof item.badge === "number" ? (
              <span
                className={`inline-flex items-center justify-center rounded-full font-bold leading-none ${densityStyles.badgeSize} ${badgeColorClass}`}
              >
                {item.badge}
              </span>
            ) : (
              item.badge
            )}
          </div>
        )}

        {/* Trailing action in expanded mode */}
        {!isCollapsed && item.trailing && (
          <div
            className="shrink-0 ml-1"
            onClick={(e) => e.stopPropagation()}
          >
            {item.trailing}
          </div>
        )}
      </>
    );

    const buttonClasses = `group relative flex items-center w-full select-none rounded-[var(--radius-lg)] border transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)] ${
      isCollapsed
        ? `justify-center ${densityStyles.itemPaddingCollapsed}`
        : `justify-start gap-2.5 ${densityStyles.itemPadding}`
    } ${densityStyles.textSize} ${
      isActive
        ? "border-[color:var(--brand-500)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-medium shadow-sm"
        : "border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
    } ${
      isDisabled
        ? "cursor-not-allowed opacity-40 pointer-events-none"
        : "cursor-pointer"
    }`;

    if (item.href && !isDisabled) {
      return (
        <Link
          key={key}
          href={item.href}
          ref={(node) => {
            itemRefs.current[key] = node;
          }}
          title={item.tooltip || item.label}
          aria-current={isActive ? "page" : undefined}
          aria-label={item.label}
          tabIndex={isFocused ? 0 : -1}
          onClick={() => handleItemSelect(key, item)}
          onKeyDown={(e) => handleItemKeyDown(e, globalIndex)}
          className={buttonClasses}
        >
          {itemContent}
        </Link>
      );
    }

    return (
      <button
        key={key}
        type="button"
        ref={(node) => {
          itemRefs.current[key] = node;
        }}
        title={item.tooltip || item.label}
        aria-current={isActive ? "page" : undefined}
        aria-label={item.label}
        disabled={isDisabled}
        tabIndex={isFocused ? 0 : -1}
        onClick={() => handleItemSelect(key, item)}
        onKeyDown={(e) => handleItemKeyDown(e, globalIndex)}
        className={buttonClasses}
      >
        {itemContent}
      </button>
    );
  };

  // Rail inner body: headers, items/groups, children, footer
  const railInnerContent = (
    <>
      {/* Header Slot */}
      {(header || title || showCollapseToggle) && (
        <div
          className={`flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 px-3 py-3 ${headerClassName}`}
        >
          {header ? (
            header
          ) : (
            <div className="flex min-w-0 flex-1 items-center justify-between">
              {!isCollapsed && (title || subtitle) && (
                <div className="min-w-0 flex-1">
                  {title && (
                    <h2 className="truncate text-xs sm:text-sm font-semibold text-[var(--text-primary)]">
                      {title}
                    </h2>
                  )}
                  {subtitle && (
                    <p className="truncate text-[0.6875rem] text-[var(--text-secondary)]">
                      {subtitle}
                    </p>
                  )}
                </div>
              )}
              {!isCollapsed && headerAction && (
                <div className="shrink-0">{headerAction}</div>
              )}
            </div>
          )}

          {/* Desktop collapse toggle button */}
          {showCollapseToggle && !isMobile && !isDrawerOpen && (
            <button
              type="button"
              onClick={handleToggleCollapse}
              aria-label={isCollapsed ? expandLabel : collapseLabel}
              title={isCollapsed ? expandLabel : collapseLabel}
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)] transition ${
                isCollapsed ? "mx-auto" : ""
              }`}
            >
              <Icon
                name={isCollapsed ? "arrow-right" : "arrow-left"}
                size={14}
              />
            </button>
          )}

          {/* Mobile close button in drawer mode */}
          {(isMobile || isDrawerOpen) && (
            <button
              type="button"
              onClick={handleClose}
              aria-label={closeLabel}
              title={closeLabel}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)]"
            >
              <Icon name="close" size={16} />
            </button>
          )}
        </div>
      )}

      {/* Main Navigation Item List */}
      <div
        className={`flex-1 overflow-y-auto px-2 py-2.5 flex flex-col ${densityStyles.gap} ${bodyClassName}`}
      >
        {propGroups && propGroups.length > 0 ? (
          propGroups.map((group, gIdx) => (
            <div key={group.id ?? `group-${gIdx}`} className="flex flex-col gap-1 my-1">
              {!isCollapsed && group.title && (
                <div className="px-2.5 py-1 text-[0.6875rem] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  {group.title}
                </div>
              )}
              {group.items.map((item) => {
                const globalIdx = flattenedItems.findIndex(
                  (fi) => getItemKey(fi, -1) === getItemKey(item, -1),
                );
                return renderItem(item, globalIdx >= 0 ? globalIdx : 0);
              })}
            </div>
          ))
        ) : (
          flattenedItems.map((item, idx) => renderItem(item, idx))
        )}

        {children}
      </div>

      {/* Footer Slot */}
      {footer && (
        <div
          className={`border-t border-[color:var(--shell-border)]/60 p-2.5 ${footerClassName}`}
        >
          {footer}
        </div>
      )}
    </>
  );

  // Mobile drawer / sheet overlay rendering
  if (isMobile || isDrawerOpen) {
    if (!isDrawerOpen) return null;

    return (
      <div
        className="fixed inset-0 z-50 flex"
        data-testid={dataTestId}
        id={railId}
      >
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={handleClose}
          aria-hidden="true"
        />

        {/* Drawer panel with role="dialog" */}
        <div
          ref={drawerPanelRef}
          role="dialog"
          aria-modal="true"
          aria-label={ariaLabel}
          tabIndex={-1}
          className={`relative z-10 flex w-[280px] max-w-[85vw] flex-col border-r border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-2xl transition-transform ${className}`}
        >
          {railInnerContent}
        </div>
      </div>
    );
  }

  // Desktop side rail rendering
  return (
    <nav
      id={railId}
      role="navigation"
      aria-label={ariaLabel}
      data-testid={dataTestId}
      style={customWidthStyle}
      className={`flex flex-col shrink-0 border-r border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] transition-all duration-200 ${desktopWidthClass} ${className}`}
    >
      {railInnerContent}
    </nav>
  );
}

export default ContextRail;
