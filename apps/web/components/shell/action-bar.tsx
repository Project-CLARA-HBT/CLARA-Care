"use client";

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Link from "next/link";
import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

export type ActionBarVariant = "floating" | "sticky" | "inline";
export type ActionBarDensity = "comfortable" | "compact" | "dense";
export type ActionBarMaxWidth =
  | "prose"
  | "instrument"
  | "workbench"
  | "full-bleed"
  | "sm"
  | "md"
  | "lg"
  | "xl"
  | "2xl"
  | "3xl"
  | "4xl"
  | "full"
  | "default"
  | number
  | string;

export interface ActionBarAction {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: IconName | string;
  href?: string;
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  "data-testid"?: string;
  id?: string;
  title?: string;
  ariaLabel?: string;
}

export interface ActionBarProps
  extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Visual presentation mode */
  variant?: ActionBarVariant;
  /** Width boundary constraint */
  maxWidth?: ActionBarMaxWidth;
  /** Spacing density */
  density?: ActionBarDensity;
  /** Multi-step workflow: current 1-indexed step */
  step?: number;
  /** Multi-step workflow: total count of steps */
  totalSteps?: number;
  /** Custom step label override (e.g. "Bước 2/4: Tiền sử dị ứng") */
  stepLabel?: ReactNode;
  /** Whether to render a miniature step progress bar */
  showProgress?: boolean;
  /** Explicit 0–100 progress percentage */
  progress?: number;
  /** Status indicator / dirty state */
  dirty?: boolean;
  unsavedChangesLabel?: string;
  status?: ReactNode;
  message?: ReactNode;
  badge?: ReactNode;
  /** Main action buttons */
  primaryAction?: ActionBarAction | ReactNode;
  secondaryAction?: ActionBarAction | ReactNode;
  dangerAction?: ActionBarAction | ReactNode;
  /** Workflow navigation callbacks */
  onNext?: () => void;
  onPrevious?: () => void;
  onCancel?: () => void;
  onSave?: () => void;
  onReset?: () => void;
  /** Standard action button labels */
  nextLabel?: string;
  prevLabel?: string;
  cancelLabel?: string;
  saveLabel?: string;
  resetLabel?: string;
  /** Global loading / busy indicator */
  isBusy?: boolean;
  loading?: boolean;
  /** Slots */
  leading?: ReactNode;
  center?: ReactNode;
  trailing?: ReactNode;
  children?: ReactNode;
  /** Safe area bottom spacer reservation */
  reserveSafeArea?: boolean;
  /** Accessible role (default 'toolbar') */
  role?: string;
  "aria-label"?: string;
  /** Class name overrides */
  containerClassName?: string;
  "data-testid"?: string;
  id?: string;
}

const MAX_WIDTH_MAP: Record<string, string> = {
  prose: "max-w-3xl sm:max-w-4xl",
  instrument: "max-w-5xl",
  workbench: "max-w-7xl",
  "full-bleed": "max-w-full",
  sm: "max-w-2xl",
  md: "max-w-4xl",
  lg: "max-w-5xl",
  xl: "max-w-6xl",
  "2xl": "max-w-7xl",
  "3xl": "max-w-[1600px]",
  "4xl": "max-w-[1800px]",
  full: "max-w-full",
  default: "max-w-5xl",
};

const DENSITY_CONFIG: Record<
  ActionBarDensity,
  {
    padding: string;
    gap: string;
    btnPadding: string;
    btnHeight: string;
    textSize: string;
    iconSize: number;
  }
> = {
  comfortable: {
    padding: "px-5 py-3.5 sm:px-6 sm:py-4",
    gap: "gap-3 sm:gap-4",
    btnPadding: "px-4 py-2 sm:px-5 sm:py-2.5",
    btnHeight: "h-10 sm:h-11",
    textSize: "text-sm",
    iconSize: 18,
  },
  compact: {
    padding: "px-3.5 py-2.5 sm:px-4 sm:py-3",
    gap: "gap-2 sm:gap-3",
    btnPadding: "px-3 py-1.5 sm:px-4 sm:py-2",
    btnHeight: "h-8.5 sm:h-9.5",
    textSize: "text-xs sm:text-sm",
    iconSize: 16,
  },
  dense: {
    padding: "px-2.5 py-1.5 sm:px-3 sm:py-2",
    gap: "gap-1.5 sm:gap-2",
    btnPadding: "px-2.5 py-1 sm:px-3 sm:py-1.5",
    btnHeight: "h-7 sm:h-8",
    textSize: "text-xs",
    iconSize: 14,
  },
};

/**
 * ActionBar Primitive (Spec v8 §5.9)
 * Sticky / floating contextual bottom action bar for multi-step workflows,
 * form confirmations, step wizards, and bulk triage actions.
 */
export const ActionBar = forwardRef<HTMLElement, ActionBarProps>(
  (
    {
      variant = "floating",
      maxWidth = "default",
      density = "compact",
      step,
      totalSteps,
      stepLabel,
      showProgress = false,
      progress: propProgress,
      dirty = false,
      unsavedChangesLabel = "Chưa lưu thay đổi",
      status,
      message,
      badge,
      primaryAction,
      secondaryAction,
      dangerAction,
      onNext,
      onPrevious,
      onCancel,
      onSave,
      onReset,
      nextLabel = "Tiếp tục",
      prevLabel = "Quay lại",
      cancelLabel = "Hủy bỏ",
      saveLabel = "Lưu",
      resetLabel = "Đặt lại",
      isBusy: propIsBusy = false,
      loading: propLoading = false,
      leading,
      center,
      trailing,
      children,
      reserveSafeArea = false,
      role = "toolbar",
      "aria-label": ariaLabel = "Thanh thao tác quy trình",
      className = "",
      containerClassName = "",
      "data-testid": dataTestId = "action-bar",
      id: customId,
      ...rest
    },
    ref,
  ) => {
    const generatedId = useId();
    const barId = customId ?? `action-bar-${generatedId}`;
    const isBusy = propIsBusy || propLoading;

    // Resolve max width class
    const maxWClass =
      typeof maxWidth === "string" && MAX_WIDTH_MAP[maxWidth]
        ? MAX_WIDTH_MAP[maxWidth]
        : typeof maxWidth === "string"
          ? maxWidth
          : "max-w-5xl";

    const customWidthStyle =
      typeof maxWidth === "number" ? { maxWidth: `${maxWidth}px` } : undefined;

    const densityStyles = DENSITY_CONFIG[density] ?? DENSITY_CONFIG.compact;

    // Calculate percentage progress
    const computedProgress =
      propProgress !== undefined
        ? propProgress
        : step !== undefined && totalSteps !== undefined && totalSteps > 0
          ? Math.round((step / totalSteps) * 100)
          : undefined;

    // Keyboard shortcut handler (e.g. Cmd+S to save, Escape to cancel)
    const handleKeyDown = useCallback(
      (e: KeyboardEvent) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "s") {
          if (onSave) {
            e.preventDefault();
            onSave();
          }
        }
        if (e.key === "Escape" && onCancel) {
          onCancel();
        }
      },
      [onSave, onCancel],
    );

    useEffect(() => {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, [handleKeyDown]);

    // Render action button helper
    const renderAction = (
      action: ActionBarAction | ReactNode,
      fallbackType: "primary" | "secondary" | "danger",
    ) => {
      if (!action) return null;
      if (React.isValidElement(action)) {
        return action;
      }

      const actionObj = action as ActionBarAction;
      const type = actionObj.variant ?? fallbackType;
      const actionLoading = actionObj.loading || isBusy;
      const actionDisabled = Boolean(actionObj.disabled || actionLoading);

      let variantClasses =
        "bg-[var(--brand-600)] hover:bg-[var(--brand-500)] text-white font-semibold shadow-sm focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]";
      if (type === "secondary") {
        variantClasses =
          "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:bg-[var(--surface-muted)] text-[var(--text-primary)] font-medium shadow-xs focus-visible:ring-2 focus-visible:ring-[var(--focus-ring-color)]";
      } else if (type === "outline") {
        variantClasses =
          "border border-[color:var(--brand-500)]/40 bg-transparent hover:bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-medium focus-visible:ring-2 focus-visible:ring-[var(--brand-500)]";
      } else if (type === "danger") {
        variantClasses =
          "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] hover:bg-[var(--danger-600)] text-[var(--status-danger-text)] hover:text-white font-semibold focus-visible:ring-2 focus-visible:ring-[var(--danger-500)]";
      } else if (type === "ghost") {
        variantClasses =
          "border-transparent bg-transparent hover:bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)]";
      }

      const buttonClasses = `inline-flex items-center justify-center gap-1.5 select-none rounded-[var(--radius-lg)] transition-all duration-150 active:scale-[0.98] ${
        densityStyles.btnPadding
      } ${densityStyles.btnHeight} ${densityStyles.textSize} ${variantClasses} ${
        actionDisabled ? "opacity-50 cursor-not-allowed pointer-events-none" : "cursor-pointer"
      }`;

      const iconContent = actionLoading ? (
        <span
          className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent shrink-0"
          aria-hidden="true"
        />
      ) : actionObj.icon ? (
        <Icon
          name={resolveIconName(actionObj.icon)}
          size={densityStyles.iconSize}
          aria-hidden="true"
        />
      ) : null;

      if (actionObj.href && !actionDisabled) {
        return (
          <Link
            id={actionObj.id}
            href={actionObj.href}
            data-testid={actionObj["data-testid"]}
            title={actionObj.title || actionObj.label}
            aria-label={actionObj.ariaLabel || actionObj.label}
            className={buttonClasses}
            onClick={actionObj.onClick}
          >
            {iconContent}
            <span>{actionObj.label}</span>
          </Link>
        );
      }

      return (
        <button
          id={actionObj.id}
          type="button"
          data-testid={actionObj["data-testid"]}
          disabled={actionDisabled}
          title={actionObj.title || actionObj.label}
          aria-label={actionObj.ariaLabel || actionObj.label}
          className={buttonClasses}
          onClick={actionObj.onClick}
        >
          {iconContent}
          <span>{actionObj.label}</span>
        </button>
      );
    };

    // Inner action bar content layout
    const innerContent = (
      <div
        className={`flex w-full items-center justify-between ${densityStyles.gap} ${containerClassName}`}
      >
        {/* Left Section: Progress, Step Label, Status / Dirty indicator, or Leading slot */}
        <div className="flex min-w-0 flex-1 items-center gap-2.5 sm:gap-3.5 overflow-hidden">
          {leading ? (
            leading
          ) : (
            <>
              {/* Step indicator pill */}
              {(step !== undefined || stepLabel) && (
                <div className="flex items-center gap-2 shrink-0">
                  <div className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-500)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-semibold text-[var(--text-brand)]">
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)] animate-pulse"
                      aria-hidden="true"
                    />
                    <span>
                      {stepLabel ??
                        (totalSteps
                          ? `Bước ${step}/${totalSteps}`
                          : `Bước ${step}`)}
                    </span>
                  </div>
                </div>
              )}

              {/* Status / Message / Dirty notice */}
              <div className="min-w-0 flex-1 truncate text-xs text-[var(--text-secondary)]">
                {dirty ? (
                  <span className="inline-flex items-center gap-1.5 font-medium text-[var(--status-warn-text)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--warn-500)] shrink-0" />
                    <span>{unsavedChangesLabel}</span>
                  </span>
                ) : status ? (
                  <span className="font-medium text-[var(--text-primary)] truncate">
                    {status}
                  </span>
                ) : message ? (
                  <span className="truncate">{message}</span>
                ) : null}
              </div>

              {badge && <div className="shrink-0">{badge}</div>}
            </>
          )}
        </div>

        {/* Center slot (optional) */}
        {center && (
          <div className="hidden md:flex shrink-0 items-center justify-center">
            {center}
          </div>
        )}

        {/* Right Section: Action buttons (Previous, Cancel, Reset, Danger, Secondary, Next, Save, or Trailing) */}
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {trailing}

          {/* Previous / Back Action */}
          {onPrevious && (
            <button
              type="button"
              onClick={onPrevious}
              disabled={isBusy}
              aria-label={prevLabel}
              data-testid="action-bar-prev"
              className={`inline-flex items-center justify-center gap-1 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] hover:bg-[var(--surface-muted)] transition select-none ${
                densityStyles.btnPadding
              } ${densityStyles.btnHeight} ${densityStyles.textSize} ${
                isBusy ? "opacity-50 pointer-events-none" : "cursor-pointer"
              }`}
            >
              <Icon name="arrow-left" size={densityStyles.iconSize} />
              <span className="hidden sm:inline">{prevLabel}</span>
            </button>
          )}

          {/* Cancel Action */}
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isBusy}
              aria-label={cancelLabel}
              data-testid="action-bar-cancel"
              className={`inline-flex items-center justify-center rounded-[var(--radius-lg)] border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition select-none ${
                densityStyles.btnPadding
              } ${densityStyles.btnHeight} ${densityStyles.textSize} ${
                isBusy ? "opacity-50 pointer-events-none" : "cursor-pointer"
              }`}
            >
              <span>{cancelLabel}</span>
            </button>
          )}

          {/* Reset Action */}
          {onReset && (
            <button
              type="button"
              onClick={onReset}
              disabled={isBusy}
              aria-label={resetLabel}
              data-testid="action-bar-reset"
              className={`inline-flex items-center justify-center rounded-[var(--radius-lg)] border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition select-none ${
                densityStyles.btnPadding
              } ${densityStyles.btnHeight} ${densityStyles.textSize} ${
                isBusy ? "opacity-50 pointer-events-none" : "cursor-pointer"
              }`}
            >
              <span>{resetLabel}</span>
            </button>
          )}

          {/* Danger Action */}
          {dangerAction && renderAction(dangerAction, "danger")}

          {/* Secondary Action */}
          {secondaryAction && renderAction(secondaryAction, "secondary")}

          {/* Save Action */}
          {onSave &&
            !primaryAction &&
            renderAction(
              {
                label: saveLabel,
                onClick: onSave,
                loading: isBusy,
                icon: "check",
                variant: "primary",
                "data-testid": "action-bar-save",
              },
              "primary",
            )}

          {/* Next Action */}
          {onNext &&
            !primaryAction &&
            renderAction(
              {
                label: nextLabel,
                onClick: onNext,
                loading: isBusy,
                icon: "arrow-right",
                variant: "primary",
                "data-testid": "action-bar-next",
              },
              "primary",
            )}

          {/* Primary Action */}
          {primaryAction && renderAction(primaryAction, "primary")}

          {children}
        </div>
      </div>
    );

    // Progress bar strip at top of action bar
    const progressBarElement =
      showProgress && computedProgress !== undefined ? (
        <div
          className="absolute top-0 left-0 right-0 h-1 overflow-hidden bg-[var(--surface-muted)] rounded-t-2xl"
          role="progressbar"
          aria-valuenow={computedProgress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full bg-[var(--brand-500)] transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, computedProgress))}%` }}
          />
        </div>
      ) : null;

    // Floating variant: Elevated pill / surface floating above the bottom
    if (variant === "floating") {
      return (
        <>
          {reserveSafeArea && (
            <div
              data-testid="action-bar-safe-area-spacer"
              className="h-20 sm:h-24 pointer-events-none"
              aria-hidden="true"
            />
          )}

          <aside
            ref={ref}
            id={barId}
            role={role}
            aria-label={ariaLabel}
            data-testid={dataTestId}
            data-variant="floating"
            style={customWidthStyle}
            className={`fixed bottom-4 sm:bottom-6 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-1.5rem)] ${maxWClass} rounded-2xl border border-[color:var(--shell-border)]/90 bg-[var(--surface-header)]/95 shadow-2xl backdrop-blur-xl text-[var(--text-primary)] transition-all duration-200 ${densityStyles.padding} ${className}`}
            {...rest}
          >
            {progressBarElement}
            {innerContent}
          </aside>
        </>
      );
    }

    // Sticky variant: Docked at bottom of viewport / container
    if (variant === "sticky") {
      return (
        <footer
          ref={ref as React.Ref<HTMLElement>}
          id={barId}
          role={role}
          aria-label={ariaLabel}
          data-testid={dataTestId}
          data-variant="sticky"
          className={`sticky bottom-0 z-40 w-full border-t border-[color:var(--shell-border)] bg-[var(--surface-header)]/95 shadow-lg backdrop-blur-xl text-[var(--text-primary)] pb-[max(env(safe-area-inset-bottom,0px),0.25rem)] ${densityStyles.padding} ${className}`}
          {...rest}
        >
          {progressBarElement}
          <div className={`mx-auto w-full ${maxWClass}`} style={customWidthStyle}>
            {innerContent}
          </div>
        </footer>
      );
    }

    // Inline variant: standard static or embedded block
    return (
      <div
        ref={ref as React.Ref<HTMLDivElement>}
        id={barId}
        role={role}
        aria-label={ariaLabel}
        data-testid={dataTestId}
        data-variant="inline"
        style={customWidthStyle}
        className={`relative w-full rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm text-[var(--text-primary)] ${densityStyles.padding} ${className}`}
        {...rest}
      >
        {progressBarElement}
        {innerContent}
      </div>
    );
  },
);

ActionBar.displayName = "ActionBar";

export default ActionBar;
