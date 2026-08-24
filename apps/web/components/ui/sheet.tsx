"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Button from "./button";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "button:not([disabled])",
  "iframe",
  "object",
  "embed",
  "[contenteditable]:not([contenteditable='false'])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function getFocusableElements(container: HTMLElement): HTMLElement[] {
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

export type SheetSide = "right" | "left" | "top" | "bottom";
export type SheetSize = "sm" | "md" | "lg" | "xl" | "full";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  side?: SheetSide;
  size?: SheetSize;
  closeLabel?: string;
  role?: "dialog" | "alertdialog";
  ariaLabel?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  dismissible?: boolean;
  className?: string;
  headerClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  headerActions?: ReactNode;
  showCloseButton?: boolean;
  "data-testid"?: string;
  id?: string;
}

interface SheetContextValue {
  titleId: string;
  descriptionId: string;
  onClose: () => void;
}

const SheetContext = createContext<SheetContextValue | null>(null);

export function useSheetContext() {
  const context = useContext(SheetContext);
  if (!context) {
    throw new Error("Sheet subcomponents must be used within a Sheet");
  }
  return context;
}

const SIDE_CLASSES: Record<SheetSide, string> = {
  right: "top-0 right-0 h-full border-l border-[color:var(--shell-border)] shadow-2xl",
  left: "top-0 left-0 h-full border-r border-[color:var(--shell-border)] shadow-2xl",
  top: "top-0 left-0 right-0 max-h-[90vh] border-b border-[color:var(--shell-border)] rounded-b-[var(--radius-2xl)] shadow-2xl",
  bottom: "bottom-0 left-0 right-0 max-h-[90vh] border-t border-[color:var(--shell-border)] rounded-t-[var(--radius-2xl)] shadow-2xl",
};

const WIDTH_CLASSES: Record<SheetSize, string> = {
  sm: "max-w-sm w-full",
  md: "max-w-md w-full",
  lg: "max-w-xl w-full",
  xl: "max-w-3xl w-full",
  full: "max-w-full w-full",
};

export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  side = "right",
  size = "md",
  closeLabel = "Đóng",
  role = "dialog",
  ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  dismissible = true,
  className = "",
  headerClassName = "",
  bodyClassName = "",
  footerClassName = "",
  headerActions,
  showCloseButton = true,
  "data-testid": dataTestId,
  id: customId,
}: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const sheetId = useId();
  const titleId = `${sheetId}-title`;
  const descriptionId = `${sheetId}-description`;

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!dismissible && event.key === "Escape") return;
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;

      const nodes = getFocusableElements(panel);

      if (nodes.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }

      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;

      if (event.shiftKey && (activeEl === first || activeEl === panel || !panel.contains(activeEl))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (activeEl === last || !panel.contains(activeEl))) {
        event.preventDefault();
        first.focus();
      }
    },
    [dismissible, onClose],
  );

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    const panel = panelRef.current;
    const focusable = panel ? getFocusableElements(panel)[0] : null;
    (focusable ?? panel)?.focus();

    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused.current?.focus?.();
    };
  }, [open, onKeyDown]);

  if (!open) return null;

  const isVertical = side === "top" || side === "bottom";
  const sizeClasses = isVertical ? "w-full" : WIDTH_CLASSES[size];

  return (
    <SheetContext.Provider value={{ titleId, descriptionId, onClose }}>
      <div className="fixed inset-0 z-[80] overflow-hidden">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-[rgba(16,20,25,0.72)] backdrop-blur-[2px] transition-opacity animate-in fade-in duration-200"
          aria-hidden="true"
          onClick={dismissible ? onClose : undefined}
        />

          {/* Slide-over Container */}
          <div
            ref={panelRef}
            id={customId}
            data-testid={dataTestId}
            role={role}
            aria-modal="true"
            aria-label={ariaLabel}
            aria-labelledby={ariaLabel ? undefined : (ariaLabelledBy ?? (title || children ? titleId : undefined))}
            aria-describedby={ariaDescribedBy ?? (description ? descriptionId : undefined)}
            tabIndex={-1}
            className={`fixed z-[81] flex flex-col bg-[var(--surface-panel)] text-[var(--text-primary)] transition-transform duration-200 ease-out focus-visible:outline-none ${SIDE_CLASSES[side]} ${sizeClasses} ${className}`}
          >
          {/* Header if title or custom header provided */}
          {(title || description || showCloseButton || headerActions) && (
            <div
              className={`flex items-start justify-between gap-4 border-b border-[color:var(--shell-border)] px-6 py-4.5 shrink-0 ${headerClassName}`}
            >
              <div className="min-w-0 flex-1">
                {title ? (
                  <h2
                    id={titleId}
                    className="text-base sm:text-lg font-semibold text-[var(--text-primary)]"
                  >
                    {title}
                  </h2>
                ) : null}
                {description ? (
                  <p
                    id={descriptionId}
                    className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed"
                  >
                    {description}
                  </p>
                ) : null}
              </div>

              <div className="flex shrink-0 items-center gap-2">
                {headerActions}
                {showCloseButton && (
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
          )}

          {/* Scrollable Body */}
          <div
            className={`flex-1 overflow-y-auto px-6 py-5 focus-visible:outline-none ${bodyClassName}`}
          >
            {children}
          </div>

          {/* Footer */}
          {footer ? (
            <div
              className={`flex flex-wrap items-center justify-end gap-3 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-6 py-4 shrink-0 ${footerClassName}`}
            >
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    </SheetContext.Provider>
  );
}

/* Subcomponents for granular composition */

export function SheetHeader({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`flex items-start justify-between gap-4 border-b border-[color:var(--shell-border)] px-6 py-4.5 shrink-0 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function SheetTitle({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  const { titleId } = useSheetContext();
  return (
    <h2
      id={titleId}
      className={`text-base sm:text-lg font-semibold text-[var(--text-primary)] ${className}`}
      {...props}
    >
      {children}
    </h2>
  );
}

export function SheetDescription({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  const { descriptionId } = useSheetContext();
  return (
    <p
      id={descriptionId}
      className={`mt-1 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed ${className}`}
      {...props}
    >
      {children}
    </p>
  );
}

export function SheetBody({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`flex-1 overflow-y-auto px-6 py-5 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function SheetFooter({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`flex flex-wrap items-center justify-end gap-3 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-6 py-4 shrink-0 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export default Sheet;
