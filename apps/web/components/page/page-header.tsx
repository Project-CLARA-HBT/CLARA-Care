"use client";

import React, {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/icon";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  onClick?: () => void;
  active?: boolean;
}

export interface PageHeaderBackAction {
  label?: string;
  href?: string;
  onClick?: () => void;
  ariaLabel?: string;
}

export interface PageHeaderProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Small category/domain eyebrow above title */
  eyebrow?: ReactNode;
  /** Primary page title (rendered as h1 by default) */
  title: ReactNode;
  /** Secondary subtitle or description */
  subtitle?: ReactNode;
  /** Alias for subtitle */
  description?: ReactNode;
  /** Status chips or badge tags */
  badges?: ReactNode;
  /** Single badge alias */
  badge?: ReactNode;
  /** Breadcrumb navigation items or custom node */
  breadcrumbs?: BreadcrumbItem[] | ReactNode;
  /** Trailing action buttons or controls slot */
  actions?: ReactNode;
  /** Alias for actions */
  trailing?: ReactNode;
  /** Back navigation button/link */
  backAction?: PageHeaderBackAction;
  /** Additional metadata row (e.g. author, timestamp, ID) */
  meta?: ReactNode;
  /** Enable sticky header with background blur */
  sticky?: boolean;
  /** Add a bottom divider border */
  border?: boolean;
  /** Density variant */
  density?: "comfortable" | "compact";
  /** Title HTML tag */
  titleAs?: "h1" | "h2" | "h3";
  /** Explicit title element ID for ARIA linking */
  titleId?: string;
  /** Additional class names */
  className?: string;
}

/**
 * Standard page header primitive.
 * Supports eyebrow, title, subtitle, badges, breadcrumbs, and trailing action slot.
 */
export const PageHeader = forwardRef<HTMLElement, PageHeaderProps>(
  (
    {
      eyebrow,
      title,
      subtitle,
      description,
      badges,
      badge,
      breadcrumbs,
      actions,
      trailing,
      backAction,
      meta,
      sticky = false,
      border = false,
      density = "comfortable",
      titleAs: TitleTag = "h1",
      titleId,
      className = "",
      ...rest
    },
    ref
  ) => {
    const desc = subtitle ?? description;
    const resolvedBadges = badges ?? badge;
    const resolvedActions = actions ?? trailing;

    const renderBreadcrumbs = () => {
      if (!breadcrumbs) return null;

      if (React.isValidElement(breadcrumbs)) {
        return <div className="mb-2">{breadcrumbs}</div>;
      }

      if (Array.isArray(breadcrumbs) && breadcrumbs.length > 0) {
        return (
          <nav aria-label="Breadcrumbs" className="mb-2 flex items-center">
            <ol className="flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              {breadcrumbs.map((item, index) => {
                const isLast = index === breadcrumbs.length - 1;
                const isCurrent = item.active ?? isLast;

                return (
                  <li key={item.label + index} className="inline-flex items-center gap-1.5">
                    {index > 0 && (
                      <Icon
                        name="arrow-right"
                        size="0.75rem"
                        className="text-[var(--text-muted)] opacity-60"
                        aria-hidden="true"
                      />
                    )}
                    {item.href && !isCurrent ? (
                      <Link
                        href={item.href}
                        className="hover:text-[var(--text-primary)] hover:underline focus-ring rounded transition-colors"
                      >
                        {item.label}
                      </Link>
                    ) : item.onClick && !isCurrent ? (
                      <button
                        type="button"
                        onClick={item.onClick}
                        className="hover:text-[var(--text-primary)] hover:underline focus-ring rounded transition-colors"
                      >
                        {item.label}
                      </button>
                    ) : (
                      <span
                        aria-current={isCurrent ? "page" : undefined}
                        className={isCurrent ? "font-semibold text-[var(--text-primary)]" : ""}
                      >
                        {item.label}
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>
        );
      }

      return null;
    };

    const renderBackAction = () => {
      if (!backAction) return null;

      const label = backAction.label ?? "Quay lại";
      const ariaLabel = backAction.ariaLabel ?? label;

      if (backAction.href) {
        return (
          <Link
            href={backAction.href}
            aria-label={ariaLabel}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors focus-ring rounded"
          >
            <Icon name="arrow-left" size="0.875rem" aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      }

      if (backAction.onClick) {
        return (
          <button
            type="button"
            onClick={backAction.onClick}
            aria-label={ariaLabel}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors focus-ring rounded"
          >
            <Icon name="arrow-left" size="0.875rem" aria-hidden="true" />
            <span>{label}</span>
          </button>
        );
      }

      return null;
    };

    const isCompact = density === "compact";

    return (
      <header
        ref={ref}
        className={`w-full ${
          sticky
            ? "sticky top-0 z-20 bg-[var(--surface-header)]/95 backdrop-blur-md transition-all"
            : ""
        } ${
          border ? "border-b border-[color:var(--shell-border)] pb-4 sm:pb-5" : ""
        } ${className}`}
        {...rest}
      >
        {renderBreadcrumbs()}
        {renderBackAction()}

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1 space-y-1">
            {eyebrow ? (
              <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">
                {eyebrow}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2.5">
              <TitleTag
                id={titleId}
                className={`${
                  isCompact
                    ? "text-xl sm:text-2xl font-bold leading-tight"
                    : "text-2xl sm:text-3xl font-bold leading-tight"
                } tracking-[-0.02em] text-[var(--text-primary)]`}
              >
                {title}
              </TitleTag>

              {resolvedBadges ? (
                <div className="inline-flex items-center gap-1.5">{resolvedBadges}</div>
              ) : null}
            </div>

            {desc ? (
              <div
                className={`max-w-[72ch] text-[var(--text-secondary)] ${
                  isCompact ? "text-xs sm:text-sm leading-5" : "text-sm sm:text-base leading-6"
                }`}
              >
                {desc}
              </div>
            ) : null}

            {meta ? (
              <div className="pt-1 text-xs text-[var(--text-muted)] flex flex-wrap items-center gap-3">
                {meta}
              </div>
            ) : null}
          </div>

          {resolvedActions ? (
            <div className="flex shrink-0 flex-wrap items-center gap-2.5 sm:self-start">
              {resolvedActions}
            </div>
          ) : null}
        </div>
      </header>
    );
  }
);

PageHeader.displayName = "PageHeader";

export default PageHeader;
