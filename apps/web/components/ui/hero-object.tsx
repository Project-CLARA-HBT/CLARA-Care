"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

export type HeroObjectVariant = "primary" | "journey" | "clinical" | "alert";

export type HeroActionTone =
  | "primary"
  | "secondary"
  | "danger"
  | "ghost"
  | "brand"
  | "mint"
  | "iris"
  | "warning";

export interface HeroAction {
  label: ReactNode;
  onClick?: (e: React.MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => void;
  href?: string;
  icon?: IconName | string | ReactNode;
  tone?: HeroActionTone;
  disabled?: boolean;
  className?: string;
  target?: string;
  rel?: string;
  "aria-label"?: string;
}

export interface HeroObjectProps {
  title: ReactNode;
  description?: ReactNode;
  /** Eyebrow / context category tag (alias: badge) */
  contextTag?: ReactNode;
  badge?: ReactNode;
  /** Primary call-to-action */
  primaryAction?: HeroAction;
  /** Secondary call-to-action */
  secondaryAction?: HeroAction | ReactNode;
  /** Supporting metadata (e.g. timestamp, patient id, details) */
  supportingMeta?: ReactNode;
  /** Semantic variant driving accent styling */
  variant?: HeroObjectVariant;
  /** Status badge / chip */
  status?: ReactNode;
  /** Optional hero icon or illustration */
  icon?: IconName | string | ReactNode;
  /** Optional journey / task progress indicator (0-100 or structured object) */
  progress?: number | { value: number; max?: number; label?: string };
  /** Optional custom content rendered inside the hero card */
  children?: ReactNode;
  className?: string;
  id?: string;
}

const VARIANT_CONTAINER_STYLES: Record<HeroObjectVariant, string> = {
  primary:
    "border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
  journey:
    "border-t-[color:var(--brand-500,#a4c9ff)] border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
  clinical:
    "border-t-[color:var(--clara-mint-500,#14A88D)] border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
  alert:
    "border-t-[color:var(--warn-500,#fabd34)] border-[color:var(--status-warn-border,rgba(250,189,52,0.30))] bg-[var(--surface-panel)]",
};

const VARIANT_TAG_STYLES: Record<HeroObjectVariant, string> = {
  primary:
    "border-[color:var(--brand-500,#a4c9ff)]/30 bg-[var(--surface-brand-soft,rgba(164,201,255,0.12))] text-[var(--text-brand,#a4c9ff)]",
  journey:
    "border-[color:var(--brand-500,#a4c9ff)]/30 bg-[var(--surface-brand-soft,rgba(164,201,255,0.12))] text-[var(--text-brand,#a4c9ff)]",
  clinical:
    "border-[color:var(--clara-mint-500,#14A88D)]/30 bg-[color:var(--clara-mint-500,#14A88D)]/12 text-[color:var(--clara-mint-400,#3AD2B6)]",
  alert:
    "border-[color:var(--status-warn-border,rgba(250,189,52,0.30))] bg-[var(--status-warn-bg,rgba(250,189,52,0.12))] text-[var(--status-warn-text,#fabd34)]",
};

const ACTION_TONE_STYLES: Record<HeroActionTone, string> = {
  primary:
    "border border-[color:var(--brand-700)] bg-[var(--brand-600)] text-[var(--button-primary-text)] hover:bg-[var(--brand-700)] shadow-sm",
  brand:
    "border border-[color:var(--brand-700)] bg-[var(--brand-600)] text-[var(--button-primary-text)] hover:bg-[var(--brand-700)] shadow-sm",
  secondary:
    "border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)]",
  ghost:
    "border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
  danger:
    "border border-[color:var(--danger-500)] bg-[var(--danger-500)] text-[var(--on-error-container)] hover:brightness-95",
  mint:
    "border border-[color:var(--clara-mint-700,#0F6F61)] bg-[color:var(--clara-mint-600,#0F8A75)] text-white hover:bg-[color:var(--clara-mint-700,#0F6F61)] shadow-sm",
  iris:
    "border border-[color:var(--clara-iris-700,#6354C9)] bg-[color:var(--clara-iris-600,#7566E8)] text-white hover:bg-[color:var(--clara-iris-700,#6354C9)] shadow-sm",
  warning:
    "border border-[color:var(--status-warn-border,rgba(250,189,52,0.4))] bg-[color:var(--warn-500,#fabd34)] text-[#101419] font-bold hover:brightness-95 shadow-sm",
};

function renderActionGlyph(icon: IconName | string | ReactNode) {
  if (!icon) return null;
  if (typeof icon === "string") {
    return <Icon name={resolveIconName(icon)} size={16} aria-hidden="true" />;
  }
  return <span className="inline-flex shrink-0 items-center">{icon}</span>;
}

function ActionButton({
  action,
  defaultTone = "primary",
}: {
  action: HeroAction;
  defaultTone?: HeroActionTone;
}) {
  const tone = action.tone ?? defaultTone;
  const toneClass = ACTION_TONE_STYLES[tone] ?? ACTION_TONE_STYLES.primary;
  const baseClasses =
    "inline-flex min-h-[var(--touch-target-min,44px)] items-center justify-center gap-2 rounded-[var(--radius-md,8px)] px-4 py-2.5 text-sm font-semibold leading-tight transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus-ring-color,#0B6FD8)] disabled:cursor-not-allowed disabled:opacity-50";

  if (action.href && !action.disabled) {
    return (
      <Link
        href={action.href}
        onClick={action.onClick}
        target={action.target}
        rel={action.rel}
        aria-label={action["aria-label"]}
        className={`${baseClasses} ${toneClass} ${action.className ?? ""}`}
      >
        {renderActionGlyph(action.icon)}
        <span>{action.label}</span>
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={action.onClick}
      disabled={action.disabled}
      aria-label={action["aria-label"]}
      className={`${baseClasses} ${toneClass} ${action.className ?? ""}`}
    >
      {renderActionGlyph(action.icon)}
      <span>{action.label}</span>
    </button>
  );
}

function isHeroActionObject(item: unknown): item is HeroAction {
  return typeof item === "object" && item !== null && "label" in item;
}

export function HeroObject({
  title,
  description,
  contextTag,
  badge,
  primaryAction,
  secondaryAction,
  supportingMeta,
  variant = "primary",
  status,
  icon,
  progress,
  children,
  className = "",
  id,
}: HeroObjectProps) {
  const activeEyebrow = contextTag ?? badge;
  const containerVariantStyle =
    VARIANT_CONTAINER_STYLES[variant] ?? VARIANT_CONTAINER_STYLES.primary;
  const tagVariantStyle =
    VARIANT_TAG_STYLES[variant] ?? VARIANT_TAG_STYLES.primary;

  // Progress computation
  let progressValue: number | null = null;
  let progressMax = 100;
  let progressLabel: string | undefined;
  if (typeof progress === "number") {
    progressValue = progress;
  } else if (progress && typeof progress === "object") {
    progressValue = progress.value;
    progressMax = progress.max ?? 100;
    progressLabel = progress.label;
  }

  return (
    <section
      id={id}
      data-variant={variant}
      className={`relative overflow-hidden rounded-[var(--radius-xl)] border p-5 sm:p-7 shadow-sm transition-colors ${containerVariantStyle} ${className}`}
    >
      {/* Top Header Row: Eyebrow Tag, Status Chip, and Supporting Meta */}
      {(activeEyebrow || status || supportingMeta) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2">
            {activeEyebrow ? (
              typeof activeEyebrow === "string" ? (
                <span
                  className={`inline-flex items-center rounded-[var(--radius-pill)] border px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider ${tagVariantStyle}`}
                >
                  {activeEyebrow}
                </span>
              ) : (
                activeEyebrow
              )
            ) : null}

            {status ? (
              typeof status === "string" ? (
                <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                  {status}
                </span>
              ) : (
                status
              )
            ) : null}
          </div>

          {supportingMeta ? (
            <div className="text-xs text-[var(--text-muted)]">
              {supportingMeta}
            </div>
          ) : null}
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3.5">
            {icon ? (
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-[var(--surface-muted)] text-[var(--text-brand)]">
                {typeof icon === "string" ? (
                  <Icon name={resolveIconName(icon)} size={24} aria-hidden="true" />
                ) : (
                  icon
                )}
              </span>
            ) : null}

            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-2xl lg:text-[1.75rem]">
                {title}
              </h2>

              {description ? (
                <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
                  {description}
                </p>
              ) : null}
            </div>
          </div>

          {/* Optional Journey Progress Bar */}
          {progressValue !== null && (
            <div
              className="mt-4 max-w-md space-y-1.5"
              role="progressbar"
              aria-valuenow={progressValue}
              aria-valuemin={0}
              aria-valuemax={progressMax}
              aria-label={progressLabel ?? "Tiến độ"}
            >
              {progressLabel ? (
                <div className="flex items-center justify-between text-xs text-[var(--text-secondary)]">
                  <span>{progressLabel}</span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {Math.round((progressValue / progressMax) * 100)}%
                  </span>
                </div>
              ) : null}
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
                <div
                  className="h-full rounded-full bg-[var(--brand-600)] transition-all duration-300"
                  style={{
                    width: `${Math.min(100, Math.max(0, (progressValue / progressMax) * 100))}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Children Slot */}
          {children ? <div className="mt-4">{children}</div> : null}
        </div>

        {/* Action Button Strip */}
        {(primaryAction || secondaryAction) && (
          <div className="mt-2 flex flex-wrap items-center gap-2.5 sm:shrink-0 lg:mt-0">
            {primaryAction ? (
              <ActionButton
                action={primaryAction}
                defaultTone={
                  variant === "clinical"
                    ? "mint"
                    : variant === "alert"
                    ? "warning"
                    : "primary"
                }
              />
            ) : null}

            {secondaryAction ? (
              isHeroActionObject(secondaryAction) ? (
                <ActionButton action={secondaryAction} defaultTone="secondary" />
              ) : (
                secondaryAction
              )
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}

export default HeroObject;
