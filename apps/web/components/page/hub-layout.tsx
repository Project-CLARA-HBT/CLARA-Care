"use client";

import React, {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { PageFrame, type PageCanvasBg, type PageGutter, type PageMaxWidth } from "./page-frame";
import { PageHeader, type BreadcrumbItem, type PageHeaderBackAction } from "./page-header";

export interface HubQuickAction {
  id?: string;
  title: string;
  description?: string;
  icon?: IconName | ReactNode;
  href?: string;
  onClick?: () => void;
  badge?: ReactNode;
  tone?: "brand" | "neutral" | "ok" | "warn" | "danger";
  disabled?: boolean;
}

export interface HubSection {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  icon?: IconName | ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  status?: ReactNode;
  href?: string;
}

export interface HubLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Custom header node or uses PageHeader props below */
  header?: ReactNode;
  eyebrow?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  breadcrumbs?: BreadcrumbItem[] | ReactNode;
  headerActions?: ReactNode;
  backAction?: PageHeaderBackAction;
  /** Primary hero banner / overview card */
  overviewBanner?: ReactNode;
  /** Quick action tiles list or custom grid */
  quickActions?: HubQuickAction[] | ReactNode;
  /** Domain cards / section containers */
  domainSections?: HubSection[];
  /** Optional side rail */
  aside?: ReactNode;
  /** Additional body children */
  children?: ReactNode;
  /** Number of grid columns for quick action tiles */
  actionColumns?: 2 | 3 | 4;
  /** Max width constraint */
  maxWidth?: PageMaxWidth;
  /** Gutter padding */
  gutter?: PageGutter;
  /** Canvas background */
  canvasBg?: PageCanvasBg;
}

const TONE_ICON_BG: Record<string, string> = {
  brand: "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
  neutral: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
  ok: "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
  warn: "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
  danger: "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
};

/**
 * Hub archetype layout primitive.
 * Consolidates overview banner, quick action launchpad tiles, and domain sections.
 */
export const HubLayout = forwardRef<HTMLElement, HubLayoutProps>(
  (
    {
      header,
      eyebrow,
      title,
      subtitle,
      description,
      badges,
      breadcrumbs,
      headerActions,
      backAction,
      overviewBanner,
      quickActions,
      domainSections,
      aside,
      children,
      actionColumns = 3,
      maxWidth = "default",
      gutter = "default",
      canvasBg = "canvas",
      className = "",
      ...rest
    },
    ref
  ) => {
    const renderedHeader =
      header ??
      (title ? (
        <PageHeader
          eyebrow={eyebrow}
          title={title}
          subtitle={subtitle}
          description={description}
          badges={badges}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
          backAction={backAction}
        />
      ) : null);

    const renderQuickActionTile = (action: HubQuickAction, index: number) => {
      const toneClass =
        TONE_ICON_BG[action.tone ?? "brand"] ?? TONE_ICON_BG.brand;
      const content = (
        <div className="flex h-full flex-col justify-between p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-lg)] ${toneClass}`}
            >
              {typeof action.icon === "string" ? (
                <Icon name={action.icon as IconName} size="1.25rem" />
              ) : (
                action.icon ?? <Icon name="arrow-right" size="1.25rem" />
              )}
            </div>
            {action.badge ? <div>{action.badge}</div> : null}
          </div>
          <div className="mt-4">
            <p className="font-semibold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
              {action.title}
            </p>
            {action.description ? (
              <p className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)] line-clamp-2">
                {action.description}
              </p>
            ) : null}
          </div>
        </div>
      );

      const tileClass = `group block h-full rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-left transition-all hover:border-[color:var(--shell-border-strong)]/70 hover:bg-[var(--surface-muted)] focus-ring ${
        action.disabled ? "pointer-events-none opacity-50" : ""
      }`;

      if (action.href) {
        return (
          <Link
            key={action.id ?? action.title + index}
            href={action.href}
            className={tileClass}
          >
            {content}
          </Link>
        );
      }

      return (
        <button
          key={action.id ?? action.title + index}
          type="button"
          onClick={action.onClick}
          disabled={action.disabled}
          className={tileClass}
        >
          {content}
        </button>
      );
    };

    const renderQuickActions = () => {
      if (!quickActions) return null;

      if (React.isValidElement(quickActions)) {
        return <div className="mb-8">{quickActions}</div>;
      }

      if (Array.isArray(quickActions) && quickActions.length > 0) {
        const colClass =
          actionColumns === 2
            ? "grid-cols-1 sm:grid-cols-2"
            : actionColumns === 4
            ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
            : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";

        return (
          <section aria-label="Quick actions" className="mb-8">
            <div className={`grid gap-4 sm:gap-5 ${colClass}`}>
              {quickActions.map(renderQuickActionTile)}
            </div>
          </section>
        );
      }

      return null;
    };

    const renderDomainSections = () => {
      if (!domainSections || domainSections.length === 0) return null;

      return (
        <div className="space-y-6 sm:space-y-8">
          {domainSections.map((section) => (
            <SurfaceCard
              key={section.id}
              id={section.id}
              className="overflow-hidden p-5 sm:p-6"
            >
              <div className="flex flex-col gap-3 pb-4 border-b border-[color:var(--shell-border)]/60 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  {section.icon ? (
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
                      {typeof section.icon === "string" ? (
                        <Icon name={section.icon as IconName} size="1.125rem" />
                      ) : (
                        section.icon
                      )}
                    </div>
                  ) : null}
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                        {section.title}
                      </h2>
                      {section.badge ? <div>{section.badge}</div> : null}
                    </div>
                    {section.description ? (
                      <p className="mt-0.5 text-xs sm:text-sm text-[var(--text-secondary)]">
                        {section.description}
                      </p>
                    ) : null}
                  </div>
                </div>

                {section.actions || section.status ? (
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    {section.status}
                    {section.actions}
                  </div>
                ) : null}
              </div>

              <div className="pt-4">{section.children}</div>
            </SurfaceCard>
          ))}
        </div>
      );
    };

    return (
      <PageFrame
        ref={ref}
        archetype="hub"
        header={renderedHeader}
        aside={aside}
        maxWidth={maxWidth}
        gutter={gutter}
        bg={canvasBg}
        className={className}
        {...rest}
      >
        <div className="space-y-6 sm:space-y-8">
          {overviewBanner ? (
            <div className="overview-banner">{overviewBanner}</div>
          ) : null}

          {renderQuickActions()}

          {renderDomainSections()}

          {children}
        </div>
      </PageFrame>
    );
  }
);

HubLayout.displayName = "HubLayout";

export default HubLayout;
