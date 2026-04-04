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
    <div className="sticky bottom-0 z-20 -mx-4 border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)]/90 px-4 pb-2 pt-3 backdrop-blur-xl sm:-mx-5 sm:px-5">
      <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onChangeQuery(prompt)}
            className="inline-flex min-h-[32px] shrink-0 items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-[11px] font-medium text-[var(--text-secondary)] transition hover:border-cyan-300/70 hover:text-cyan-700 dark:hover:text-cyan-300"
          >
            {prompt}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} className="space-y-2.5">
        <textarea
          value={query}
          onChange={(event) => onChangeQuery(event.target.value)}
          disabled={isSubmitting}
          placeholder="Hỏi CLARA bất cứ điều gì về an toàn thuốc, DDI, guideline..."
          className="min-h-[102px] w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm leading-7 text-[var(--text-primary)] outline-none transition focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-200/40 dark:focus:ring-cyan-900/40"
        />

        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap gap-2.5">
            <fieldset className="inline-flex rounded-full border border-cyan-300/70 bg-cyan-500/10 p-1">
              <legend className="sr-only">Research mode</legend>
              {RESEARCH_MODE_OPTIONS.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => onChangeResearchMode(mode.id)}
                  disabled={isSubmitting}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-semibold",
                    selectedResearchMode === mode.id
                      ? "bg-cyan-500 text-white"
                      : "text-cyan-800 dark:text-cyan-200",
                  ].join(" ")}
                >
                  {mode.label}
                </button>
              ))}
            </fieldset>

            <fieldset className="inline-flex rounded-full border border-violet-300/70 bg-violet-500/10 p-1">
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
                      "rounded-full px-3 py-1 text-xs font-semibold disabled:opacity-50",
                      selectedRetrievalStackMode === mode.id
                        ? "bg-violet-500 text-white"
                        : "text-violet-800 dark:text-violet-200",
                    ].join(" ")}
                  >
                    {mode.label}
                  </button>
                );
              })}
            </fieldset>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !query.trim()}
            className="inline-flex min-h-[42px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white shadow-[0_10px_24px_-16px_rgba(6,182,212,0.75)] disabled:opacity-60"
          >
            {isSubmitting ? "Đang xử lý..." : "Gửi"}
          </button>
        </div>
      </form>

      <div className="mt-2 min-h-[1.2rem] text-xs">
        {liveJobId || liveStatusNote ? (
          <p className="text-cyan-700 dark:text-cyan-300">
            {liveStatusNote || "Đang xử lý tier2 job..."}
            {liveJobId ? ` (job_id: ${liveJobId})` : ""}
          </p>
        ) : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
        {!error && notice ? <p className="text-emerald-700 dark:text-emerald-300">{notice}</p> : null}
      </div>
    </div>
  );
}
