import { FormEvent } from "react";
import { ResearchExecutionMode, ResearchRetrievalStackMode } from "@/lib/research";
import type { UILanguage } from "@/lib/ui-language";

type ChatComposerProps = {
  query: string;
  isSubmitting: boolean;
  onChangeQuery: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  quickPrompts: string[];
  selectedResearchMode: ResearchExecutionMode;
  selectedRetrievalStackMode: ResearchRetrievalStackMode;
  isFastResearchMode: boolean;
  onChangeResearchMode: (mode: ResearchExecutionMode) => void;
  onChangeRetrievalStackMode: (mode: ResearchRetrievalStackMode) => void;
  liveJobId: string | null;
  liveStatusNote: string;
  error: string;
  notice: string;
  uiLanguage: UILanguage;
};

const RESEARCH_MODE_OPTIONS: Array<{ id: ResearchExecutionMode; label: string }> = [
  { id: "fast", label: "Fast" },
  { id: "deep", label: "Deep" },
  { id: "deep_beta", label: "Deep Beta" },
];

const RESEARCH_RETRIEVAL_STACK_OPTIONS: Array<{ id: ResearchRetrievalStackMode; label: string }> = [
  { id: "auto", label: "Auto" },
  { id: "full", label: "Full" },
];

const COMPOSER_COPY: Record<
  UILanguage,
  {
    placeholder: string;
    submit: string;
    personal: string;
    liveStatusFallback: string;
  }
> = {
  vi: {
    placeholder: "Hỏi CLARA bất cứ điều gì về an toàn thuốc, DDI, guideline...",
    submit: "Gửi",
    personal: "Personal",
    liveStatusFallback: "Đang xử lý research job...",
  },
  en: {
    placeholder: "Ask CLARA anything about medication safety, DDI, and guidelines...",
    submit: "Send",
    personal: "Personal",
    liveStatusFallback: "Research job in progress...",
  },
};

function modeButtonClass(active: boolean, disabled = false): string {
  return [
    "inline-flex min-h-[28px] items-center justify-center rounded-full px-2.5 text-[10px] font-semibold transition",
    disabled
      ? "cursor-not-allowed text-[var(--text-muted)] opacity-60"
      : active
        ? "bg-cyan-600 text-white shadow-[0_0_0_1px_rgba(125,211,252,0.34)_inset]"
        : "text-slate-300 hover:text-slate-100",
  ].join(" ");
}

function stackButtonClass(active: boolean, disabled = false): string {
  return [
    "inline-flex min-h-[28px] items-center justify-center rounded-full px-2.5 text-[10px] font-semibold transition",
    disabled
      ? "cursor-not-allowed text-[var(--text-muted)] opacity-60"
      : active
        ? "bg-violet-500 text-white shadow-[0_0_0_1px_rgba(233,213,255,0.35)_inset]"
        : "text-slate-300 hover:text-slate-100",
  ].join(" ");
}

export default function ChatComposer(props: ChatComposerProps) {
  const {
    query,
    isSubmitting,
    onChangeQuery,
    onSubmit,
    quickPrompts,
    selectedResearchMode,
    selectedRetrievalStackMode,
    isFastResearchMode,
    onChangeResearchMode,
    onChangeRetrievalStackMode,
    liveJobId,
    liveStatusNote,
    error,
    notice,
    uiLanguage,
  } = props;

  const copy = COMPOSER_COPY[uiLanguage];
  const showRawError = error && !/internal server error/i.test(error);

  return (
    <footer className="sticky bottom-0 z-20 border-t border-[color:var(--shell-border)]/70 bg-[var(--bg-canvas)]/95 px-1.5 py-1 backdrop-blur-xl">
      <div className="mx-auto w-full max-w-none space-y-1.5">
        {quickPrompts.length ? (
          <div className="overflow-x-auto [scrollbar-width:thin]">
            <div className="flex min-w-max items-center gap-1.5 pr-1">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onChangeQuery(prompt)}
                  className="inline-flex min-h-[28px] shrink-0 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-medium text-[var(--text-secondary)] transition hover:border-cyan-300/70 hover:text-[var(--text-primary)]"
                  title={prompt}
                >
                  <span className="max-w-[18rem] truncate">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <form onSubmit={onSubmit} className="space-y-1.5">
          <div className="rounded-[0.95rem] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1.5">
            <textarea
              id="chat-composer-input"
              value={query}
              onChange={(event) => onChangeQuery(event.target.value)}
              disabled={isSubmitting}
              aria-label="Chat composer input"
              placeholder={copy.placeholder}
              rows={2}
              className="min-h-[76px] max-h-40 w-full resize-y border-0 bg-transparent px-0 py-1 text-[13px] leading-5 text-[var(--text-primary)] outline-none"
            />
          </div>

          <div className="flex items-center justify-between gap-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="inline-flex items-center gap-1 rounded-full border border-cyan-400/70 bg-slate-900/70 p-[2px]">
                {RESEARCH_MODE_OPTIONS.map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => onChangeResearchMode(mode.id)}
                    disabled={isSubmitting}
                    className={modeButtonClass(selectedResearchMode === mode.id, isSubmitting)}
                    aria-pressed={selectedResearchMode === mode.id}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>

              <div className="inline-flex items-center gap-1 rounded-full border border-violet-400/55 bg-violet-950/35 p-[2px]">
                {RESEARCH_RETRIEVAL_STACK_OPTIONS.map((mode) => {
                  const disabled = isSubmitting || (isFastResearchMode && mode.id === "full");
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => onChangeRetrievalStackMode(mode.id)}
                      disabled={disabled}
                      className={stackButtonClass(selectedRetrievalStackMode === mode.id, disabled)}
                      aria-pressed={selectedRetrievalStackMode === mode.id}
                    >
                      {mode.label}
                    </button>
                  );
                })}
              </div>

              <button
                type="button"
                className="inline-flex min-h-[32px] items-center justify-center rounded-full border border-emerald-400/65 bg-emerald-500/14 px-3.5 text-[10px] font-semibold text-emerald-300 transition"
              >
                {copy.personal}
              </button>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !query.trim()}
              className="inline-flex min-h-[30px] min-w-[54px] items-center justify-center rounded-full border border-cyan-400/75 bg-cyan-700/35 px-3 text-[13px] font-semibold text-cyan-200 transition hover:bg-cyan-700/45 disabled:cursor-not-allowed disabled:opacity-60"
              aria-label={copy.submit}
              title={copy.submit}
            >
              {copy.submit}
            </button>
          </div>
        </form>

        {liveJobId || liveStatusNote || showRawError || notice ? (
          <div className="text-[10px]">
            {liveJobId && !liveStatusNote ? (
              <p className="text-cyan-700 dark:text-cyan-300">
                {copy.liveStatusFallback} ({liveJobId})
              </p>
            ) : null}
            {liveStatusNote ? <p className="text-cyan-700 dark:text-cyan-300">{liveStatusNote}</p> : null}
            {showRawError ? <p className="text-rose-500">{error}</p> : null}
            {!showRawError && notice ? <p className="text-emerald-600 dark:text-emerald-300">{notice}</p> : null}
          </div>
        ) : null}
      </div>
    </footer>
  );
}
