"use client";

import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

import { useFocusTrap } from "@/app/chat/_v2/lib/useFocusTrap";
import { Icon, type IconName } from "@/components/ui/icon";

/**
 * Shared, accessible design-system primitives for the rebuilt CLARA Chat
 * (CHAT_V2). These build on the app's existing CSS-variable token layer
 * (`globals.css`) so light/dark are consistent (Requirement 4.1, 4.2) and every
 * interactive primitive ships consistent hover/focus-visible/active/disabled
 * states (Requirement 4.3, 5.5).
 */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

const BASE_BUTTON =
  "inline-flex items-center justify-center gap-1.5 rounded-xl font-semibold transition " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-canvas)] " +
  "disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "border border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)] active:bg-[var(--brand-700)]",
  secondary:
    "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)]",
  ghost:
    "border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
  danger:
    "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] hover:brightness-105",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "min-h-[34px] px-3 text-[12px]",
  md: "min-h-[42px] px-4 text-sm",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "secondary",
      size = "md",
      className = "",
      type = "button",
      ...rest
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type={type}
        className={[
          BASE_BUTTON,
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        ].join(" ")}
        {...rest}
      />
    );
  },
);

const ICON_BUTTON_NAMES: Record<string, IconName> = {
  add: "medication",
  close: "close",
  menu: "menu",
  stop: "stop",
  arrow_upward: "send",
  light_mode: "theme",
  dark_mode: "theme",
  notifications: "notifications",
  more_horiz: "more",
  arrow_forward: "arrow-right",
  bolt: "progress",
  dock_to_left: "folder",
};

export type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** Accessible label is required — icon-only buttons must be named (Req 5.2). */
  label: string;
  /**
   * Legacy call-sites use Material glyph identifiers; resolve each supported
   * identifier at compile time so a missing webfont can never render its name.
   */
  icon: keyof typeof ICON_BUTTON_NAMES;
  variant?: ButtonVariant;
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    {
      label,
      icon,
      variant = "ghost",
      className = "",
      type = "button",
      ...rest
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type={type}
        aria-label={label}
        title={label}
        className={[
          BASE_BUTTON,
          VARIANT_CLASSES[variant],
          "h-9 w-9 p-0 text-[var(--text-secondary)]",
          className,
        ].join(" ")}
        {...rest}
      >
        <Icon name={ICON_BUTTON_NAMES[icon]} size={18} />
      </button>
    );
  },
);

export type StatusTone = "ok" | "warn" | "danger" | "info" | "neutral";

const STATUS_DOT_CLASSES: Record<StatusTone, string> = {
  ok: "bg-[var(--success-500)]",
  warn: "bg-[var(--warn-500)]",
  danger: "bg-[var(--danger-500)]",
  info: "bg-[var(--brand-500)]",
  neutral: "bg-[color:var(--text-muted)]",
};

export function StatusDot({
  tone,
  pulse = false,
  className = "",
}: {
  tone: StatusTone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={[
        "inline-block h-2.5 w-2.5 shrink-0 rounded-full",
        STATUS_DOT_CLASSES[tone],
        pulse ? "motion-safe:animate-pulse" : "",
        className,
      ].join(" ")}
    />
  );
}

export function Badge({
  children,
  tone = "info",
  className = "",
}: {
  children: ReactNode;
  tone?: StatusTone;
  className?: string;
}) {
  const toneClass: Record<StatusTone, string> = {
    ok: "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
    warn: "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
    danger:
      "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
    info: "border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
    neutral:
      "border-[color:var(--status-neutral-border)] bg-[var(--status-neutral-bg)] text-[var(--status-neutral-text)]",
  };
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]",
        toneClass[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}

export type TooltipProps = {
  /** The interactive element the tooltip describes. */
  children: ReactNode;
  /** Plain-text tooltip content (announced to assistive tech). */
  label: string;
  className?: string;
};

/**
 * Lightweight, accessible tooltip. The trigger is wrapped in a focusable group
 * so the tip shows on both hover and keyboard focus (Req 4.3, 5.5), respects
 * `prefers-reduced-motion`, and exposes its content via `aria-describedby`.
 */
export function Tooltip({ children, label, className = "" }: TooltipProps) {
  const tipId = useId();
  return (
    <span className={["group relative inline-flex", className].join(" ")}>
      <span aria-describedby={tipId} className="inline-flex">
        {children}
      </span>
      <span
        role="tooltip"
        id={tipId}
        className={
          "pointer-events-none absolute left-1/2 top-full z-50 mt-1.5 -translate-x-1/2 " +
          "whitespace-nowrap rounded-lg border border-[color:var(--shell-border)] " +
          "bg-[var(--surface-panel)] px-2 py-1 text-[11px] font-medium text-[var(--text-primary)] " +
          "opacity-0 shadow-lg transition-opacity duration-150 " +
          "group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none"
        }
      >
        {label}
      </span>
    </span>
  );
}

export type TabItem = {
  id: string;
  label: ReactNode;
  disabled?: boolean;
};

export type TabsProps = {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  /** Accessible name for the tablist (Req 5.2). */
  label: string;
  className?: string;
};

/**
 * Accessible, roving-focus tab strip (ARIA `tablist`/`tab`). Arrow keys move
 * between tabs, Home/End jump to the ends, and the active tab is the only one in
 * the tab order (Req 4.3, 5.1). Purely presentational — the caller owns panels.
 */
export function Tabs({
  items,
  activeId,
  onChange,
  label,
  className = "",
}: TabsProps) {
  const enabled = items.filter((item) => !item.disabled);

  const focusByOffset = (currentId: string, offset: number) => {
    if (!enabled.length) return;
    const index = enabled.findIndex((item) => item.id === currentId);
    const nextIndex = (index + offset + enabled.length) % enabled.length;
    onChange(enabled[nextIndex].id);
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      className={[
        "inline-flex items-center gap-1 rounded-xl bg-[var(--surface-muted)] p-1",
        className,
      ].join(" ")}
    >
      {items.map((item) => {
        const isActive = item.id === activeId;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${item.id}`}
            tabIndex={isActive ? 0 : -1}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight" || event.key === "ArrowDown") {
                event.preventDefault();
                focusByOffset(item.id, 1);
              } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
                event.preventDefault();
                focusByOffset(item.id, -1);
              } else if (event.key === "Home") {
                event.preventDefault();
                if (enabled[0]) onChange(enabled[0].id);
              } else if (event.key === "End") {
                event.preventDefault();
                if (enabled.length) onChange(enabled[enabled.length - 1].id);
              }
            }}
            className={[
              "min-h-[34px] rounded-lg px-3 text-[12px] font-semibold transition",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]",
              "disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none",
              isActive
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
            ].join(" ")}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export type DrawerProps = {
  open: boolean;
  onClose: () => void;
  /** Accessible name for the dialog (Req 5.2). */
  label: string;
  children: ReactNode;
  /** Which edge the panel slides in from. */
  side?: "left" | "right";
  className?: string;
};

/**
 * Accessible slide-over drawer (modal `dialog`). Closes on Escape and overlay
 * click, moves focus into the panel on open, and restores focus to the prior
 * element on close (Req 5.4). Respects `prefers-reduced-motion`.
 */
export function Drawer({
  open,
  onClose,
  label,
  children,
  side = "right",
  className = "",
}: DrawerProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Keep Tab focus inside the panel while the drawer is open (Req 5.4).
  useFocusTrap(open && mounted, panelRef);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = (document.activeElement as HTMLElement) ?? null;
    const timer = window.setTimeout(() => panelRef.current?.focus(), 10);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKeyDown);
      restoreFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open || !mounted) return null;

  return (
    <div
      className={[
        "fixed inset-0 z-[65] flex",
        side === "right" ? "justify-end" : "justify-start",
      ].join(" ")}
    >
      <button
        type="button"
        aria-label={`${label} — overlay`}
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 bg-[rgba(16,20,25,0.72)]"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={[
          "relative flex h-full w-[min(92vw,24rem)] flex-col bg-[var(--surface-panel)] p-4 outline-none",
          side === "right"
            ? "border-l border-[color:var(--shell-border)]"
            : "border-r border-[color:var(--shell-border)]",
          className,
        ].join(" ")}
      >
        {children}
      </div>
    </div>
  );
}
