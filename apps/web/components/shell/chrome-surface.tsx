"use client";

import React, {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ComponentPropsWithRef,
  type ElementType,
  type ReactNode,
} from "react";

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
  children?: ReactNode;
  /**
   * Additional CSS classes.
   */
  className?: string;
}

export type ChromeSurfaceProps<E extends ElementType = "div"> =
  ChromeSurfaceBaseProps & {
    as?: E;
  } & Omit<ComponentPropsWithoutRef<E>, keyof ChromeSurfaceBaseProps | "as">;

export type SurfaceProps<E extends ElementType = "div"> = Omit<
  ChromeSurfaceBaseProps,
  "variant" | "blur"
> & {
  as?: E;
  interactive?: boolean;
} & Omit<
  ComponentPropsWithoutRef<E>,
  keyof ChromeSurfaceBaseProps | "as" | "interactive"
>;

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

type ChromeSurfaceComponent = <E extends ElementType = "div">(
  props: ChromeSurfaceProps<E> & { ref?: ComponentPropsWithRef<E>["ref"] }
) => React.ReactElement | null;

type SurfaceComponent = <E extends ElementType = "div">(
  props: SurfaceProps<E> & { ref?: ComponentPropsWithRef<E>["ref"] }
) => React.ReactElement | null;

/**
 * ChromeSurface: Tokenized chrome surface primitive for navigation, headers, menus, sheets, and popovers.
 * Supports CSS fallback for `prefers-reduced-transparency: reduce` or unsupported `backdrop-filter`.
 *
 * Invariant: Variant 'opaque' enforces `blur="none"` and `var(--surface-panel)` background
 * for medical records, clinical notes, tables, charts, and forms.
 */
export const ChromeSurface: ChromeSurfaceComponent = forwardRef(
  function ChromeSurface(
    props: ChromeSurfaceProps<ElementType>,
    ref: React.ForwardedRef<HTMLElement>
  ) {
    const {
      variant,
      material,
      blur,
      border,
      elevation,
      className = "",
      as: Component = "div",
      children,
      ...rest
    } = props;

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
(ChromeSurface as unknown as { displayName?: string }).displayName = "ChromeSurface";

/**
 * Opaque Surface primitive for medical records, tables, charts, forms, and clinical notes.
 * Enforces opaque background (`var(--surface-panel)`) and is NEVER blurred.
 */
export const Surface: SurfaceComponent = forwardRef(
  function Surface(
    props: SurfaceProps<ElementType>,
    ref: React.ForwardedRef<HTMLElement>
  ) {
    const {
      className = "",
      interactive = false,
      border = "default",
      elevation = "flat",
      children,
      as: Component = "div",
      ...rest
    } = props;

    return (
      <ChromeSurface
        ref={ref}
        as={Component}
        variant="opaque"
        blur="none"
        border={border}
        elevation={elevation}
        className={`${
          interactive
            ? "transition-colors hover:border-[color:var(--shell-border-strong)]/60 hover:bg-[var(--surface-muted)]"
            : ""
        } ${className}`.trim()}
        {...rest}
      >
        {children}
      </ChromeSurface>
    );
  }
) as unknown as SurfaceComponent;
(Surface as unknown as { displayName?: string }).displayName = "Surface";

export default ChromeSurface;
