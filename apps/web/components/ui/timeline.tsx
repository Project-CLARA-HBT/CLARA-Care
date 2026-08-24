"use client";

import type { HTMLAttributes, LiHTMLAttributes, OlHTMLAttributes, ReactNode } from "react";
import React, { createContext, useContext } from "react";
import { Icon, resolveIconName, type IconName } from "@/components/ui/icon";

export type TimelineNodeState = "completed" | "active" | "pending" | "disputed" | "error";
export type TimelineOrientation = "vertical" | "horizontal";

export interface TimelineItemData {
  id?: string | number;
  state?: TimelineNodeState;
  title: ReactNode;
  description?: ReactNode;
  timestamp?: ReactNode;
  icon?: IconName | string | ReactNode;
  tags?: ReactNode;
  action?: ReactNode;
  className?: string;
  onClick?: () => void;
}

export interface TimelineProps extends OlHTMLAttributes<HTMLOListElement> {
  items?: TimelineItemData[];
  orientation?: TimelineOrientation;
  className?: string;
  children?: ReactNode;
}

interface TimelineContextValue {
  orientation: TimelineOrientation;
}

const TimelineContext = createContext<TimelineContextValue>({
  orientation: "vertical",
});

export const useTimelineContext = () => useContext(TimelineContext);

const STATE_NODE_STYLES: Record<
  TimelineNodeState,
  {
    wrapper: string;
    iconColor: string;
    defaultIcon: IconName;
  }
> = {
  completed: {
    wrapper:
      "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border-2 border-[color:var(--status-ok-border)]",
    iconColor: "text-[var(--status-ok-text)]",
    defaultIcon: "check",
  },
  active: {
    wrapper:
      "bg-[var(--brand-600)] text-white ring-4 ring-[var(--brand-500)]/20 shadow-sm border-2 border-[var(--brand-500)]",
    iconColor: "text-white",
    defaultIcon: "progress",
  },
  pending: {
    wrapper:
      "bg-[var(--surface-muted)] text-[var(--text-muted)] border border-[color:var(--shell-border)]",
    iconColor: "text-[var(--text-muted)]",
    defaultIcon: "more",
  },
  disputed: {
    wrapper:
      "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border-2 border-[color:var(--status-warn-border)]",
    iconColor: "text-[var(--status-warn-text)]",
    defaultIcon: "warning",
  },
  error: {
    wrapper:
      "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border-2 border-[color:var(--status-danger-border)]",
    iconColor: "text-[var(--status-danger-text)]",
    defaultIcon: "close",
  },
};

export interface TimelineNodeProps extends HTMLAttributes<HTMLDivElement> {
  state?: TimelineNodeState;
  icon?: IconName | string | ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function TimelineNode({
  state = "pending",
  icon,
  size = "md",
  className = "",
  ...rest
}: TimelineNodeProps) {
  const nodeConfig = STATE_NODE_STYLES[state] ?? STATE_NODE_STYLES.pending;

  const sizeClasses =
    size === "sm"
      ? "h-6 w-6 text-xs"
      : size === "lg"
      ? "h-10 w-10 text-base"
      : "h-8 w-8 text-sm";

  const iconSizes = size === "sm" ? "0.75rem" : size === "lg" ? "1.25rem" : "0.95rem";

  const renderIcon = () => {
    if (React.isValidElement(icon)) {
      return icon;
    }
    if (typeof icon === "string") {
      return <Icon name={resolveIconName(icon)} size={iconSizes} aria-hidden="true" />;
    }
    if (state === "pending" && !icon) {
      return <span className="h-2 w-2 rounded-full bg-[var(--text-muted)]" />;
    }
    const fallbackIcon = nodeConfig.defaultIcon;
    return <Icon name={fallbackIcon} size={iconSizes} aria-hidden="true" />;
  };

  return (
    <div
      data-state={state}
      className={`relative z-10 flex shrink-0 items-center justify-center rounded-full transition-all duration-150 ${sizeClasses} ${nodeConfig.wrapper} ${className}`}
      {...rest}
    >
      {renderIcon()}
    </div>
  );
}

export function TimelineConnector({
  state = "pending",
  isLast = false,
  className = "",
}: {
  state?: TimelineNodeState;
  isLast?: boolean;
  className?: string;
}) {
  const { orientation } = useTimelineContext();

  if (isLast) return null;

  const isCompleted = state === "completed";
  const lineColor = isCompleted
    ? "bg-[var(--status-ok-border,var(--brand-600))]"
    : "bg-[var(--shell-border)]";

  if (orientation === "horizontal") {
    return (
      <div
        data-testid="timeline-connector-horizontal"
        aria-hidden="true"
        className={`absolute top-4 left-1/2 w-full h-0.5 -translate-y-1/2 transition-colors duration-150 ${lineColor} ${className}`}
      />
    );
  }

  return (
    <div
      data-testid="timeline-connector-vertical"
      aria-hidden="true"
      className={`absolute top-8 bottom-0 left-[calc(1rem-1px)] w-0.5 -translate-x-1/2 transition-colors duration-150 ${lineColor} ${className}`}
    />
  );
}

export function TimelineTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <h4 className={`font-semibold text-sm sm:text-base text-[var(--text-primary)] ${className}`}>
      {children}
    </h4>
  );
}

export function TimelineDescription({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`mt-1 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed ${className}`}>
      {children}
    </div>
  );
}

export function TimelineTimestamp({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <time className={`inline-flex items-center gap-1 text-xs text-[var(--text-muted)] font-medium ${className}`}>
      {children}
    </time>
  );
}

export function TimelineContent({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { orientation } = useTimelineContext();

  if (orientation === "horizontal") {
    return <div className={`mt-2 text-center w-full ${className}`}>{children}</div>;
  }

  return <div className={`min-w-0 flex-1 pt-0.5 ${className}`}>{children}</div>;
}

export interface TimelineItemProps extends LiHTMLAttributes<HTMLLIElement> {
  state?: TimelineNodeState;
  isLast?: boolean;
  children?: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function TimelineItem({
  state = "pending",
  isLast = false,
  children,
  className = "",
  onClick,
  ...rest
}: TimelineItemProps) {
  const { orientation } = useTimelineContext();
  const isClickable = Boolean(onClick);

  if (orientation === "horizontal") {
    return (
      <li
        role="listitem"
        onClick={onClick}
        data-state={state}
        className={`relative flex-1 flex flex-col items-center min-w-[120px] ${
          isClickable ? "cursor-pointer group" : ""
        } ${className}`}
        {...rest}
      >
        <TimelineConnector state={state} isLast={isLast} />
        {children}
      </li>
    );
  }

  return (
    <li
      role="listitem"
      onClick={onClick}
      data-state={state}
      className={`relative flex items-start gap-4 pb-8 last:pb-0 ${
        isClickable ? "cursor-pointer group" : ""
      } ${className}`}
      {...rest}
    >
      <TimelineConnector state={state} isLast={isLast} />
      {children}
    </li>
  );
}

export function Timeline({
  items,
  orientation = "vertical",
  className = "",
  children,
  ...rest
}: TimelineProps) {
  const containerClasses =
    orientation === "horizontal"
      ? "flex items-start w-full overflow-x-auto hide-scrollbar py-2"
      : "relative flex flex-col space-y-0";

  return (
    <TimelineContext.Provider value={{ orientation }}>
      <ol
        role="list"
        data-orientation={orientation}
        className={`${containerClasses} ${className}`}
        {...rest}
      >
        {items
          ? items.map((item, index) => {
              const isLast = index === items.length - 1;
              const itemState = item.state ?? "pending";

              return (
                <TimelineItem
                  key={item.id ?? index}
                  state={itemState}
                  isLast={isLast}
                  onClick={item.onClick}
                  className={item.className}
                >
                  <TimelineNode state={itemState} icon={item.icon} />
                  <TimelineContent>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <TimelineTitle>{item.title}</TimelineTitle>
                      {item.timestamp && (
                        <TimelineTimestamp>{item.timestamp}</TimelineTimestamp>
                      )}
                    </div>
                    {item.description && (
                      <TimelineDescription>{item.description}</TimelineDescription>
                    )}
                    {item.tags && <div className="mt-2 flex flex-wrap gap-1.5">{item.tags}</div>}
                    {item.action && <div className="mt-3 flex items-center gap-2">{item.action}</div>}
                  </TimelineContent>
                </TimelineItem>
              );
            })
          : children}
      </ol>
    </TimelineContext.Provider>
  );
}

export default Timeline;
