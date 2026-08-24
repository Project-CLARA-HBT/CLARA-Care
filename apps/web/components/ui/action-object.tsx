"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

export type ActionObjectTone = "brand" | "mint" | "iris" | "warning";

export interface ActionObjectProps {
  title: ReactNode;
  description: ReactNode;
  badge?: ReactNode;
  icon?: IconName | string | ReactNode;
  /** List of highlight bullets (e.g. 3 capability strings) */
  highlights?: Array<string | { text?: string; vi?: string; en?: string }>;
  href?: string;
  onClick?: (e: React.MouseEvent<HTMLElement>) => void;
  tone?: ActionObjectTone;
  actionLabel?: ReactNode;
  disabled?: boolean;
  className?: string;
  children?: ReactNode;
  id?: string;
  target?: string;
  rel?: string;
  "aria-label"?: string;
}

interface ToneStyleConfig {
  iconContainer: string;
  badge: string;
  borderHover: string;
  actionText: string;
  dot: string;
  arrowHover: string;
}

const TONE_STYLES: Record<ActionObjectTone, ToneStyleConfig> = {
  brand: {
    iconContainer:
      "bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:bg-[var(--surface-brand-soft,rgba(164,201,255,0.12))]",
    badge:
      "border-[color:var(--brand-500,#a4c9ff)]/30 bg-[var(--surface-brand-soft,rgba(164,201,255,0.12))] text-[var(--text-brand,#a4c9ff)]",
    borderHover: "hover:border-[color:var(--text-brand,#a4c9ff)]",
    actionText: "text-[var(--text-brand,#a4c9ff)]",
    dot: "bg-[var(--text-brand,#a4c9ff)]",
    arrowHover:
      "group-hover:bg-[var(--brand-600)] group-hover:text-[var(--button-primary-text,#cdd7ff)]",
  },
  mint: {
    iconContainer:
      "bg-[var(--surface-muted)] text-[color:var(--clara-mint-400,#3AD2B6)] group-hover:bg-[color:var(--clara-mint-500,#14A88D)]/15",
    badge:
      "border-[color:var(--clara-mint-500,#14A88D)]/30 bg-[color:var(--clara-mint-500,#14A88D)]/12 text-[color:var(--clara-mint-400,#3AD2B6)]",
    borderHover: "hover:border-[color:var(--clara-mint-400,#3AD2B6)]",
    actionText: "text-[color:var(--clara-mint-400,#3AD2B6)]",
    dot: "bg-[color:var(--clara-mint-400,#3AD2B6)]",
    arrowHover:
      "group-hover:bg-[color:var(--clara-mint-600,#0F8A75)] group-hover:text-white",
  },
  iris: {
    iconContainer:
      "bg-[var(--surface-muted)] text-[color:var(--clara-iris-400,#A78BFA)] group-hover:bg-[color:var(--clara-iris-500,#8B7CF6)]/15",
    badge:
      "border-[color:var(--clara-iris-500,#8B7CF6)]/30 bg-[color:var(--clara-iris-500,#8B7CF6)]/12 text-[color:var(--clara-iris-400,#A78BFA)]",
    borderHover: "hover:border-[color:var(--clara-iris-400,#A78BFA)]",
    actionText: "text-[color:var(--clara-iris-400,#A78BFA)]",
    dot: "bg-[color:var(--clara-iris-400,#A78BFA)]",
    arrowHover:
      "group-hover:bg-[color:var(--clara-iris-600,#7566E8)] group-hover:text-white",
  },
  warning: {
    iconContainer:
      "bg-[var(--surface-muted)] text-[var(--status-warn-text,#fabd34)] group-hover:bg-[var(--status-warn-bg,rgba(250,189,52,0.12))]",
    badge:
      "border-[color:var(--status-warn-border,rgba(250,189,52,0.30))] bg-[var(--status-warn-bg,rgba(250,189,52,0.12))] text-[var(--status-warn-text,#fabd34)]",
    borderHover: "hover:border-[color:var(--status-warn-text,#fabd34)]",
    actionText: "text-[var(--status-warn-text,#fabd34)]",
    dot: "bg-[var(--status-warn-text,#fabd34)]",
    arrowHover:
      "group-hover:bg-[color:var(--warn-500,#fabd34)] group-hover:text-[#101419]",
  },
};

function renderActionObjectIcon(icon: IconName | string | ReactNode) {
  if (!icon) return null;
  if (typeof icon === "string") {
    return <Icon name={resolveIconName(icon)} size={24} aria-hidden="true" />;
  }
  return <span className="inline-flex shrink-0 items-center">{icon}</span>;
}

export function ActionObject({
  title,
  description,
  badge,
  icon,
  highlights,
  href,
  onClick,
  tone = "brand",
  actionLabel,
  disabled = false,
  className = "",
  children,
  id,
  target,
  rel,
  "aria-label": ariaLabel,
}: ActionObjectProps) {
  const toneStyle = TONE_STYLES[tone] ?? TONE_STYLES.brand;

  const cardContent = (
    <>
      <div>
        {/* Top Icon & Badge Header */}
        <div className="flex items-center justify-between gap-3">
          {icon ? (
            <span
              className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl transition-all duration-200 group-hover:scale-105 ${toneStyle.iconContainer}`}
            >
              {renderActionObjectIcon(icon)}
            </span>
          ) : (
            <span />
          )}

          {badge ? (
            typeof badge === "string" ? (
              <span
                className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${toneStyle.badge}`}
              >
                {badge}
              </span>
            ) : (
              badge
            )
          ) : null}
        </div>

        {/* Title */}
        <h3 className="mt-4 text-lg font-bold tracking-tight text-[var(--text-primary)] transition-colors group-hover:text-[var(--text-primary)]">
          {title}
        </h3>

        {/* Description */}
        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
          {description}
        </p>

        {/* Highlights List */}
        {highlights && highlights.length > 0 && (
          <div className="mt-4 space-y-1.5 border-t border-[color:var(--shell-border)]/60 pt-3">
            {highlights.map((item, index) => {
              const text =
                typeof item === "string"
                  ? item
                  : item.text ?? item.vi ?? item.en ?? "";
              return (
                <div
                  key={index}
                  className="flex items-center gap-2 text-xs text-[var(--text-muted)]"
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full opacity-80 ${toneStyle.dot}`}
                    aria-hidden="true"
                  />
                  <span className="truncate">{text}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Children Slot */}
        {children ? <div className="mt-3">{children}</div> : null}
      </div>

      {/* Trailing Action Row */}
      <div className="mt-5 flex items-center justify-between pt-2">
        <span className={`text-xs font-bold transition-colors ${toneStyle.actionText}`}>
          {actionLabel ?? (tone === "warning" ? "Xem cảnh báo" : "Mở công cụ")}
        </span>
        <span
          className={`grid h-7 w-7 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-secondary)] transition-all duration-200 group-hover:translate-x-1 ${toneStyle.arrowHover}`}
          aria-hidden="true"
        >
          <Icon name="arrow-right" size={14} />
        </span>
      </div>
    </>
  );

  const containerClasses = `group relative flex flex-col justify-between overflow-hidden rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus-ring-color,#0B6FD8)] ${
    disabled
      ? "opacity-60 cursor-not-allowed"
      : `hover:-translate-y-1 hover:shadow-lg ${toneStyle.borderHover}`
  } ${className}`;

  if (href && !disabled) {
    return (
      <Link
        id={id}
        href={href}
        onClick={onClick}
        target={target}
        rel={rel}
        aria-label={ariaLabel}
        data-tone={tone}
        className={containerClasses}
      >
        {cardContent}
      </Link>
    );
  }

  if (onClick && !disabled) {
    return (
      <button
        id={id}
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        data-tone={tone}
        className={`w-full ${containerClasses}`}
      >
        {cardContent}
      </button>
    );
  }

  return (
    <article
      id={id}
      aria-label={ariaLabel}
      data-tone={tone}
      className={containerClasses}
    >
      {cardContent}
    </article>
  );
}

export default ActionObject;
