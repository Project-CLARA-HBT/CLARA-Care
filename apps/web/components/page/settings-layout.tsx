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

export interface SettingsCategory {
  id: string;
  label: string;
  description?: string;
  icon?: IconName | ReactNode;
  badge?: ReactNode;
  disabled?: boolean;
  href?: string;
}

export interface SettingsLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Page header slot or uses PageHeader props below */
  header?: ReactNode;
  eyebrow?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  breadcrumbs?: BreadcrumbItem[] | ReactNode;
  headerActions?: ReactNode;
  backAction?: PageHeaderBackAction;
  /** Top profile / identity banner */
  profileBanner?: ReactNode;
  /** Alias for profileBanner */
  summaryCard?: ReactNode;
  /** Categorized navigation tabs list */
  categories?: SettingsCategory[];
  /** Active selected category identifier */
  activeCategoryId?: string;
  /** Callback on category selection */
  onCategoryChange?: (categoryId: string) => void;
  /** Contextual guidance / privacy guarantees sidebar */
  aside?: ReactNode;
  /** Alias for aside */
  helpRail?: ReactNode;
  /** Sticky or bottom unsaved changes / actions bar */
  saveBar?: ReactNode;
  /** Alias for saveBar */
  footerActions?: ReactNode;
  /** Max width */
  maxWidth?: PageMaxWidth;
  /** Gutter padding */
  gutter?: PageGutter;
  /** Canvas background */
  canvasBg?: PageCanvasBg;
  /** Main body content */
  children?: ReactNode;
}

/**
 * Settings archetype layout primitive.
 * Consolidates vertical category navigation, identity banner, settings sections, and contextual help rail.
 */
export const SettingsLayout = forwardRef<HTMLElement, SettingsLayoutProps>(
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
      profileBanner,
      summaryCard,
      categories,
      activeCategoryId,
      onCategoryChange,
      aside,
      helpRail,
      saveBar,
      footerActions,
      maxWidth = "default",
      gutter = "default",
      canvasBg = "canvas",
      className = "",
      children,
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
          subtitle={subtitle ?? description}
          badges={badges}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
          backAction={backAction}
        />
      ) : null);

    const resolvedBanner = profileBanner ?? summaryCard;
    const resolvedAside = aside ?? helpRail;
    const resolvedSaveBar = saveBar ?? footerActions;

    const renderCategoriesNav = () => {
      if (!categories || categories.length === 0) return null;

      return (
        <nav aria-label="Settings Categories" className="w-full">
          {/* Mobile Horizontal Tabs */}
          <div className="flex md:hidden overflow-x-auto gap-2 pb-2 mb-4 scrollbar-thin">
            {categories.map((cat) => {
              const isActive = cat.id === activeCategoryId;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => onCategoryChange?.(cat.id)}
                  disabled={cat.disabled}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex shrink-0 items-center gap-2 rounded-[var(--radius-pill)] px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    isActive
                      ? "bg-[var(--brand-600)] text-white shadow-sm"
                      : "bg-[var(--surface-panel)] text-[var(--text-secondary)] border border-[color:var(--shell-border)]"
                  }`}
                >
                  {cat.icon ? (
                    typeof cat.icon === "string" ? (
                      <Icon name={cat.icon as IconName} size="0.875rem" />
                    ) : (
                      cat.icon
                    )
                  ) : null}
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>

          {/* Desktop Vertical List */}
          <div className="hidden md:block space-y-1">
            {categories.map((cat) => {
              const isActive = cat.id === activeCategoryId;
              const content = (
                <div className="flex items-center justify-between gap-3 w-full">
                  <div className="flex items-center gap-3 min-w-0">
                    {cat.icon ? (
                      <div
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] ${
                          isActive
                            ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                            : "bg-[var(--surface-muted)] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]"
                        }`}
                      >
                        {typeof cat.icon === "string" ? (
                          <Icon name={cat.icon as IconName} size="1rem" />
                        ) : (
                          cat.icon
                        )}
                      </div>
                    ) : null}
                    <div className="min-w-0 text-left">
                      <p
                        className={`text-sm font-semibold truncate ${
                          isActive
                            ? "text-[var(--text-brand)]"
                            : "text-[var(--text-primary)] group-hover:text-[var(--text-brand)]"
                        }`}
                      >
                        {cat.label}
                      </p>
                      {cat.description ? (
                        <p className="text-xs text-[var(--text-secondary)] truncate">
                          {cat.description}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  {cat.badge ? <div className="shrink-0">{cat.badge}</div> : null}
                </div>
              );

              const itemClasses = `group flex w-full items-center rounded-[var(--radius-lg)] border p-3 text-left transition-all ${
                isActive
                  ? "border-[color:var(--brand-500)]/40 bg-[var(--surface-panel)] shadow-sm"
                  : "border-transparent hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
              } ${cat.disabled ? "pointer-events-none opacity-50" : ""}`;

              if (cat.href) {
                return (
                  <Link
                    key={cat.id}
                    href={cat.href}
                    className={itemClasses}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {content}
                  </Link>
                );
              }

              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => onCategoryChange?.(cat.id)}
                  disabled={cat.disabled}
                  aria-current={isActive ? "page" : undefined}
                  className={itemClasses}
                >
                  {content}
                </button>
              );
            })}
          </div>
        </nav>
      );
    };

    return (
      <PageFrame
        ref={ref}
        archetype="settings"
        header={renderedHeader}
        maxWidth={maxWidth}
        gutter={gutter}
        bg={canvasBg}
        className={className}
        {...rest}
      >
        <div className="space-y-6 sm:space-y-8">
          {resolvedBanner ? (
            <div className="settings-banner">{resolvedBanner}</div>
          ) : null}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-12 md:gap-8">
            {categories && categories.length > 0 ? (
              <aside className="md:col-span-4 lg:col-span-3">
                <div className="sticky top-6">{renderCategoriesNav()}</div>
              </aside>
            ) : null}

            <div
              className={`min-w-0 space-y-6 ${
                categories && categories.length > 0
                  ? resolvedAside
                    ? "md:col-span-8 lg:col-span-6"
                    : "md:col-span-8 lg:col-span-9"
                  : resolvedAside
                  ? "lg:col-span-8"
                  : "col-span-12"
              }`}
            >
              {children}
            </div>

            {resolvedAside ? (
              <aside className="min-w-0 space-y-6 md:col-span-12 lg:col-span-3">
                <div className="sticky top-6">{resolvedAside}</div>
              </aside>
            ) : null}
          </div>

          {resolvedSaveBar ? (
            <div className="sticky bottom-4 z-20 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-header)]/95 p-4 shadow-[var(--shadow-float)] backdrop-blur-md">
              {resolvedSaveBar}
            </div>
          ) : null}
        </div>
      </PageFrame>
    );
  }
);

SettingsLayout.displayName = "SettingsLayout";

export default SettingsLayout;
