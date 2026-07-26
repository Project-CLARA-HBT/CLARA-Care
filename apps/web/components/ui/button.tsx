"use client";

import { forwardRef } from "react";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] font-semibold leading-tight transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-ring disabled:cursor-not-allowed disabled:opacity-55";

const VARIANTS: Record<Variant, string> = {
  primary:
    "border border-[color:var(--brand-700)] bg-[var(--brand-600)] text-white shadow-[var(--shadow-sm)] hover:bg-[var(--brand-700)] active:translate-y-px",
  secondary:
    "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-[var(--shadow-sm)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)]",
  ghost:
    "border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
  danger:
    "border border-[color:var(--danger-500)] bg-[var(--danger-500)] text-white shadow-[var(--shadow-sm)] hover:brightness-95 active:translate-y-px",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-9 px-3 py-1.5 text-[0.8125rem]",
  md: "min-h-[var(--touch-target-min)] px-4 py-2.5 text-sm",
  lg: "min-h-12 px-5 py-3 text-[0.9375rem]",
};

function classesFor(variant: Variant, size: Size, block: boolean, className: string) {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${block ? "w-full" : ""} ${className}`;
}

function Glyph({ glyph, spin }: { glyph: string; spin: boolean }) {
  return (
    <span
      className={`material-symbols-outlined text-[1.15em] ${spin ? "animate-spin" : ""}`}
      aria-hidden="true"
    >
      {glyph}
    </span>
  );
}

type CommonProps = {
  variant?: Variant;
  size?: Size;
  block?: boolean;
  icon?: string;
  iconTrailing?: boolean;
  children?: ReactNode;
  className?: string;
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  CommonProps & {
    as?: "button";
    loading?: boolean;
    loadingLabel?: string;
  };

export type LinkButtonProps = CommonProps & {
  as: "link";
  href: string;
};

const Button = forwardRef<HTMLButtonElement, ButtonProps | LinkButtonProps>(
  function Button(props, ref) {
    const {
      variant = "primary",
      size = "md",
      block = false,
      icon,
      iconTrailing = false,
      className = "",
      children,
    } = props;

    if (props.as === "link") {
      return (
        <Link href={props.href} className={classesFor(variant, size, block, className)}>
          {icon && !iconTrailing ? <Glyph glyph={icon} spin={false} /> : null}
          {children ? <span className="truncate">{children}</span> : null}
          {icon && iconTrailing ? <Glyph glyph={icon} spin={false} /> : null}
        </Link>
      );
    }

    const {
      as: _as,
      variant: _variant,
      size: _size,
      block: _block,
      icon: _icon,
      iconTrailing: _iconTrailing,
      className: _className,
      children: _children,
      loading = false,
      loadingLabel,
      disabled,
      type = "button",
      ...rest
    } = props;
    void _as;
    void _variant;
    void _size;
    void _block;
    void _icon;
    void _iconTrailing;
    void _className;
    void _children;

    const label = loading && loadingLabel ? loadingLabel : children;
    const glyph = loading ? "progress_activity" : icon;

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={classesFor(variant, size, block, className)}
        {...rest}
      >
        {glyph && !iconTrailing ? <Glyph glyph={glyph} spin={loading} /> : null}
        {label ? <span className="truncate">{label}</span> : null}
        {glyph && iconTrailing ? <Glyph glyph={glyph} spin={loading} /> : null}
      </button>
    );
  },
);

export { Button };
export default Button;
