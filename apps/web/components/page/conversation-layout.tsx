"use client";

import React, {
  forwardRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { type PageCanvasBg, type PageMaxWidth } from "./page-frame";

export interface ConversationLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Top conversation bar / custom header */
  header?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  headerActions?: ReactNode;
  /** Collapsible left history rail / navigation sidebar */
  sidebar?: ReactNode;
  /** Alias for sidebar */
  historyRail?: ReactNode;
  /** Controlled sidebar visibility */
  sidebarOpen?: boolean;
  /** Callback on sidebar toggle */
  onToggleSidebar?: () => void;
  /** Scrollable chat messages feed */
  messages?: ReactNode;
  /** Alias/fallback for messages */
  children?: ReactNode;
  /** Bottom input prompt composer */
  composer?: ReactNode;
  /** Right contextual evidence / inspector panel */
  inspector?: ReactNode;
  /** Alias for inspector */
  evidenceRail?: ReactNode;
  /** Controlled inspector visibility */
  inspectorOpen?: boolean;
  /** Callback on inspector toggle */
  onToggleInspector?: () => void;
  /** Medical disclaimer banner slot */
  disclaimerBanner?: ReactNode;
  /** Alias for disclaimerBanner */
  banner?: ReactNode;
  /** Ensure viewport fits exact height */
  fullHeight?: boolean;
  /** Max width for message center column */
  maxWidth?: PageMaxWidth;
  /** Background canvas */
  canvasBg?: PageCanvasBg;
}

const BG_MAP: Record<PageCanvasBg, string> = {
  canvas: "bg-[var(--bg-canvas)] text-[var(--text-primary)]",
  panel: "bg-[var(--surface-panel)] text-[var(--text-primary)]",
  subtle: "bg-[var(--surface-muted)] text-[var(--text-primary)]",
  sidebar: "bg-[var(--surface-sidebar)] text-[var(--text-primary)]",
  transparent: "bg-transparent text-[var(--text-primary)]",
};

const MAX_WIDTH_MAP: Record<PageMaxWidth, string> = {
  sm: "max-w-3xl",
  narrow: "max-w-3xl",
  md: "max-w-4xl",
  medium: "max-w-4xl",
  lg: "max-w-5xl",
  default: "max-w-5xl",
  wide: "max-w-6xl",
  xl: "max-w-6xl",
  "2xl": "max-w-7xl",
  "3xl": "max-w-[1600px]",
  "4xl": "max-w-[1600px]",
  dense: "max-w-[1600px]",
  prose: "max-w-3xl",
  full: "max-w-full",
};

/**
 * Conversation archetype layout primitive.
 * Optimized for AI chat interaction, message streams, docked composer, and side rails.
 */
export const ConversationLayout = forwardRef<HTMLElement, ConversationLayoutProps>(
  (
    {
      header,
      title,
      subtitle,
      headerActions,
      sidebar,
      historyRail,
      sidebarOpen: controlledSidebarOpen,
      onToggleSidebar,
      messages,
      children,
      composer,
      inspector,
      evidenceRail,
      inspectorOpen: controlledInspectorOpen,
      onToggleInspector,
      disclaimerBanner,
      banner,
      fullHeight = true,
      maxWidth = "default",
      canvasBg = "canvas",
      className = "",
      ...rest
    },
    ref
  ) => {
    const [internalSidebarOpen, setInternalSidebarOpen] = useState(false);
    const [internalInspectorOpen, setInternalInspectorOpen] = useState(false);

    const resolvedSidebar = sidebar ?? historyRail;
    const resolvedInspector = inspector ?? evidenceRail;
    const resolvedDisclaimer = disclaimerBanner ?? banner;
    const feedContent = messages ?? children;

    const isSidebarOpen = controlledSidebarOpen ?? internalSidebarOpen;
    const handleToggleSidebar = () => {
      if (onToggleSidebar) {
        onToggleSidebar();
      } else {
        setInternalSidebarOpen(!internalSidebarOpen);
      }
    };

    const isInspectorOpen = controlledInspectorOpen ?? internalInspectorOpen;
    const handleToggleInspector = () => {
      if (onToggleInspector) {
        onToggleInspector();
      } else {
        setInternalInspectorOpen(!internalInspectorOpen);
      }
    };

    const bgClass = BG_MAP[canvasBg] ?? BG_MAP.canvas;
    const maxWClass = MAX_WIDTH_MAP[maxWidth] ?? MAX_WIDTH_MAP.default;

    return (
      <div
        ref={ref as React.Ref<HTMLDivElement>}
        data-archetype="conversation"
        className={`relative flex w-full overflow-hidden ${
          fullHeight ? "h-full min-h-[500px]" : "min-h-screen"
        } ${bgClass} ${className}`}
        {...rest}
      >
        {/* Left History Sidebar */}
        {resolvedSidebar ? (
          <aside
            className={`transition-all duration-200 ease-in-out border-r border-[color:var(--shell-border)] bg-[var(--surface-sidebar)] ${
              isSidebarOpen
                ? "w-72 sm:w-80 shrink-0 block"
                : "hidden lg:block lg:w-0 lg:overflow-hidden lg:border-r-0"
            }`}
          >
            <div className="h-full w-72 sm:w-80 overflow-y-auto">{resolvedSidebar}</div>
          </aside>
        ) : null}

        {/* Central Chat Canvas */}
        <main className="flex flex-1 flex-col min-w-0 h-full overflow-hidden">
          {/* Header */}
          {header ? (
            <div className="shrink-0 border-b border-[color:var(--shell-border)] bg-[var(--surface-header)]/90 backdrop-blur-md">
              {header}
            </div>
          ) : title ? (
            <div className="flex shrink-0 items-center justify-between border-b border-[color:var(--shell-border)] bg-[var(--surface-header)]/90 px-4 py-3 backdrop-blur-md">
              <div className="flex items-center gap-3 min-w-0">
                {resolvedSidebar ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleToggleSidebar}
                    aria-label="Toggle conversation history"
                    icon="menu"
                  />
                ) : null}
                <div className="min-w-0">
                  <h1 className="truncate text-base font-semibold text-[var(--text-primary)]">
                    {title}
                  </h1>
                  {subtitle ? (
                    <p className="truncate text-xs text-[var(--text-secondary)]">
                      {subtitle}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {headerActions}
                {resolvedInspector ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleToggleInspector}
                    aria-label="Toggle context panel"
                    icon="clinical-notes"
                  />
                ) : null}
              </div>
            </div>
          ) : null}

          {/* Medical Disclaimer Banner */}
          {resolvedDisclaimer ? (
            <div className="shrink-0 border-b border-[color:var(--shell-border)]/50 bg-[var(--surface-brand-soft)] px-4 py-2 text-xs text-[var(--text-secondary)]">
              <div className={`mx-auto ${maxWClass}`}>{resolvedDisclaimer}</div>
            </div>
          ) : null}

          {/* Scrollable Messages Stream */}
          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6 sm:px-6">
            <div className={`mx-auto w-full ${maxWClass} space-y-6`}>
              {feedContent}
            </div>
          </div>

          {/* Bottom Prompt Composer */}
          {composer ? (
            <div className="shrink-0 border-t border-[color:var(--shell-border)] bg-[var(--surface-header)]/95 px-4 py-3 sm:px-6 sm:py-4 backdrop-blur-md">
              <div className={`mx-auto w-full ${maxWClass}`}>{composer}</div>
            </div>
          ) : null}
        </main>

        {/* Right Evidence / Inspector Panel */}
        {resolvedInspector ? (
          <aside
            className={`transition-all duration-200 ease-in-out border-l border-[color:var(--shell-border)] bg-[var(--surface-panel)] ${
              isInspectorOpen
                ? "w-80 sm:w-96 shrink-0 block"
                : "hidden xl:block xl:w-0 xl:overflow-hidden xl:border-l-0"
            }`}
          >
            <div className="h-full w-80 sm:w-96 overflow-y-auto">{resolvedInspector}</div>
          </aside>
        ) : null}
      </div>
    );
  }
);

ConversationLayout.displayName = "ConversationLayout";

export default ConversationLayout;
