"use client";

import { Component, memo, type ReactNode } from "react";

import type { UILanguage } from "@/lib/ui-language";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import AnswerRenderer from "@/app/chat/_v2/components/AnswerRenderer";
import FlowTimeline from "@/app/chat/_v2/components/FlowTimeline";

/**
 * A single conversation turn (user query + CLARA answer) for the rebuilt chat.
 *
 * Composes `AnswerRenderer` and, for tier2 turns, `FlowTimeline`. Each turn is
 * wrapped in an error boundary so one malformed turn can never crash the whole
 * message log (design "Error Handling": render errors isolated per turn).
 */

type TurnErrorBoundaryProps = {
  children: ReactNode;
  fallbackLabel: string;
};

class TurnErrorBoundary extends Component<TurnErrorBoundaryProps, { hasError: boolean }> {
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
};

function TurnView({ turn, uiLanguage }: TurnViewProps) {
  const isEn = uiLanguage === "en";
  const tier2Result = turn.result.tier === "tier2" ? turn.result : null;

  return (
    <article className="space-y-3" aria-label={isEn ? "Conversation turn" : "Lượt trò chuyện"}>
      {turn.query.trim() ? (
        <div className="flex justify-end">
          <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-4 py-2.5 text-sm text-[var(--text-primary)]">
            {turn.query}
          </div>
        </div>
      ) : null}

      <div className="rounded-2xl rounded-tl-sm border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
        <TurnErrorBoundary
          fallbackLabel={
            isEn
              ? "This answer could not be displayed."
              : "Không thể hiển thị câu trả lời này."
          }
        >
          {tier2Result ? (
            <div className="space-y-3">
              <FlowTimeline result={tier2Result} uiLanguage={uiLanguage} />
              <AnswerRenderer result={turn.result} uiLanguage={uiLanguage} />
            </div>
          ) : (
            <AnswerRenderer result={turn.result} uiLanguage={uiLanguage} />
          )}
        </TurnErrorBoundary>
      </div>
    </article>
  );
}

/**
 * Memoized so an unchanged turn never re-renders when the parent `MessageLog`
 * re-renders (new turns appended, streaming flag toggling). `turn` is a stable
 * reference held in the turns cache, so referential equality is the right
 * bailout signal here (Requirement 7.2, Property P9).
 */
export default memo(TurnView);
