"use client";

import React, {
  forwardRef,
  type ElementType,
  type HTMLAttributes,
  type ReactNode,
} from "react";

export type PageMaxWidth =
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
  | "narrow"
  | "medium"
  | "wide"
  | "dense";

export type PageGutter = "none" | "compact" | "default" | "spacious";
export type PageCanvasBg =
  | "canvas"
  | "panel"
  | "subtle"
  | "sidebar"
  | "transparent"
  | "workbench";

export type PageSurface = "default" | "panel" | "card" | "flush" | "none";

export interface PageFrameProps extends HTMLAttributes<HTMLElement> {
  /** Underlying HTML container element, defaults to 'div' or 'main' */
  as?: ElementType;
  /** Top page header slot */
  header?: ReactNode;
  /** Main content */
  children?: ReactNode;
  /** Optional bottom footer slot */
  footer?: ReactNode;
  /** Optional side rail / secondary panel */
  aside?: ReactNode;
  /** Width boundary token (Spec v8 §5.5: prose, instrument, workbench, full-bleed) */
  maxWidth?: PageMaxWidth;
  /** Responsive gutter padding preset */
  gutter?: PageGutter;
  /** Background canvas surface token */
  bg?: PageCanvasBg;
  /** Opaque content surface type (e.g. 'panel' renders opaque var(--surface-panel) container) */
  surface?: PageSurface;
  /** Layout archetype identifier for styling and telemetry inspection */
  archetype?: string;
  /** Active workspace context (e.g. 'personal', 'clinical', 'research', 'admin') */
  workspace?: string;
  /** Additional class names for outer container */
  className?: string;
  /** Additional class names for inner constrained content wrapper */
  containerClassName?: string;
  /** Additional class names for content body area */
  contentClassName?: string;
  /** Additional class names for header slot wrapper */
  headerClassName?: string;
  /** Additional class names for footer slot wrapper */
  footerClassName?: string;
  /** Additional class names for aside slot wrapper */
  asideClassName?: string;
  /** Additional class names for opaque surface wrapper */
  surfaceClassName?: string;
}

const MAX_WIDTH_MAP: Record<PageMaxWidth, string> = {
  prose: "max-w-4xl",
  instrument: "max-w-5xl",
  workbench: "max-w-7xl",
  "full-bleed": "max-w-full",
  sm: "max-w-3xl",
  narrow: "max-w-3xl",
  md: "max-w-5xl",
  medium: "max-w-5xl",
  lg: "max-w-7xl",
  default: "max-w-7xl",
  wide: "max-w-7xl",
  xl: "max-w-[1400px]",
  "2xl": "max-w-[1536px]",
  "3xl": "max-w-[1680px]",
  "4xl": "max-w-[1680px]",
  dense: "max-w-[1680px]",
  full: "max-w-full",
};

const GUTTER_MAP: Record<PageGutter, string> = {
  none: "p-0",
  compact: "px-3 py-3 sm:px-4 sm:py-4",
  default: "px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8",
  spacious: "px-4 py-6 sm:px-8 sm:py-10 lg:px-12 lg:py-12",
};

const BG_MAP: Record<PageCanvasBg, string> = {
  canvas: "bg-[var(--bg-canvas)] text-[var(--text-primary)]",
  panel: "bg-[var(--surface-panel)] text-[var(--text-primary)]",
  subtle: "bg-[var(--surface-muted)] text-[var(--text-primary)]",
  sidebar: "bg-[var(--surface-sidebar)] text-[var(--text-primary)]",
  transparent: "bg-transparent text-[var(--text-primary)]",
  workbench: "bg-[var(--bg-canvas)] text-[var(--text-primary)]",
};

const SURFACE_MAP: Record<PageSurface, string> = {
  default: "",
  none: "",
  flush: "",
  panel:
    "rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm p-4 sm:p-6 lg:p-8",
  card:
    "rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-md p-4 sm:p-6",
};

/**
 * Standard page container primitive (Spec v8 §5.5).
 * Enforces max-width tokens (`prose`, `instrument`, `workbench`, `full-bleed`),
 * header slot, responsive gutters, background canvas tokens, and opaque content surfaces.
 */
export const PageFrame = forwardRef<HTMLElement, PageFrameProps>(
  (
    {
      as: Component = "div",
      header,
      children,
      footer,
      aside,
      maxWidth = "default",
      gutter = "default",
      bg = "canvas",
      surface = "default",
      archetype,
      workspace,
      className = "",
      containerClassName = "",
      contentClassName = "",
      headerClassName = "",
      footerClassName = "",
      asideClassName = "",
      surfaceClassName = "",
      ...rest
    },
    ref,
  ) => {
    const maxWClass = MAX_WIDTH_MAP[maxWidth] ?? MAX_WIDTH_MAP.default;
    const gutterClass = GUTTER_MAP[gutter] ?? GUTTER_MAP.default;
    const bgClass = BG_MAP[bg] ?? BG_MAP.canvas;
    const surfaceClass = SURFACE_MAP[surface] ?? "";

    const renderedChildren = surfaceClass ? (
      <div className={`${surfaceClass} ${surfaceClassName}`}>
        {children}
      </div>
    ) : (
      children
    );

    return (
      <Component
        ref={ref}
        data-archetype={archetype}
        data-workspace={workspace}
        data-surface={surface !== "default" ? surface : undefined}
        className={`relative min-h-full w-full ${bgClass} ${className}`}
        {...rest}
      >
        <div
          className={`mx-auto w-full ${maxWClass} ${gutterClass} ${containerClassName}`}
        >
          {header ? (
            <div className={`mb-6 sm:mb-8 ${headerClassName}`}>{header}</div>
          ) : null}

          {aside ? (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px] lg:gap-8 xl:grid-cols-[1fr_360px]">
              <div className={`min-w-0 ${contentClassName}`}>
                {renderedChildren}
              </div>
              <aside className={`min-w-0 ${asideClassName}`}>{aside}</aside>
            </div>
          ) : (
            <div className={contentClassName}>{renderedChildren}</div>
          )}

          {footer ? (
            <div
              className={`mt-8 sm:mt-12 border-t border-[color:var(--shell-border)] pt-6 ${footerClassName}`}
            >
              {footer}
            </div>
          ) : null}
        </div>
      </Component>
    );
  },
);

PageFrame.displayName = "PageFrame";

export default PageFrame;
