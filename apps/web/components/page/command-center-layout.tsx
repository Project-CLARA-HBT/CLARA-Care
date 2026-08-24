"use client";

import React, {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Icon, type IconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { PageFrame, type PageCanvasBg, type PageGutter, type PageMaxWidth } from "./page-frame";
import { PageHeader, type BreadcrumbItem, type PageHeaderBackAction } from "./page-header";

export interface CommandCenterMetric {
  id?: string;
  label: string;
  value: ReactNode;
  change?: string | ReactNode;
  trend?: "up" | "down" | "neutral";
  hint?: string;
  icon?: IconName | ReactNode;
  tone?: "brand" | "ok" | "warn" | "danger" | "neutral";
  status?: ReactNode;
  onClick?: () => void;
}

export type CommandCenterDensity = "comfortable" | "compact" | "dense";

export interface CommandCenterLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
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
  /** Command bar or tab strip (e.g. AdminCommandStrip) */
  commandStrip?: ReactNode;
  /** Alias for commandStrip */
  navStrip?: ReactNode;
  /** Active workspace context (e.g. 'personal', 'clinical', 'research', 'admin') */
  workspace?: string;
  /** Top KPI summary metrics */
  metrics?: CommandCenterMetric[] | ReactNode;
  /** Alias for metrics */
  kpiGrid?: ReactNode;
  /** Real-time live activity / incident stream panel */
  liveStream?: ReactNode;
  /** Alias for liveStream */
  sidePanel?: ReactNode;
  /** Slide-over diagnostic or detail inspector */
  inspector?: ReactNode;
  /** Layout density mode */
  density?: CommandCenterDensity;
  /** Number of grid columns for metric cards */
  metricColumns?: 2 | 3 | 4 | 5 | 6;
  /** Max width */
  maxWidth?: PageMaxWidth;
  /** Gutter spacing */
  gutter?: PageGutter;
  /** Canvas background */
  canvasBg?: PageCanvasBg;
  /** Main body content */
  children?: ReactNode;
}

const TONE_CLASSES: Record<string, { icon: string; border: string }> = {
  brand: {
    icon: "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]",
    border: "border-t-[color:var(--brand-500)]",
  },
  ok: {
    icon: "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
    border: "border-t-[color:var(--status-ok-border)]",
  },
  warn: {
    icon: "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
    border: "border-t-[color:var(--status-warn-border)]",
  },
  danger: {
    icon: "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
    border: "border-t-[color:var(--status-danger-border)]",
  },
  neutral: {
    icon: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
    border: "border-t-[color:var(--shell-border)]",
  },
};

const METRIC_COLUMNS_MAP: Record<number, string> = {
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
  5: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5",
  6: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6",
};

/**
 * Command Center archetype layout primitive.
 * Optimized for dense administrative consoles, operational metrics, live streams, and diagnostic tooling.
 */
export const CommandCenterLayout = forwardRef<HTMLElement, CommandCenterLayoutProps>(
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
      commandStrip,
      navStrip,
      workspace,
      metrics,
      kpiGrid,
      liveStream,
      sidePanel,
      inspector,
      density = "dense",
      metricColumns = 4,
      maxWidth = "dense",
      gutter = "compact",
      canvasBg = "canvas",
      className = "",
      children,
      ...rest
    },
    ref
  ) => {
    const resolvedStrip = commandStrip ?? navStrip;
    const resolvedStream = liveStream ?? sidePanel;
    const resolvedMetrics = metrics ?? kpiGrid;

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
          density={density === "comfortable" ? "comfortable" : "compact"}
        />
      ) : null);

    const renderMetricTile = (metric: CommandCenterMetric, index: number) => {
      const toneConfig =
        TONE_CLASSES[metric.tone ?? "brand"] ?? TONE_CLASSES.brand;

      return (
        <SurfaceCard
          key={metric.id ?? metric.label + index}
          onClick={metric.onClick}
          className={`relative border-t-2 ${toneConfig.border} ${
            density === "dense" ? "p-3.5" : "p-4 sm:p-5"
          } ${metric.onClick ? "cursor-pointer hover:border-[color:var(--shell-border-strong)]" : ""}`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-medium text-[var(--text-secondary)] truncate">
              {metric.label}
            </p>
            {metric.icon ? (
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-md)] ${toneConfig.icon}`}
              >
                {typeof metric.icon === "string" ? (
                  <Icon name={metric.icon as IconName} size="0.875rem" />
                ) : (
                  metric.icon
                )}
              </div>
            ) : metric.status ? (
              <div>{metric.status}</div>
            ) : null}
          </div>

          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={`${
                density === "dense"
                  ? "text-xl sm:text-2xl"
                  : "text-2xl sm:text-3xl"
              } font-bold tracking-tight text-[var(--text-primary)]`}
            >
              {metric.value}
            </span>
            {metric.change ? (
              <span
                className={`text-xs font-semibold ${
                  metric.trend === "up"
                    ? "text-[var(--status-ok-text)]"
                    : metric.trend === "down"
                    ? "text-[var(--status-danger-text)]"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                {metric.change}
              </span>
            ) : null}
          </div>

          {metric.hint ? (
            <p className="mt-1 text-[0.6875rem] text-[var(--text-muted)] truncate">
              {metric.hint}
            </p>
          ) : null}
        </SurfaceCard>
      );
    };

    const renderMetrics = () => {
      if (!resolvedMetrics) return null;

      if (React.isValidElement(resolvedMetrics)) {
        return <div className="command-metrics mb-5">{resolvedMetrics}</div>;
      }

      if (Array.isArray(resolvedMetrics) && resolvedMetrics.length > 0) {
        const colClass =
          METRIC_COLUMNS_MAP[metricColumns] ?? METRIC_COLUMNS_MAP[4];

        return (
          <section aria-label="KPI Metrics" className="command-metrics mb-5">
            <div className={`grid gap-3 sm:gap-4 ${colClass}`}>
              {resolvedMetrics.map(renderMetricTile)}
            </div>
          </section>
        );
      }

      return null;
    };

    return (
      <PageFrame
        ref={ref}
        archetype="command-center"
        workspace={workspace}
        header={
          renderedHeader || resolvedStrip ? (
            <div className="space-y-4">
              {renderedHeader}
              {resolvedStrip ? (
                <div className="command-nav-strip">{resolvedStrip}</div>
              ) : null}
            </div>
          ) : null
        }
        maxWidth={maxWidth}
        gutter={gutter}
        bg={canvasBg}
        className={className}
        {...rest}
      >
        <div className="space-y-5">
          {renderMetrics()}

          {resolvedStream ? (
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px] xl:grid-cols-[1fr_400px]">
              <div className="min-w-0 space-y-5">{children}</div>
              <aside className="min-w-0 space-y-5">{resolvedStream}</aside>
            </div>
          ) : (
            <div className="space-y-5">{children}</div>
          )}

          {inspector ? (
            <div className="command-inspector">{inspector}</div>
          ) : null}
        </div>
      </PageFrame>
    );
  }
);

CommandCenterLayout.displayName = "CommandCenterLayout";

export default CommandCenterLayout;
