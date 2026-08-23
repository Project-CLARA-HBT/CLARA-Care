"use client";

import { Component, memo, type ReactNode } from "react";

import type { UILanguage } from "@/lib/ui-language";
import { t } from "@/lib/i18n/catalog";
import type { UserRole } from "@/lib/auth-store";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import AnswerRenderer from "@/app/chat/_v2/components/AnswerRenderer";
import FlowTimeline from "@/app/chat/_v2/components/FlowTimeline";
import Icon from "@/components/ui/icon";

/**
 * Clean editorial conversation feed turn with refined bubble typography.
 * Aligned with Stitch template h_i_clara_active_conversation_refined.
 *
 * User bubble (right-aligned, refined bubble typography with soft contrast).
 * Assistant turn (left-aligned, AI avatar, status header, structured answer-first card).
 */

type TurnErrorBoundaryProps = {
  children: ReactNode;
  fallbackLabel: string;
};

class TurnErrorBoundary extends Component<
  TurnErrorBoundaryProps,
  { hasError: boolean }
> {
  constructor(props: TurnErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <p
          role="alert"
          className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-[12px] text-[var(--status-danger-text)]"
        >
          {this.props.fallbackLabel}
        </p>
      );
    }
    return this.props.children;
  }
}

export type TurnViewProps = {
  turn: ConversationItem;
  uiLanguage: UILanguage;
  role?: UserRole;
  onLaunchResearch?: (query: string) => void;
  onSaveNote?: (answerText: string) => void;
};

function TurnView({
  turn,
  uiLanguage,
  role = "normal",
  onLaunchResearch,
  onSaveNote,
}: TurnViewProps) {
  const tier2Result = turn.result.tier === "tier2" ? turn.result : null;

  return (
    <article
      className="space-y-4"
      aria-label={t(uiLanguage, "chat.turnView.aria")}
    >
      {/* User Bubble */}
      {turn.query.trim() ? (
        <div className="flex justify-end">
          <div className="max-w-[88%] sm:max-w-[80%] rounded-2xl rounded-tr-none border border-[color:var(--shell-border)]/70 bg-[var(--surface-brand-soft)] dark:bg-[#1c2430] px-5 py-3.5 text-sm sm:text-[15px] leading-relaxed text-[var(--text-primary)] shadow-xs">
            <p className="whitespace-pre-wrap">{turn.query}</p>
          </div>
        </div>
      ) : null}

      {/* AI Assistant Turn */}
      <div className="flex flex-col items-start w-full">
        {/* Assistant Header Avatar & Label */}
        <div className="flex items-center gap-2.5 mb-2.5 px-1">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-xs">
            <Icon name="clinical-notes" size={15} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold tracking-tight text-[var(--text-primary)]">
              CLARA
            </span>
            <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-[9px] font-semibold text-[var(--text-brand)]">
              {tier2Result ? "DeepBeta" : "Assistant"}
            </span>
          </div>
        </div>

        {/* Structured Response Container */}
        <div className="w-full rounded-2xl border border-[color:var(--shell-border)]/80 dark:border-[#2A3950] bg-[var(--surface-panel)] dark:bg-[#111C29] p-5 sm:p-7 shadow-sm space-y-5">
          <TurnErrorBoundary
            fallbackLabel={t(uiLanguage, "chat.turnView.displayFailed")}
          >
            {tier2Result ? (
              <div className="space-y-5">
                <AnswerRenderer
                  result={turn.result}
                  uiLanguage={uiLanguage}
                  role={role}
                  onSaveNote={onSaveNote}
                />
                <details className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-2.5">
                  <summary className="cursor-pointer text-xs sm:text-sm font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                    {t(uiLanguage, "chat.turnView.explain")}
                  </summary>
                  <div className="mt-3">
                    <FlowTimeline result={tier2Result} uiLanguage={uiLanguage} />
                  </div>
                </details>
              </div>
            ) : (
              <AnswerRenderer
                result={turn.result}
                uiLanguage={uiLanguage}
                role={role}
                onSaveNote={onSaveNote}
              />
            )}
          </TurnErrorBoundary>

          {onLaunchResearch && turn.query.trim() ? (
            <div className="flex justify-end border-t border-[color:var(--shell-border)]/60 pt-3">
              <button
                type="button"
                onClick={() => onLaunchResearch(turn.query)}
                className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-medium text-[var(--text-brand)] transition hover:border-[color:var(--brand-500)] hover:bg-[var(--surface-brand-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]"
              >
                <Icon name="clinical-notes" size={14} aria-hidden="true" />
                <span>
                  {t(
                    uiLanguage,
                    tier2Result
                      ? "chat.turnView.refineEvidence"
                      : "chat.turnView.investigate",
                  )}
                </span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

/**
 * Memoized turn view.
 */
export default memo(TurnView);
