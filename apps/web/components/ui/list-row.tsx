"use client";

import React, { forwardRef, type ElementType, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import Link from "next/link";

export type ListRowDensity = "comfortable" | "compact" | "dense";

export interface ListRowProps {
  /** Leading visual: icon, avatar, status indicator, or checkbox */
  leading?: ReactNode;
  /** Primary title text or element */
  title: ReactNode;
  /** Optional secondary subtitle or description */
  subtitle?: ReactNode;
  /** Optional badges or status chips displayed alongside title */
  badges?: ReactNode;
  /** Optional metadata, timestamps, or secondary info */
  meta?: ReactNode;
  /** Trailing content: action buttons, chevron, or status indicators */
  trailing?: ReactNode;
  /** Link URL when row should act as a navigation link */
  href?: string;
  /** Click handler for interactive rows */
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  /** Row density preset */
  density?: ListRowDensity;
  /** Selected / active state */
  selected?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Override rendered HTML tag */
  as?: "div" | "li" | "button" | "a";
  /** Optional additional CSS classes */
  className?: string;
  /** Optional custom ID */
  id?: string;
  /** Optional accessibility label */
  ariaLabel?: string;
  /** Additional children */
  children?: ReactNode;
}

const DENSITY_STYLES: Record<
  ListRowDensity,
  {
    container: string;
    leading: string;
    title: string;
    subtitle: string;
    meta: string;
    trailing: string;
  }
> = {
  comfortable: {
    container: "min-h-[56px] px-4 py-3.5 gap-3.5 text-base",
    leading: "min-w-[2.25rem] text-lg",
    title: "text-base font-semibold leading-snug",
    subtitle: "text-sm leading-relaxed mt-0.5",
    meta: "text-xs leading-normal",
    trailing: "gap-2.5",
  },
  compact: {
    container: "min-h-[44px] px-3.5 py-2.5 gap-3 text-sm",
    leading: "min-w-[1.75rem] text-base",
    title: "text-sm font-medium leading-snug",
    subtitle: "text-xs leading-normal mt-0.5",
    meta: "text-xs leading-normal",
    trailing: "gap-2",
  },
  dense: {
    container: "min-h-[36px] px-2.5 py-1.5 gap-2 text-xs",
    leading: "min-w-[1.25rem] text-sm",
    title: "text-xs font-medium leading-tight",
    subtitle: "text-[0.6875rem] leading-tight mt-0.5",
    meta: "text-[0.6875rem] leading-tight",
    trailing: "gap-1.5",
  },
};

export const ListRow = forwardRef<HTMLElement, ListRowProps>(function ListRow(
  {
    leading,
    title,
    subtitle,
    badges,
    meta,
    trailing,
    href,
    onClick,
    density = "compact",
    selected = false,
    disabled = false,
    as,
    className = "",
    id,
    ariaLabel,
    children,
    ...rest
  },
  ref,
) {
  const densityConfig = DENSITY_STYLES[density] ?? DENSITY_STYLES.compact;
  const isInteractive = Boolean(href || onClick) && !disabled;

  const baseClasses = [
    "group relative flex w-full items-center justify-between rounded-[var(--radius-lg)] border border-transparent transition-all duration-150 text-left",
    densityConfig.container,
    // Interactive states
    isInteractive
      ? "cursor-pointer hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)] active:bg-[var(--surface-muted)]/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface-canvas)]"
      : "",
    // Selected state
    selected
      ? "border-[color:var(--brand-500)]/40 bg-[var(--surface-brand-soft)] text-[var(--text-primary)] shadow-sm font-medium"
      : "text-[var(--text-primary)]",
    // Disabled state
    disabled ? "opacity-50 cursor-not-allowed pointer-events-none select-none" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (disabled) return;
    if ((event.key === "Enter" || event.key === " ") && onClick) {
      event.preventDefault();
      onClick(event as unknown as MouseEvent<HTMLElement>);
    }
  };

  const content = (
    <>
      {/* Left side: leading visual + text content */}
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {leading ? (
          <div
            className={`flex shrink-0 items-center justify-center text-[var(--text-secondary)] ${densityConfig.leading}`}
            aria-hidden="true"
          >
            {leading}
          </div>
        ) : null}

        <div className="min-w-0 flex-1 flex flex-col justify-center">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`truncate text-[var(--text-primary)] group-hover:text-[var(--text-primary)] ${densityConfig.title} ${
                selected ? "text-[var(--text-brand)]" : ""
              }`}
            >
              {title}
            </span>
            {badges ? (
              <div className="inline-flex shrink-0 items-center gap-1.5">{badges}</div>
            ) : null}
          </div>

          {subtitle ? (
            <div className={`truncate text-[var(--text-secondary)] ${densityConfig.subtitle}`}>
              {subtitle}
            </div>
          ) : null}

          {children ? <div className="mt-1">{children}</div> : null}
        </div>
      </div>

      {/* Right side: metadata + trailing controls */}
      {(meta || trailing) && (
        <div className={`flex shrink-0 items-center pl-3 ${densityConfig.trailing}`}>
          {meta ? (
            <div className={`text-right text-[var(--text-tertiary)] ${densityConfig.meta}`}>
              {meta}
            </div>
          ) : null}

          {trailing ? (
            <div className="flex shrink-0 items-center text-[var(--text-secondary)]">
              {trailing}
            </div>
          ) : null}
        </div>
      )}
    </>
  );

  // If href is present and not disabled, render Next.js Link
  if (href && !disabled) {
    return (
      <Link
        href={href}
        ref={ref as React.Ref<HTMLAnchorElement>}
        id={id}
        aria-label={ariaLabel}
        aria-selected={selected || undefined}
        aria-disabled={disabled || undefined}
        className={baseClasses}
      >
        {content}
      </Link>
    );
  }

  // If onClick is present and not explicitly another tag, default to button semantics
  const Component: ElementType =
    as || (onClick ? "button" : "div");

  const componentProps: Record<string, any> = {
    ref,
    id,
    className: baseClasses,
    "aria-label": ariaLabel,
    "aria-selected": selected || undefined,
    "aria-disabled": disabled || undefined,
    ...rest,
  };

  if (Component === "button") {
    componentProps.type = "button";
    componentProps.disabled = disabled;
    if (onClick && !disabled) {
      componentProps.onKeyDown = handleKeyDown;
    }
  } else if (onClick && !disabled) {
    componentProps.role = "button";
    componentProps.tabIndex = 0;
    componentProps.onKeyDown = handleKeyDown;
  }

  if (onClick && !disabled) {
    componentProps.onClick = onClick;
  }

  return <Component {...componentProps}>{content}</Component>;
});

export default ListRow;
