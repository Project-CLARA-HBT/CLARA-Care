"use client";

import React, { forwardRef } from "react";

export type ChromeSurfaceVariant =
  | "navbar"
  | "header"
  | "sheet"
  | "menu"
  | "popover"
  | "banner"
  | "opaque";

export type ChromeSurfaceBlur = "subtle" | "medium" | "high" | "none";
export type ChromeSurfaceBorder = "subtle" | "default" | "strong" | "none";
export type ChromeSurfaceElevation = "flat" | "raised" | "floating" | "overlay";

export interface ChromeSurfaceBaseProps {
  /**
   * Surface preset variant.
   * Note: 'opaque' is strictly opaque (`var(--surface-panel)`) and NEVER blurred.
   */
  variant?: ChromeSurfaceVariant;
  /**
   * Optional material alias for compatibility.
   */
  material?: string;
  /**
   * Backdrop blur level. Forced to 'none' if variant is 'opaque'.
   */
  blur?: ChromeSurfaceBlur;
  /**
   * Border weight / style.
   */
  border?: ChromeSurfaceBorder;
  /**
   * Elevation shadow level.
   */
  elevation?: ChromeSurfaceElevation;
  /**
   * Content inside the surface.
   */
  children?: React.ReactNode;
  /**
   * Additional CSS classes.
   */
  className?: string;
}

export type ChromeSurfaceProps<E extends React.ElementType = "div"> =
  ChromeSurfaceBaseProps & {
    as?: E;
  } & Omit<React.ComponentPropsWithRef<E>, keyof ChromeSurfaceBaseProps | "as">;

export const VARIANT_DEFAULTS: Record<
  ChromeSurfaceVariant,
  {
    blur: ChromeSurfaceBlur;
    border: ChromeSurfaceBorder;
    elevation: ChromeSurfaceElevation;
  }
> = {
  navbar: { blur: "high", border: "subtle", elevation: "floating" },
  header: { blur: "medium", border: "subtle", elevation: "raised" },
  sheet: { blur: "medium", border: "subtle", elevation: "overlay" },
  menu: { blur: "medium", border: "subtle", elevation: "overlay" },
  popover: { blur: "medium", border: "subtle", elevation: "floating" },
  banner: { blur: "subtle", border: "subtle", elevation: "flat" },
  opaque: { blur: "none", border: "default", elevation: "flat" },
};

const VARIANT_BG_CLASSES: Record<ChromeSurfaceVariant, string> = {
  navbar: "bg-[var(--glass-bg-navbar,rgba(16,20,25,0.80))]",
  header: "bg-[var(--glass-bg-header,var(--surface-header,rgba(16,20,25,0.88)))]",
  sheet: "bg-[var(--glass-bg-sheet,rgba(29,32,37,0.92))]",
  menu: "bg-[var(--glass-bg-menu,rgba(29,32,37,0.90))]",
  popover: "bg-[var(--glass-bg-menu,rgba(29,32,37,0.90))]",
  banner: "bg-[var(--glass-bg-header,rgba(16,20,25,0.88))]",
  opaque: "bg-[var(--surface-panel,#1d2025)]",
};

const BLUR_CLASSES: Record<ChromeSurfaceBlur, string> = {
  none: "backdrop-blur-none",
  subtle: "backdrop-blur-sm",
  medium: "backdrop-blur-md",
  high: "backdrop-blur-xl",
};

const BORDER_CLASSES: Record<ChromeSurfaceBorder, string> = {
  none: "border-0",
  subtle: "border border-[color:var(--glass-border-subtle,rgba(255,255,255,0.08))]",
  default: "border border-[color:var(--shell-border,#414751)]",
  strong: "border border-[color:var(--shell-border-strong,#8b919d)]",
};

const ELEVATION_CLASSES: Record<ChromeSurfaceElevation, string> = {
  flat: "shadow-none",
  raised: "shadow-sm",
  floating: "shadow-[var(--shadow-float,0_8px_24px_-12px_rgba(0,0,0,0.28))]",
  overlay: "shadow-[var(--shadow-overlay,0_16px_36px_-16px_rgba(0,0,0,0.42))]",
};

type ChromeSurfaceComponent = <E extends React.ElementType = "div">(
  props: ChromeSurfaceProps<E> & { ref?: React.ComponentPropsWithRef<E>["ref"] }
) => React.ReactElement | null;

/**
 * ChromeSurface: Tokenized chrome surface primitive for navigation, headers, menus, sheets, and popovers.
 * Supports CSS fallback for `prefers-reduced-transparency: reduce` or unsupported `backdrop-filter`.
 *
 * Invariant: Variant 'opaque' enforces `blur="none"` and `var(--surface-panel)` background
 * for medical records, clinical notes, tables, charts, and forms.
 */
export const ChromeSurface: ChromeSurfaceComponent = forwardRef(
  <E extends React.ElementType = "div">(
    {
      variant,
      material,
      blur,
      border,
      elevation,
      className = "",
      as,
      children,
      ...rest
    }: ChromeSurfaceProps<E>,
    ref: React.ComponentPropsWithRef<E>["ref"]
  ) => {
    // Resolve variant with backwards compatibility for material names
    const resolvedVariant: ChromeSurfaceVariant =
      variant ??
      (material === "navigation"
        ? "navbar"
        : (material as ChromeSurfaceVariant | undefined)) ??
      "header";

    const defaults =
      VARIANT_DEFAULTS[resolvedVariant] || VARIANT_DEFAULTS.header;

    // Opaque Surface Contract: variant='opaque' MUST NEVER be blurred
    const isOpaque = resolvedVariant === "opaque";
    const resolvedBlur: ChromeSurfaceBlur = isOpaque
      ? "none"
      : (blur ?? defaults.blur);
    const resolvedBorder: ChromeSurfaceBorder = border ?? defaults.border;
    const resolvedElevation: ChromeSurfaceElevation =
      elevation ?? defaults.elevation;

    const Component = as || "div";

    const computedClasses = [
      "chrome-surface",
      VARIANT_BG_CLASSES[resolvedVariant],
      BLUR_CLASSES[resolvedBlur],
      BORDER_CLASSES[resolvedBorder],
      ELEVATION_CLASSES[resolvedElevation],
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <Component
        ref={ref}
        className={computedClasses}
        data-chrome-surface="true"
        data-variant={resolvedVariant}
        data-blur={resolvedBlur}
        data-border={resolvedBorder}
        data-elevation={resolvedElevation}
        {...rest}
      >
        {children}
      </Component>
    );
  }
) as unknown as ChromeSurfaceComponent;

/**
 * Opaque Surface primitive for medical records, tables, charts, forms, and clinical notes.
 * Enforces opaque background (`var(--surface-panel)`) and is NEVER blurred.
 */
export interface SurfaceProps<E extends React.ElementType = "div">
  extends Omit<ChromeSurfaceProps<E>, "variant" | "blur"> {
  interactive?: boolean;
}

export const Surface = forwardRef(
  <E extends React.ElementType = "div">(
    { className = "", interactive = false, ...rest }: SurfaceProps<E>,
    ref: React.ComponentPropsWithRef<E>["ref"]
  ) => {
    return (
      <ChromeSurface
        ref={ref}
        variant="opaque"
        blur="none"
        border={rest.border ?? "default"}
        elevation={rest.elevation ?? "flat"}
        className={`${
          interactive
            ? "transition-colors hover:border-[color:var(--shell-border-strong)]/60 hover:bg-[var(--surface-muted)]"
            : ""
        } ${className}`.trim()}
        {...rest}
      />
    );
  }
) as unknown as <E extends React.ElementType = "div">(
  props: SurfaceProps<E> & { ref?: React.ComponentPropsWithRef<E>["ref"] }
) => React.ReactElement | null;

export default ChromeSurface;
