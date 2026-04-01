"use client";

import { FormEvent, useMemo, useState } from "react";
import ResearchEmptyState from "@/components/research/research-empty-state";
import ResearchLabNav from "@/components/research/research-lab-nav";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { resolveFlowModeFromResult } from "@/components/research/lib/research-page-helpers";
import { Tier2Result } from "@/components/research/lib/research-page-types";
import PageShell from "@/components/ui/page-shell";
import {
  createResearchConversation,
  normalizeResearchTier2,
  ResearchExecutionMode,
  runResearchTier2
} from "@/lib/research";

export default function ResearchDeepdivePage() {
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "failed">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<Tier2Result | null>(null);
  const [selectedResearchMode, setSelectedResearchMode] = useState<ResearchExecutionMode>("deep");

  const flowMode = useMemo(
    () => (result ? resolveFlowModeFromResult(result) : "idle"),
    [result]
  );

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isRunning) return;

    setError("");
    setStatus("running");
    setIsRunning(true);
    setLastQuery(message);

    try {
      const response = await runResearchTier2(message, { researchMode: selectedResearchMode });
      const normalized = normalizeResearchTier2(response);
      const nextResult: Tier2Result = { tier: "tier2", ...normalized };
      setResult(nextResult);
      setStatus("done");
      setQuery("");

      const persistPayload: Record<string, unknown> = { ...nextResult };
      void createResearchConversation(message, persistPayload).catch(() => undefined);
    } catch (submitError) {
      setStatus("failed");
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Deep research không thực thi được."
      );
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <PageShell
      title="Research Deepdive"
      description="Chạy deep/deep_beta research riêng: nhập query, thực thi, nhận answer và trạng thái tối giản."
    >
      <div className="space-y-4">
        <ResearchLabNav />

        <section className="chrome-panel rounded-[1.5rem] p-5 sm:p-6">
          <form onSubmit={onSubmit} className="space-y-3">
            <label
              htmlFor="deepdive-query"
              className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]"
            >
              Query
            </label>
            <textarea
              id="deepdive-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              disabled={isRunning}
              placeholder="Nhập câu hỏi cần deep research..."
              className="min-h-[132px] w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none ring-sky-500 transition focus:ring-2 disabled:opacity-60"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <fieldset className="inline-flex rounded-full border border-cyan-300/70 bg-cyan-500/10 p-1">
                <legend className="sr-only">Chọn mode deepdive</legend>
                <button
                  type="button"
                  onClick={() => setSelectedResearchMode("deep")}
                  disabled={isRunning}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-semibold transition",
                    selectedResearchMode === "deep"
                      ? "bg-cyan-500 text-white"
                      : "text-cyan-700 dark:text-cyan-200"
                  ].join(" ")}
                >
                  Deep
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedResearchMode("deep_beta")}
                  disabled={isRunning}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-semibold transition",
                    selectedResearchMode === "deep_beta"
                      ? "bg-cyan-500 text-white"
                      : "text-cyan-700 dark:text-cyan-200"
                  ].join(" ")}
                >
                  Deep Beta
                </button>
              </fieldset>
              <button
                type="submit"
                disabled={isRunning || !query.trim()}
                className="rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-60"
              >
                {isRunning ? "Executing..." : "Execute"}
              </button>
            </div>
          </form>
        </section>

        <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              status: {status}
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              mode: {selectedResearchMode === "deep_beta" ? "DEEP BETA" : "DEEP"}
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              flow: {flowMode}
            </span>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 font-medium text-[var(--text-secondary)]">
              citations: {result?.citations.length ?? 0}
            </span>
          </div>
          {lastQuery ? (
            <p className="mt-3 text-sm text-[var(--text-primary)]">
              <span className="font-semibold">Latest query:</span> {lastQuery}
            </p>
          ) : null}
          {error ? (
            <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          ) : null}
        </section>

        <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Answer
          </p>
          <div className="mt-2">
            {result ? (
              <MarkdownAnswer answer={result.answer || "Chưa có nội dung trả lời."} citations={result.citations} />
            ) : (
              <ResearchEmptyState
                className="border-0 bg-transparent p-0"
                title="Chưa có kết quả deep research"
                description="Nhập query và chạy Execute để tạo kết quả chuyên sâu."
              />
            )}
          </div>
        </section>
      </div>
    </PageShell>
  );
}
