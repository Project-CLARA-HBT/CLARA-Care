"use client";

import React, {
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Sheet, { type SheetSize } from "./sheet";
import Button from "./button";
import Icon from "./icon";

export type InspectorDensity = "comfortable" | "compact" | "dense";
export type InspectorMode = "slide-over" | "inline";

export interface InspectorProps {
  /** Controlled open state for slide-over mode */
  open?: boolean;
  /** Close callback */
  onClose?: () => void;
  /** Primary entity title */
  title: ReactNode;
  /** Optional subtitle or descriptive text */
  subtitle?: ReactNode;
  /** Optional single badge or multiple badges */
  badge?: ReactNode;
  badges?: ReactNode;
  /** Header action buttons or menu */
  actions?: ReactNode;
  /** Main body content */
  children: ReactNode;
  /** Optional footer action bar */
  footer?: ReactNode;
  /** Mode: slide-over drawer or inline panel */
  mode?: InspectorMode;
  /** Drawer slide direction (for slide-over mode) */
  side?: "right" | "left";
  /** Drawer width size preset */
  size?: SheetSize;
  /** Density preset */
  density?: InspectorDensity;
  /** Close button aria-label */
  closeLabel?: string;
  /** Accessibility role (defaults to dialog) */
  role?: "dialog" | "alertdialog";
  /** Additional container styling */
  className?: string;
  bodyClassName?: string;
  headerClassName?: string;
  footerClassName?: string;
}

export interface InspectorSectionProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  className?: string;
}

export interface InspectorFieldProps {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  copyable?: boolean;
  vertical?: boolean;
  className?: string;
}

const DENSITY_SPACING: Record<InspectorDensity, { body: string; section: string }> = {
  comfortable: {
    body: "p-6 space-y-6",
    section: "py-4",
  },
  compact: {
    body: "p-4 sm:p-5 space-y-4",
    section: "py-3",
  },
  dense: {
    body: "p-3 space-y-3 text-xs",
    section: "py-2",
  },
};

export function InspectorSection({
  title,
  description,
  actions,
  children,
  collapsible = false,
  defaultExpanded = true,
  className = "",
  ...rest
}: InspectorSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden transition-all ${className}`}
      {...rest}
    >
      {(title || description || actions) && (
        <div
          className={`flex items-center justify-between gap-3 border-b border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 px-4 py-2.5 ${
            collapsible ? "cursor-pointer select-none hover:bg-[var(--surface-muted)]" : ""
          }`}
          onClick={collapsible ? () => setIsExpanded((prev) => !prev) : undefined}
          role={collapsible ? "button" : undefined}
          aria-expanded={collapsible ? isExpanded : undefined}
          tabIndex={collapsible ? 0 : undefined}
          onKeyDown={
            collapsible
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setIsExpanded((prev) => !prev);
                  }
                }
              : undefined
          }
        >
          <div className="min-w-0 flex-1">
            {title && (
              <h3 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                {collapsible && (
                  <svg
                    className={`h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)] transition-transform duration-200 ${
                      isExpanded ? "rotate-90" : ""
                    }`}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                )}
                {title}
              </h3>
            )}
            {description && (
              <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{description}</p>
            )}
          </div>

          {actions && (
            <div
              className="flex shrink-0 items-center gap-1.5"
              onClick={(e) => e.stopPropagation()}
            >
              {actions}
            </div>
          )}
        </div>
      )}

      {(!collapsible || isExpanded) && (
        <div className="p-4 text-sm text-[var(--text-primary)]">{children}</div>
      )}
    </div>
  );
}

export function InspectorField({
  label,
  value,
  hint,
  copyable = false,
  vertical = false,
  className = "",
}: InspectorFieldProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (typeof value === "string" || typeof value === "number") {
      try {
        await navigator.clipboard.writeText(String(value));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        // Fallback ignore
      }
    }
  };

  return (
    <div
      className={`flex gap-2 py-1.5 ${
        vertical
          ? "flex-col items-start"
          : "flex-col sm:flex-row sm:items-baseline sm:justify-between"
      } ${className}`}
    >
      <div className="min-w-0">
        <span className="text-xs font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        {hint && (
          <p className="text-[0.6875rem] text-[var(--text-tertiary)]">{hint}</p>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <div className="text-xs sm:text-sm font-medium text-[var(--text-primary)] break-all">
          {value}
        </div>
        {copyable && (
          <button
            type="button"
            onClick={handleCopy}
            title={copied ? "Đã sao chép" : "Sao chép"}
            aria-label={copied ? "Đã sao chép" : "Sao chép giá trị"}
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-sm)] text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring-color)]"
          >
            {copied ? (
              <Icon name="check" size={12} className="text-[var(--brand-500)]" />
            ) : (
              <Icon name="clinical-notes" size={12} />
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export function Inspector({
  open = true,
  onClose,
  title,
  subtitle,
  badge,
  badges,
  actions,
  children,
  footer,
  mode = "slide-over",
  side = "right",
  size = "md",
  density = "compact",
  closeLabel = "Đóng bộ kiểm tra",
  role = "dialog",
  className = "",
  bodyClassName = "",
  headerClassName = "",
  footerClassName = "",
}: InspectorProps) {
  const densityStyles = DENSITY_SPACING[density] ?? DENSITY_SPACING.compact;

  const headerContent = (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base sm:text-lg font-semibold text-[var(--text-primary)]">
          {title}
        </span>
        {badge ? <div>{badge}</div> : null}
        {badges ? (
          <div className="inline-flex items-center gap-1.5">{badges}</div>
        ) : null}
      </div>
      {subtitle ? (
        <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
          {subtitle}
        </p>
      ) : null}
    </div>
  );

  // If slide-over mode, leverage the accessible Sheet component
  if (mode === "slide-over") {
    return (
      <Sheet
        open={open}
        onClose={onClose || (() => {})}
        side={side}
        size={size}
        role={role}
        closeLabel={closeLabel}
        headerActions={actions}
        headerClassName={headerClassName}
        bodyClassName={`${densityStyles.body} ${bodyClassName}`}
        footerClassName={footerClassName}
        title={headerContent}
        footer={footer}
        className={className}
      >
        {children}
      </Sheet>
    );
  }

  // Inline mode: render structured panel
  return (
    <aside
      role="region"
      aria-label={typeof title === "string" ? title : "Bộ kiểm tra"}
      className={`flex flex-col rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm text-[var(--text-primary)] ${className}`}
    >
      {/* Header */}
      <div
        className={`flex items-start justify-between gap-4 border-b border-[color:var(--shell-border)] px-5 py-4 ${headerClassName}`}
      >
        {headerContent}
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          {onClose && (
            <Button
              variant="ghost"
              size="sm"
              icon="close"
              aria-label={closeLabel}
              onClick={onClose}
              className="!min-h-8 !w-8 !p-0 shrink-0 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            />
          )}
        </div>
      </div>

      {/* Body */}
      <div className={`flex-1 overflow-y-auto ${densityStyles.body} ${bodyClassName}`}>
        {children}
      </div>

      {/* Footer */}
      {footer ? (
        <div
          className={`flex flex-wrap items-center justify-end gap-3 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-3.5 ${footerClassName}`}
        >
          {footer}
        </div>
      ) : null}
    </aside>
  );
}

export default Inspector;
