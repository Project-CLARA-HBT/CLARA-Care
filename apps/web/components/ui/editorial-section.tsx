"use client";

import type { ElementType, ReactNode } from "react";
import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

export type EditorialSectionMaxWidth =
  | "reading"
  | "sm"
  | "md"
  | "lg"
  | "xl"
  | "2xl"
  | "3xl"
  | "4xl"
  | "5xl"
  | "6xl"
  | "7xl"
  | "full"
  | "none";

export type EditorialSectionVariant =
  | "default"
  | "card"
  | "subtle"
  | "plain"
  | "inset";

export interface EditorialSectionProps {
  /** Section title */
  title?: ReactNode;
  /** Editorial description or subtitle */
  description?: ReactNode;
  /** Uppercase eyebrow tag above the title */
  eyebrow?: ReactNode;
  /** Optional trailing action in header (e.g. 'View all' link, buttons) */
  action?: ReactNode;
  /** Leading icon for header */
  icon?: IconName | string | ReactNode;
  /** Badge adjacent to title */
  badge?: ReactNode;
  /** Enforced max-reading-width constraint */
  maxWidth?: EditorialSectionMaxWidth;
  /** Visual presentation variant */
  variant?: EditorialSectionVariant;
  /** HTML element type for semantic markup */
  as?: "section" | "article" | "div" | "main";
  id?: string;
  "aria-labelledby"?: string;
  headerClassName?: string;
  contentClassName?: string;
  className?: string;
  children?: ReactNode;
}

const MAX_WIDTH_STYLES: Record<EditorialSectionMaxWidth, string> = {
  reading: "max-w-[68ch]",
  sm: "max-w-screen-sm",
  md: "max-w-screen-md",
  lg: "max-w-screen-lg",
  xl: "max-w-screen-xl",
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
  "4xl": "max-w-4xl",
  "5xl": "max-w-5xl",
  "6xl": "max-w-6xl",
  "7xl": "max-w-7xl",
  full: "max-w-full",
  none: "",
};

const VARIANT_STYLES: Record<EditorialSectionVariant, string> = {
  default: "space-y-4",
  card: "rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6 shadow-sm space-y-4",
  subtle:
    "rounded-[var(--radius-xl)] bg-[var(--surface-muted)]/50 border border-[color:var(--shell-border)]/40 p-5 sm:p-6 space-y-4",
  plain: "space-y-4",
  inset:
    "rounded-[var(--radius-lg)] bg-[var(--surface-lowest,#0b0e13)] border border-[color:var(--shell-border)]/30 p-4 sm:p-5 space-y-3",
};

function renderHeaderIcon(icon: IconName | string | ReactNode) {
  if (!icon) return null;
  if (typeof icon === "string") {
    return <Icon name={resolveIconName(icon)} size={20} aria-hidden="true" />;
  }
  return <span className="inline-flex shrink-0 items-center">{icon}</span>;
}

export function EditorialSection({
  title,
  description,
  eyebrow,
  action,
  icon,
  badge,
  maxWidth = "none",
  variant = "default",
  as = "section",
  id,
  "aria-labelledby": ariaLabelledby,
  headerClassName = "",
  contentClassName = "",
  className = "",
  children,
}: EditorialSectionProps) {
  const Component = as as ElementType;
  const maxWidthClass = MAX_WIDTH_STYLES[maxWidth] ?? "";
  const variantClass = VARIANT_STYLES[variant] ?? VARIANT_STYLES.default;
  const headingId = id ? `${id}-heading` : undefined;
  const resolvedAriaLabelledby = ariaLabelledby ?? (title ? headingId : undefined);

  const hasHeader = Boolean(title) || Boolean(description) || Boolean(eyebrow) || Boolean(action);

  return (
    <Component
      id={id}
      aria-labelledby={resolvedAriaLabelledby}
      className={`${variantClass} ${maxWidthClass} ${className}`}
    >
      {hasHeader && (
        <header className={`space-y-1.5 ${headerClassName}`}>
          {/* Eyebrow */}
          {eyebrow && (
            <div className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              {eyebrow}
            </div>
          )}

          {/* Title Row with optional Icon, Badge, and Trailing Action */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 min-w-0">
              {icon && (
                <span className="shrink-0 text-[var(--text-brand)]">
                  {renderHeaderIcon(icon)}
                </span>
              )}

              {title && (
                <h2
                  id={headingId}
                  className="text-lg font-bold tracking-tight text-[var(--text-primary)] sm:text-xl"
                >
                  {title}
                </h2>
              )}

              {badge && <div className="shrink-0">{badge}</div>}
            </div>

            {action && <div className="shrink-0">{action}</div>}
          </div>

          {/* Editorial Description */}
          {description && (
            <p className="max-w-[68ch] text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
              {description}
            </p>
          )}
        </header>
      )}

      {/* Section Content */}
      {children && <div className={contentClassName}>{children}</div>}
    </Component>
  );
}

export default EditorialSection;
