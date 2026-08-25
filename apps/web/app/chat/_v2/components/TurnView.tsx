"use client";

import {
  Component,
  memo,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { UILanguage } from "@/lib/ui-language";
import { t } from "@/lib/i18n/catalog";
import type { UserRole } from "@/lib/auth-store";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import AnswerRenderer from "@/app/chat/_v2/components/AnswerRenderer";
import FlowTimeline from "@/app/chat/_v2/components/FlowTimeline";
import Icon from "@/components/ui/icon";
import type { SourceInspectionItem } from "@/components/shell/inspector-drawer";

/**
 * Clean editorial conversation feed turn with Spec v8 READ_COMPOSE layout.
 * User bubble (compact) & AI Assistant turn (document-style structured answer).
 * Action buttons: Copy, Save to Notebook, Voice Read-Aloud, Related Questions.
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
  onInspectSource?: (source: SourceInspectionItem) => void;
  onInspectAllSources?: (sources: SourceInspectionItem[]) => void;
  onAskFollowUp?: (question: string) => void;
};

function TurnView({
  turn,
  uiLanguage,
  role = "normal",
  onLaunchResearch,
  onSaveNote,
  onInspectSource,
  onInspectAllSources,
  onAskFollowUp,
}: TurnViewProps) {
  const tier2Result = turn.result.tier === "tier2" ? turn.result : null;

  const [isCopied, setIsCopied] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showFollowUps, setShowFollowUps] = useState(false);

  const handleCopyAnswer = useCallback(async () => {
    const text = turn.result.answer || "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  }, [turn.result.answer]);

  const handleSaveToNotebook = useCallback(() => {
    const text = turn.result.answer || "";
    if (onSaveNote) {
      onSaveNote(text);
    }
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  }, [turn.result.answer, onSaveNote]);

  const handleToggleSpeech = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    } else {
      window.speechSynthesis.cancel();
      const cleanText = (turn.result.answer || "")
        .replace(/[#*_`\[\]()]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      if (!cleanText) return;
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.lang = uiLanguage === "vi" ? "vi-VN" : "en-US";
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
      setIsSpeaking(true);
    }
  }, [isSpeaking, turn.result.answer, uiLanguage]);

  const followUpSuggestions = useMemo(() => {
    if (uiLanguage === "vi") {
      return [
        "Tác dụng phụ thường gặp nhất và cách theo dõi?",
        "Có cần kiêng khem thực phẩm hoặc thuốc nào khác không?",
        "Khi nào các triệu chứng cần đi khám bác sĩ ngay?",
      ];
    }
    return [
      "What are the common side effects to watch for?",
      "Are there any food, supplement, or drug interactions?",
      "When should I see a doctor immediately for these symptoms?",
    ];
  }, [uiLanguage]);

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
                  onInspectSource={onInspectSource}
                  onInspectAllSources={onInspectAllSources}
                />
                <details className="group rounded-xl border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)]/70 px-4 py-3 transition-colors">
                  <summary className="cursor-pointer text-xs sm:text-sm font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <Icon name="clinical-notes" size={14} className="text-[var(--text-brand)]" />
                      <span>{t(uiLanguage, "chat.turnView.explain")}</span>
                    </span>
                    <span className="rounded-full bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-brand)] border border-[color:var(--shell-border)]/50">
                      CoT Trace
                    </span>
                  </summary>
                  <div className="mt-3.5 pt-3 border-t border-[color:var(--shell-border)]/40">
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
                onInspectSource={onInspectSource}
                onInspectAllSources={onInspectAllSources}
              />
            )}
          </TurnErrorBoundary>

          {/* 1-Click Action Buttons under each assistant message */}
          {turn.result.answer ? (
            <div className="flex flex-col gap-2.5 border-t border-[color:var(--shell-border)]/60 pt-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex flex-wrap items-center gap-1.5">
                  {/* 1. Copy Answer */}
                  <button
                    type="button"
                    onClick={handleCopyAnswer}
                    aria-label={t(uiLanguage, "chat.turnView.copyAnswer")}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition hover:border-[color:var(--brand-500)] hover:text-[var(--text-primary)] active:scale-95"
                  >
                    <Icon
                      name={isCopied ? "check" : "clinical-notes"}
                      size={13}
                      className={isCopied ? "text-emerald-500" : "text-[var(--text-brand)]"}
                    />
                    <span>{isCopied ? t(uiLanguage, "chat.turnView.copied") : t(uiLanguage, "chat.turnView.copyAnswer")}</span>
                  </button>

                  {/* 2. Save to Notebook */}
                  {onSaveNote ? (
                    <button
                      type="button"
                      onClick={handleSaveToNotebook}
                      aria-label={t(uiLanguage, "chat.turnView.saveToNotebook")}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition hover:border-[color:var(--brand-500)] hover:text-[var(--text-primary)] active:scale-95"
                    >
                      <Icon
                        name={isSaved ? "check" : "folder"}
                        size={13}
                        className={isSaved ? "text-emerald-500" : "text-[var(--text-brand)]"}
                      />
                      <span>{isSaved ? t(uiLanguage, "chat.turnView.saved") : t(uiLanguage, "chat.turnView.saveToNotebook")}</span>
                    </button>
                  ) : null}

                  {/* 3. Text-to-Speech (Voice Read-Aloud) */}
                  <button
                    type="button"
                    onClick={handleToggleSpeech}
                    aria-label={isSpeaking ? t(uiLanguage, "chat.turnView.stopSpeech") : t(uiLanguage, "chat.turnView.readAloud")}
                    className={[
                      "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition active:scale-95",
                      isSpeaking
                        ? "border-red-500/50 bg-red-500/10 text-red-500 motion-safe:animate-pulse"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:border-[color:var(--brand-500)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <Icon
                      name={isSpeaking ? "stop" : "mic"}
                      size={13}
                      className={isSpeaking ? "text-red-500" : "text-[var(--text-brand)]"}
                    />
                    <span>{isSpeaking ? t(uiLanguage, "chat.turnView.stopSpeech") : t(uiLanguage, "chat.turnView.readAloud")}</span>
                  </button>

                  {/* 4. Ask Related Question */}
                  <button
                    type="button"
                    onClick={() => setShowFollowUps((prev) => !prev)}
                    aria-expanded={showFollowUps}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--brand-500)]/40 bg-[var(--surface-brand-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-brand)] transition hover:bg-[var(--brand-500)]/15 active:scale-95"
                  >
                    <Icon name="chat" size={13} />
                    <span>{t(uiLanguage, "chat.turnView.relatedQuestions")}</span>
                  </button>
                </div>

                {onLaunchResearch && turn.query.trim() ? (
                  <button
                    type="button"
                    onClick={() => onLaunchResearch(turn.query)}
                    className="inline-flex min-h-7 items-center gap-1 rounded-lg text-[11px] font-medium text-[var(--text-muted)] hover:text-[var(--text-brand)] transition"
                  >
                    <Icon name="clinical-notes" size={13} aria-hidden="true" />
                    <span>
                      {t(
                        uiLanguage,
                        tier2Result
                          ? "chat.turnView.refineEvidence"
                          : "chat.turnView.investigate",
                      )}
                    </span>
                  </button>
                ) : null}
              </div>

              {/* Related Questions Expandable Container */}
              {showFollowUps && (
                <div className="rounded-xl border border-[color:var(--brand-500)]/30 bg-[var(--surface-muted)]/60 p-3 space-y-2">
                  <p className="text-[11px] font-semibold text-[var(--text-brand)] flex items-center gap-1.5">
                    <Icon name="chat" size={12} />
                    <span>{uiLanguage === "vi" ? "Gợi ý câu hỏi đào sâu tiếp theo:" : "Suggested follow-up questions:"}</span>
                  </p>
                  <div className="flex flex-col sm:flex-row flex-wrap gap-1.5">
                    {followUpSuggestions.map((sq, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => {
                          if (onAskFollowUp) {
                            onAskFollowUp(sq);
                          } else if (onLaunchResearch) {
                            onLaunchResearch(sq);
                          }
                          setShowFollowUps(false);
                        }}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-xs text-left font-medium text-[var(--text-secondary)] transition hover:border-[color:var(--brand-500)] hover:bg-[var(--surface-brand-soft)] hover:text-[var(--text-brand)]"
                      >
                        <span className="text-[var(--text-brand)] shrink-0">→</span>
                        <span>{sq}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export default memo(TurnView);
