import { ChangeEvent, FormEvent, RefObject } from "react";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { ResearchResult } from "@/components/research/lib/research-page-types";
import { ResearchExecutionMode, ResearchTier, Tier2Step } from "@/lib/research";

type ResearchWorkspaceHeaderProps = {
  roleLabel: string;
  selectedSourceCount: number;
  uploadedFileCount: number;
};

export function ResearchWorkspaceHeader({
  roleLabel,
  selectedSourceCount,
  uploadedFileCount
}: ResearchWorkspaceHeaderProps) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-slate-200/80 bg-gradient-to-br from-white via-slate-50/70 to-cyan-50/45 p-4 shadow-sm dark:border-slate-700 dark:from-slate-900/90 dark:via-slate-900/75 dark:to-cyan-950/35 sm:p-5">
      <div className="pointer-events-none absolute -right-8 -top-8 h-36 w-36 rounded-full bg-sky-200/55 blur-2xl dark:bg-sky-800/35" />
      <div className="pointer-events-none absolute -bottom-12 -left-6 h-32 w-40 rounded-full bg-cyan-100/60 blur-2xl dark:bg-cyan-900/25" />
      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700 dark:text-sky-300">CLARA Research Workspace</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Chatbot y tế với luồng xử lý minh bạch</h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Bố cục tách rõ thread, composer, evidence và timeline để theo dõi quality của câu trả lời theo thời gian thực.
          </p>
        </div>
        <div className="space-y-2 text-right">
          <span className="inline-flex rounded-full border border-slate-300 bg-white/90 px-3 py-1 text-xs font-medium text-slate-700 dark:border-slate-600 dark:bg-slate-900/80 dark:text-slate-200">
            Vai trò: {roleLabel}
          </span>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Sources: {selectedSourceCount} · Files: {uploadedFileCount}
          </p>
        </div>
      </div>
    </section>
  );
}

type ResearchMainCardProps = {
  query: string;
  selectedTier: ResearchTier;
  isSubmitting: boolean;
  isUploading: boolean;
  fileInputRef: RefObject<HTMLInputElement>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUploadInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onQueryChange: (value: string) => void;
  onSelectTier: (tier: ResearchTier) => void;
  selectedResearchMode: ResearchExecutionMode;
  onSelectResearchMode: (mode: ResearchExecutionMode) => void;

  lastQuery: string;
  result: ResearchResult | null;
  showDebugHints: boolean;
  evidenceSteps: Tier2Step[];
};

export function ResearchMainCard({
  query,
  selectedTier,
  isSubmitting,
  isUploading,
  fileInputRef,
  onSubmit,
  onUploadInputChange,
  onQueryChange,
  onSelectTier,
  selectedResearchMode,
  onSelectResearchMode,
  lastQuery,
  result,
  showDebugHints,
  evidenceSteps
}: ResearchMainCardProps) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85 sm:p-5 lg:p-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/90 p-3 dark:border-slate-700 dark:bg-slate-800/70 sm:p-4">
          <label htmlFor="research-query" className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
            Composer
          </label>
          <textarea
            id="research-query"
            className="mt-2 min-h-[140px] w-full resize-none border-0 bg-transparent p-0 text-sm leading-7 text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-0 dark:text-slate-100 dark:placeholder:text-slate-400"
            placeholder="Hỏi ngay một câu y tế bạn cần làm rõ..."
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            disabled={isSubmitting}
          />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-3 dark:border-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isSubmitting}
                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                {isUploading ? "Đang upload..." : "Đính kèm"}
              </button>

              <fieldset className="inline-flex rounded-full border border-slate-300 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
                <legend className="sr-only">Chọn chế độ trả lời</legend>
                <button
                  type="button"
                  onClick={() => onSelectTier("tier1")}
                  disabled={isSubmitting}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                    selectedTier === "tier1"
                      ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                      : "text-slate-600 dark:text-slate-300"
                  ].join(" ")}
                >
                  Nhanh
                </button>
                <button
                  type="button"
                  onClick={() => onSelectTier("tier2")}
                  disabled={isSubmitting}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                    selectedTier === "tier2"
                      ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                      : "text-slate-600 dark:text-slate-300"
                  ].join(" ")}
                >
                  Chuyên sâu
                </button>
              </fieldset>

              {selectedTier === "tier2" ? (
                <fieldset className="inline-flex rounded-full border border-sky-300 bg-sky-50 p-1 dark:border-sky-700 dark:bg-sky-950/30">
                  <legend className="sr-only">Chọn mức research</legend>
                  <button
                    type="button"
                    onClick={() => onSelectResearchMode("fast")}
                    disabled={isSubmitting}
                    className={[
                      "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                      selectedResearchMode === "fast"
                        ? "bg-sky-700 text-white dark:bg-sky-300 dark:text-slate-900"
                        : "text-sky-700 dark:text-sky-300"
                    ].join(" ")}
                  >
                    Fast research
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectResearchMode("deep")}
                    disabled={isSubmitting}
                    className={[
                      "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                      selectedResearchMode === "deep"
                        ? "bg-sky-700 text-white dark:bg-sky-300 dark:text-slate-900"
                        : "text-sky-700 dark:text-sky-300"
                    ].join(" ")}
                  >
                    Deep research
                  </button>
                </fieldset>
              ) : null}
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !query.trim()}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {isSubmitting ? "Đang xử lý..." : "Gửi"}
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.txt,image/*"
            className="hidden"
            onChange={onUploadInputChange}
          />
        </div>
      </form>

      <div className="mt-4 space-y-3">
        {lastQuery ? (
          <article className="rounded-3xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Câu hỏi</p>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">{lastQuery}</p>
          </article>
        ) : null}

        {isSubmitting ? (
          <article className="rounded-3xl border border-sky-200 bg-sky-50/70 px-4 py-3 text-sm text-sky-800 dark:border-sky-700 dark:bg-sky-950/30 dark:text-sky-200">
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-sky-500" />
              {selectedTier === "tier2"
                ? `Server đang xử lý research mode: ${selectedResearchMode.toUpperCase()}. Timeline sẽ cập nhật theo flow thật từ backend.`
                : "CLARA đang tổng hợp trả lời nhanh..."}
            </span>
          </article>
        ) : null}

        {result?.tier === "tier1" ? (
          <article className="rounded-3xl border border-slate-200 bg-white px-5 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">Trả lời nhanh</p>
            <div className="mt-2">
              <MarkdownAnswer answer={result.answer} citations={[]} />
            </div>
          </article>
        ) : null}

        {result?.tier === "tier2" ? (
          <article className="rounded-3xl border border-slate-200 bg-white px-5 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">Trả lời chuyên sâu</p>
              {result.policyAction ? (
                <span
                  className={[
                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                    result.policyAction === "warn"
                      ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
                      : "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                  ].join(" ")}
                >
                  {result.policyAction === "warn" ? "Policy: Warn" : "Policy: Allow"}
                </span>
              ) : null}
              {typeof result.fallbackUsed === "boolean" ? (
                <span className="rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {result.fallbackUsed ? "Fallback mode" : "RAG mode"}
                </span>
              ) : null}
            </div>

            <div className="mt-2">
              <MarkdownAnswer answer={result.answer || "Chưa có nội dung."} citations={result.citations} />
            </div>

            {result.citations.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {result.citations.map((citation, index) => (
                  <a
                    key={`answer-citation-${index + 1}`}
                    href={citation.url || `#citation-${index + 1}`}
                    target={citation.url ? "_blank" : undefined}
                    rel={citation.url ? "noreferrer" : undefined}
                    className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-100 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-300 dark:hover:border-sky-600 dark:hover:bg-sky-900/40"
                  >
                    [{index + 1}] {citation.source ?? citation.title}
                  </a>
                ))}
              </div>
            ) : null}

            {result.verificationStatus ? (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200">
                <p className="font-semibold">
                  FIDES-lite: {result.verificationStatus.verdict ?? "n/a"} | confidence:{" "}
                  {typeof result.verificationStatus.confidence === "number"
                    ? result.verificationStatus.confidence.toFixed(2)
                    : "n/a"}
                  {result.verificationStatus.severity ? ` | severity: ${result.verificationStatus.severity}` : ""}
                </p>
                {result.verificationStatus.note ? (
                  <p className="mt-1 text-slate-600 dark:text-slate-300">{result.verificationStatus.note}</p>
                ) : null}
              </div>
            ) : null}
          </article>
        ) : null}

        {showDebugHints && result?.tier === "tier1" ? (
          <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-4 dark:border-slate-600 dark:bg-slate-900/85">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Intent Debug</p>
            <div className="mt-2 grid gap-1 text-sm text-slate-700 dark:text-slate-300">
              <p>role: {result.debug?.role ?? "N/A"}</p>
              <p>intent: {result.debug?.intent ?? "N/A"}</p>
              <p>confidence: {result.debug?.confidence ?? "N/A"}</p>
              <p>model: {result.debug?.model_used ?? "N/A"}</p>
            </div>
          </section>
        ) : null}

        {result?.tier === "tier2" && evidenceSteps.length ? (
          <section className="rounded-3xl border border-slate-200 bg-white/90 p-4 dark:border-slate-700 dark:bg-slate-900/85">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">Analysis Steps</p>
            <ol className="mt-3 space-y-2">
              {evidenceSteps.map((step, index) => (
                <li key={`${step.title}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/75">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{index + 1}. {step.title}</p>
                  {step.detail ? <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{step.detail}</p> : null}
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </section>
  );
}
