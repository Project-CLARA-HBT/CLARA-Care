import { FormEvent } from "react";
import { ResearchExecutionMode, ResearchRetrievalStackMode } from "@/lib/research";

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
  } = props;

  return (
    <footer className="sticky bottom-0 z-20 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)]/90 p-4 backdrop-blur-md">
      <div className="mx-auto w-full max-w-[72rem] px-1 sm:px-2 lg:px-3">
        <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2 shadow-sm">
          <form onSubmit={onSubmit} className="flex items-end gap-2">
            <button
              type="button"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[var(--text-muted)] transition hover:bg-white/70 hover:text-cyan-700 dark:hover:bg-slate-800/60 dark:hover:text-cyan-300"
              aria-label="Đính kèm"
            >
              <span className="material-symbols-outlined">attach_file</span>
            </button>

            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <textarea
                id="chat-composer-input"
                value={query}
                onChange={(event) => onChangeQuery(event.target.value)}
                disabled={isSubmitting}
                aria-label="Chat composer input"
                placeholder="Nhập câu hỏi chuyên sâu hoặc yêu cầu phân tích mới..."
                rows={1}
                className="min-h-[52px] max-h-36 w-full resize-y rounded-xl border border-transparent bg-transparent px-2 py-3 text-sm text-[var(--text-primary)] outline-none"
              />

              <div className="flex flex-wrap items-center gap-2 pb-1">
                <fieldset className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-white/70 p-1 dark:bg-slate-900/60">
                  <legend className="sr-only">Research mode</legend>
                  {RESEARCH_MODE_OPTIONS.map((mode) => (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => onChangeResearchMode(mode.id)}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-[11px] font-semibold",
                        selectedResearchMode === mode.id
                          ? "bg-cyan-500 text-white"
                          : "text-[var(--text-secondary)]"
                      ].join(" ")}
                    >
                      {mode.label}
                    </button>
                  ))}
                </fieldset>

                <fieldset className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-white/70 p-1 dark:bg-slate-900/60">
                  <legend className="sr-only">Retrieval stack mode</legend>
                  {RESEARCH_RETRIEVAL_STACK_OPTIONS.map((mode) => {
                    const disabled = isSubmitting || (isFastResearchMode && mode.id === "full");
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => onChangeRetrievalStackMode(mode.id)}
                        disabled={disabled}
                        className={[
                          "rounded-full px-3 py-1 text-[11px] font-semibold disabled:opacity-50",
                          selectedRetrievalStackMode === mode.id
                            ? "bg-[var(--text-primary)] text-[var(--bg-canvas)]"
                            : "text-[var(--text-secondary)]"
                        ].join(" ")}
                      >
                        {mode.label}
                      </button>
                    );
                  })}
                </fieldset>
              </div>
            </div>

            <div className="flex items-center gap-2 pr-1">
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl text-[var(--text-muted)] transition hover:bg-white/70 hover:text-cyan-700 dark:hover:bg-slate-800/60 dark:hover:text-cyan-300"
                aria-label="Mic"
              >
                <span className="material-symbols-outlined">mic</span>
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !query.trim()}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--text-primary)] text-[var(--bg-canvas)] transition hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                aria-label="Gửi"
              >
                <span className="material-symbols-outlined">arrow_upward</span>
              </button>
            </div>
          </form>
        </div>

        <div className="mt-3 flex flex-wrap justify-center gap-3 text-[11px] text-[var(--text-muted)]">
          {quickPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onChangeQuery(prompt)}
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 transition hover:bg-white/70 hover:text-cyan-700 dark:hover:bg-slate-800/60 dark:hover:text-cyan-300"
            >
              <span className="material-symbols-outlined text-sm">history</span>
              {prompt}
            </button>
          ))}
        </div>

        <div className="mt-1 min-h-[1.2rem] text-center text-xs">
          {liveJobId || liveStatusNote ? (
            <p className="text-cyan-700 dark:text-cyan-300">
              {liveStatusNote || "Đang xử lý tier2 job..."}
              {liveJobId ? ` (job_id: ${liveJobId})` : ""}
            </p>
          ) : null}
          {error ? <p className="text-rose-500">{error}</p> : null}
          {!error && notice ? <p className="text-emerald-600 dark:text-emerald-300">{notice}</p> : null}
        </div>
      </div>
    </footer>
  );
}
