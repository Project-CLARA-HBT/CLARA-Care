"use client";

import { memo, useMemo } from "react";

import type { UILanguage } from "@/lib/ui-language";
import { t } from "@/lib/i18n/catalog";
import type { ResearchTier2Result } from "@/lib/research";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import {
  buildLogicFlowNodes,
  localizeLogicFlowLabel,
  localizeLogicFlowStatus,
  type LogicFlowNodeStatus,
} from "@/app/chat/_v2/lib/telemetry-format";
import { StatusDot, type StatusTone } from "@/app/chat/_v2/components/primitives";

/**
 * Inline reasoning timeline for deep/deep_beta turns (Requirement 2.3, 3.2).
 *
 * Maps the three-stage logic-flow blueprint into compact, accessible status
 * rows. Status → tone mapping is covered by the telemetry-format property tests
 * (design Property P5). Pending-only, detail-less nodes are hidden so the
 * timeline never overwhelms the answer.
 */

const STATUS_TONE: Record<LogicFlowNodeStatus, StatusTone> = {
  pending: "neutral",
  in_progress: "info",
  completed: "ok",
  warning: "warn",
  failed: "danger",
  skipped: "neutral",
};

export type FlowTimelineProps = {
  result: ResearchTier2Result | null;
  uiLanguage: UILanguage;
  /** When true, an active run is in progress (affects the live region label). */
  isRunning?: boolean;
};

function FlowTimeline({ result, uiLanguage, isRunning = false }: FlowTimelineProps) {
  const nodes = useMemo(() => buildLogicFlowNodes(result), [result]);
  const visibleNodes = nodes.filter((node) => node.status !== "pending" || Boolean(node.detail));

  if (!visibleNodes.length && !isRunning) return null;

  const heading = t(uiLanguage, "chat.flowTimeline.heading");

  return (
    <section
      aria-label={heading}
      className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
    >
      <p className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-[var(--text-muted)]">
        {heading}
      </p>
      <ol className="space-y-1.5">
        {visibleNodes.map((node) => {
          // Stage detail strings originate from the backend and can carry
          // internal telemetry labels (`retrieval`, `RAG mode`, ...). This
          // timeline is visible to every role (not admin-gated), so the detail
          // is sanitized before display to keep telemetry jargon out of the
          // End_User view (Requirement 4.1).
          const detail = node.detail ? stripTelemetryLabels(node.detail) : "";
          return (
          <li
            key={node.id}
            className="flex items-start gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5"
          >
            <StatusDot
              tone={STATUS_TONE[node.status]}
              pulse={node.status === "in_progress"}
              className="mt-1"
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">
                  {localizeLogicFlowLabel(node.id, uiLanguage)}
                </p>
                <span className="shrink-0 text-[10px] font-medium text-[var(--text-muted)]">
                  {localizeLogicFlowStatus(node.status, uiLanguage)}
                </span>
              </div>
              {detail ? (
                <p className="mt-0.5 line-clamp-2 text-[11px] leading-5 text-[var(--text-secondary)]">
                  {detail}
                </p>
              ) : null}
            </div>
          </li>
          );
        })}
      </ol>
    </section>
  );
}

/**
 * Memoized: the timeline derives + sanitizes its stage rows on each render and
 * is rendered inside every tier2 turn, so it should only re-render when its
 * `result` reference actually changes (Requirement 7.2, Property P9).
 */
export default memo(FlowTimeline);
