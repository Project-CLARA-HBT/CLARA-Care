import { FormEvent, useState } from "react";
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
  personalMode: boolean;
  onTogglePersonalMode: () => void;
  liveJobId: string | null;
  liveStatusNote: string;
  error: string;
  notice: string;
  uiLanguage: UILanguage;
};

const RESEARCH_MODE_OPTIONS: Array<{ id: ResearchExecutionMode; label: Record<UILanguage, string> }> = [
  { id: "fast", label: { vi: "Nhanh", en: "Quick" } },
  { id: "deep", label: { vi: "Tư duy", en: "Reason" } },
  { id: "deep_beta", label: { vi: "Pro", en: "Pro" } },
];

const RESEARCH_RETRIEVAL_STACK_OPTIONS: Array<{ id: ResearchRetrievalStackMode; label: Record<UILanguage, string> }> = [
  { id: "auto", label: { vi: "Tự chọn", en: "Auto" } },
  { id: "full", label: { vi: "Đầy đủ", en: "Full" } },
];

const COMPOSER_COPY: Record<
  UILanguage,
  {
    mode: string;
    stack: string;
    promptTray: string;
    placeholder: string;
    mic: string;
    submit: string;
    personal: string;
    liveStatusFallback: string;
  }
> = {
  vi: {
    mode: "Cách trả lời",
    stack: "Nguồn",
    promptTray: "Gợi ý",
    placeholder: "Nhập câu hỏi, ca bệnh hoặc yêu cầu nghiên cứu...",
    mic: "Ghi âm",
    submit: "Gửi",
    personal: "Cá nhân",
    liveStatusFallback: "Đang xử lý...",
  },
  en: {
    mode: "Mode",
    stack: "Sources",
    promptTray: "Prompts",
    placeholder: "Ask a question, clinical case, or research request...",
    mic: "Voice input",
    submit: "Send",
    personal: "Personal",
    liveStatusFallback: "Working...",
  },
};

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
    personalMode,
    onTogglePersonalMode,
    liveJobId,
    liveStatusNote,
    error,
    notice,
    uiLanguage,
  } = props;

  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [isPromptTrayOpen, setIsPromptTrayOpen] = useState(false);
  const copy = COMPOSER_COPY[uiLanguage];
  const activeModeLabel =
    RESEARCH_MODE_OPTIONS.find((mode) => mode.id === selectedResearchMode)?.label[uiLanguage] ?? "Nhanh";
  const activeStackLabel =
    RESEARCH_RETRIEVAL_STACK_OPTIONS.find((mode) => mode.id === selectedRetrievalStackMode)?.label[uiLanguage] ??
    "Tự chọn";
  const controlsSummary = `${activeModeLabel} · ${activeStackLabel}`;
  const showRawError =
    error &&
    !/(internal server error|upstream request failed|gateway|status code: 5\d\d|^5\d\d\b)/i.test(error);
  const toneButtonClass = (active: boolean, disabled = false) =>
    [
      "inline-flex min-h-[24px] items-center justify-center rounded-full px-2 text-[9px] font-semibold transition",
      disabled
        ? "cursor-not-allowed border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)] opacity-55"
        : active
          ? "border border-cyan-300/70 bg-cyan-500/12 text-cyan-700 dark:text-cyan-300"
          : "border border-transparent text-[var(--text-secondary)] hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
    ].join(" ");

  return (
    <footer className="sticky bottom-0 z-20 border-t border-[color:var(--shell-border)]/60 bg-[var(--bg-canvas)]/92 px-0.5 pb-0.5 pt-0.5 backdrop-blur-xl sm:px-1">
      <div className="mx-auto w-full max-w-none">
        <div className="rounded-[0.65rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]/98 px-1.5 py-1 shadow-[0_12px_24px_-24px_rgba(15,23,42,0.35)]">
          <form onSubmit={onSubmit} className="space-y-0.5">
            <div className="flex items-center justify-between gap-1.5">
              <div className="flex min-w-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => setIsControlsOpen((current) => !current)}
                  className={[
                    "inline-flex min-h-[24px] shrink-0 items-center gap-1 rounded-full border px-2 text-[9px] font-semibold transition",
                    isControlsOpen
                      ? "border-cyan-300/70 bg-cyan-500/12 text-cyan-700 dark:text-cyan-300"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                >
                  <span className="material-symbols-outlined text-[13px]">tune</span>
                  <span className="truncate">{controlsSummary}</span>
                </button>

                {quickPrompts.length ? (
                  <button
                    type="button"
                    onClick={() => setIsPromptTrayOpen((current) => !current)}
                    className={[
                      "inline-flex min-h-[24px] shrink-0 items-center gap-1 rounded-full border px-2 text-[9px] font-semibold transition",
                      isPromptTrayOpen
                        ? "border-cyan-300/70 bg-cyan-500/12 text-cyan-700 dark:text-cyan-300"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined text-[12px]">history</span>
                    {copy.promptTray}
                  </button>
                ) : null}
              </div>

              {liveJobId || liveStatusNote ? (
                <span className="inline-flex min-h-[24px] max-w-[12rem] shrink-0 items-center rounded-full border border-cyan-300/55 bg-cyan-500/10 px-2 text-[8px] font-medium text-cyan-700 dark:text-cyan-300">
                  <span className="truncate">{liveStatusNote || copy.liveStatusFallback}</span>
                </span>
              ) : null}
            </div>

            {isControlsOpen ? (
              <div className="space-y-1 rounded-[0.7rem] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/86 px-1.5 py-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[8px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {copy.mode}
                  </span>
                  <div className="inline-flex flex-wrap items-center gap-1 rounded-full bg-[var(--surface-panel)] p-0.5">
                    {RESEARCH_MODE_OPTIONS.map((mode) => (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => onChangeResearchMode(mode.id)}
                        disabled={isSubmitting}
                        className={toneButtonClass(selectedResearchMode === mode.id, isSubmitting)}
                        aria-pressed={selectedResearchMode === mode.id}
                      >
                        {mode.label[uiLanguage]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[8px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {copy.stack}
                  </span>
                  <div className="inline-flex flex-wrap items-center gap-1 rounded-full bg-[var(--surface-panel)] p-0.5">
                    {RESEARCH_RETRIEVAL_STACK_OPTIONS.map((mode) => {
                      const disabled = isSubmitting || (isFastResearchMode && mode.id === "full");
                      return (
                        <button
                          key={mode.id}
                          type="button"
                          onClick={() => onChangeRetrievalStackMode(mode.id)}
                          disabled={disabled}
                          className={toneButtonClass(selectedRetrievalStackMode === mode.id, disabled)}
                          aria-pressed={selectedRetrievalStackMode === mode.id}
                        >
                          {mode.label[uiLanguage]}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={onTogglePersonalMode}
                  className={toneButtonClass(personalMode, isSubmitting)}
                  aria-pressed={personalMode}
                  disabled={isSubmitting}
                >
                  {copy.personal}
                </button>
              </div>
            ) : null}

            <div className="flex items-end gap-1">
              <div className="flex min-w-0 flex-1 flex-col rounded-[0.7rem] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5">
                <textarea
                  id="chat-composer-input"
                  value={query}
                  onChange={(event) => onChangeQuery(event.target.value)}
                  disabled={isSubmitting}
                  aria-label="Chat composer input"
                  placeholder={copy.placeholder}
                  rows={1}
                  className="min-h-[34px] max-h-24 w-full resize-y border-0 bg-transparent px-0 py-1 text-[13px] leading-5 text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-[0.7rem] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)] transition hover:border-cyan-300/70 hover:text-cyan-700 dark:hover:text-cyan-300"
                  aria-label={copy.mic}
                  title={copy.mic}
                >
                  <span className="material-symbols-outlined text-[16px]">mic</span>
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !query.trim()}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-[0.7rem] bg-[var(--text-primary)] text-[var(--bg-canvas)] transition hover:scale-[1.02] active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                  aria-label={copy.submit}
                  title={copy.submit}
                >
                  <span className="material-symbols-outlined text-[16px]">arrow_upward</span>
                </button>
              </div>
            </div>
          </form>
        </div>

        {isPromptTrayOpen ? (
          <div className="mt-1 overflow-x-auto pb-0.5 text-[8px] text-[var(--text-muted)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <div className="flex gap-1">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onChangeQuery(prompt)}
                  className="inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-[9px] font-medium text-[var(--text-secondary)] transition hover:border-cyan-300/70 hover:text-[var(--text-primary)]"
                  title={prompt}
                >
                  <span className="max-w-[18rem] truncate">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {liveJobId || liveStatusNote || showRawError || notice ? (
          <div className="mt-0.5 text-[10px]">
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
