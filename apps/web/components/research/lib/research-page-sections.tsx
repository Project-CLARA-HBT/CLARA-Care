"use client";

import { ChangeEvent, FormEvent, RefObject } from "react";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { ResearchResult } from "@/components/research/lib/research-page-types";
import { t } from "@/lib/i18n/catalog";
import {
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
  ResearchTier,
  Tier2Step
} from "@/lib/research";
import { useUILanguage } from "@/lib/use-ui-language";

function researchModeLabel(language: Parameters<typeof t>[0], mode: ResearchExecutionMode): string {
  if (mode === "fast") return t(language, "research.workspace.mode.fast");
  if (mode === "deep") return t(language, "research.workspace.mode.deep");
  return t(language, "research.workspace.mode.pro");
}

function retrievalStackLabel(language: Parameters<typeof t>[0], mode: ResearchRetrievalStackMode): string {
  return mode === "full"
    ? t(language, "research.workspace.retrieval.full")
    : t(language, "research.workspace.retrieval.auto");
}

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
  const language = useUILanguage();

  return (
    <section className="relative overflow-hidden rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--text-brand)]">
            {t(language, "research.workspace.header.eyebrow")}
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
            {t(language, "research.workspace.header.title")}
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {t(language, "research.workspace.header.description")}
          </p>
        </div>
        <div className="space-y-2 text-right">
          <span className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
            {t(language, "research.workspace.header.role", { role: roleLabel })}
          </span>
          <p className="text-xs text-[var(--text-muted)]">
            {t(language, "research.workspace.header.sourcesAndFiles", {
              sources: selectedSourceCount,
              files: uploadedFileCount
            })}
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
  selectedRetrievalStackMode: ResearchRetrievalStackMode;
  onSelectRetrievalStackMode: (mode: ResearchRetrievalStackMode) => void;

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
  selectedRetrievalStackMode,
  onSelectRetrievalStackMode,
  lastQuery,
  result,
  showDebugHints,
  evidenceSteps
}: ResearchMainCardProps) {
  const language = useUILanguage();
  const isFastResearchMode = selectedResearchMode === "fast";
  const onModeChange = (mode: ResearchExecutionMode) => {
    onSelectResearchMode(mode);
    if (mode === "fast" && selectedRetrievalStackMode !== "auto") {
      onSelectRetrievalStackMode("auto");
    }
  };

  return (
    <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 lg:p-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 sm:p-4">
          <label htmlFor="research-query" className="text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            {t(language, "research.workspace.composer.label")}
          </label>
          <textarea
            id="research-query"
            className="mt-2 min-h-[140px] w-full resize-none border-0 bg-transparent p-0 text-sm leading-7 text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-0"
            placeholder={t(language, "research.workspace.composer.placeholder")}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            disabled={isSubmitting}
          />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[color:var(--shell-border)] pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isSubmitting}
                className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-brand-soft)] hover:text-[var(--text-primary)] disabled:opacity-60"
              >
                {isUploading
                  ? t(language, "research.workspace.composer.uploading")
                  : t(language, "research.workspace.composer.attach")}
              </button>

              <fieldset className="inline-flex rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-1">
                <legend className="sr-only">{t(language, "research.workspace.tier.legend")}</legend>
                <button
                  type="button"
                  onClick={() => onSelectTier("tier1")}
                  disabled={isSubmitting}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                    selectedTier === "tier1"
                      ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                      : "text-[var(--text-secondary)]"
                  ].join(" ")}
                >
                  {t(language, "research.workspace.tier.fast")}
                </button>
                <button
                  type="button"
                  onClick={() => onSelectTier("tier2")}
                  disabled={isSubmitting}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                    selectedTier === "tier2"
                      ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                      : "text-[var(--text-secondary)]"
                  ].join(" ")}
                >
                  {t(language, "research.workspace.tier.deep")}
                </button>
              </fieldset>

              {selectedTier === "tier2" ? (
                <>
                  <fieldset className="inline-flex rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-1">
                    <legend className="sr-only">{t(language, "research.workspace.mode.legend")}</legend>
                    <button
                      type="button"
                      onClick={() => onModeChange("fast")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                        selectedResearchMode === "fast"
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : "text-[var(--text-brand)]"
                      ].join(" ")}
                    >
                      {t(language, "research.workspace.mode.fast")}
                    </button>
                    <button
                      type="button"
                      onClick={() => onModeChange("deep")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                        selectedResearchMode === "deep"
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : "text-[var(--text-brand)]"
                      ].join(" ")}
                    >
                      {t(language, "research.workspace.mode.deep")}
                    </button>
                    <button
                      type="button"
                      onClick={() => onModeChange("deep_beta")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                        selectedResearchMode === "deep_beta"
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : "text-[var(--text-brand)]"
                      ].join(" ")}
                    >
                      {t(language, "research.workspace.mode.pro")}
                    </button>
                  </fieldset>

                  <fieldset className="inline-flex rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-1">
                    <legend className="sr-only">{t(language, "research.workspace.retrieval.legend")}</legend>
                    <button
                      type="button"
                      onClick={() => onSelectRetrievalStackMode("auto")}
                      disabled={isSubmitting}
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                        selectedRetrievalStackMode === "auto"
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : "text-[var(--text-brand)]"
                      ].join(" ")}
                    >
                      {t(language, "research.workspace.retrieval.auto")}
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectRetrievalStackMode("full")}
                      disabled={isSubmitting || isFastResearchMode}
                      title={
                        isFastResearchMode
                          ? t(language, "research.workspace.retrieval.fastModeTitle")
                          : undefined
                      }
                      className={[
                        "rounded-full px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                        selectedRetrievalStackMode === "full"
                          ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                          : "text-[var(--text-brand)]"
                      ].join(" ")}
                    >
                      {t(language, "research.workspace.retrieval.full")}
                    </button>
                  </fieldset>

                  {isFastResearchMode ? (
                    <p className="text-xs text-[var(--text-brand)]">
                      {t(language, "research.workspace.retrieval.fastModeHint")}
                    </p>
                  ) : null}
                </>
              ) : null}
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !query.trim()}
              className="rounded-lg bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] disabled:opacity-60"
            >
              {isSubmitting
                ? t(language, "research.workspace.action.submitting")
                : t(language, "research.workspace.action.submit")}
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
          <article className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              {t(language, "research.workspace.lastQuestion")}
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-[var(--text-primary)]">{lastQuery}</p>
          </article>
        ) : null}

        {isSubmitting ? (
          <article className="rounded-[14px] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm text-[var(--status-ok-text)]">
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--brand-primary)]" />
              {selectedTier === "tier2"
                ? t(language, "research.workspace.processing.deep", {
                    mode: researchModeLabel(language, selectedResearchMode),
                    retrieval: retrievalStackLabel(language, selectedRetrievalStackMode)
                  })
                : t(language, "research.workspace.processing.fast")}
            </span>
          </article>
        ) : null}

        {result?.tier === "tier1" ? (
          <article className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-brand)]">
              {t(language, "research.workspace.answer.fast")}
            </p>
            <div className="mt-2">
              <MarkdownAnswer
                answer={result.answer}
                citations={[]}
                showInlineCitations={false}
                enableMermaid={false}
                stripReferenceSection={true}
                stripSafetyMatrixSection={false}
                stripMermaidBlocks={true}
                stripChartSpecBlocks={true}
                uiLanguage={language}
              />
            </div>
          </article>
        ) : null}

        {result?.tier === "tier2" ? (
          <article className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-brand)]">
                {t(language, "research.workspace.answer.deep")}
              </p>
              {result.policyAction ? (
                <span
                  className={[
                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                    result.policyAction === "warn"
                      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                      : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                  ].join(" ")}
                >
                  {result.policyAction === "warn"
                    ? t(language, "research.workspace.policy.warn")
                    : t(language, "research.workspace.policy.reference")}
                </span>
              ) : null}
              {typeof result.fallbackUsed === "boolean" ? (
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
                  {result.fallbackUsed
                    ? t(language, "research.workspace.fallback.limited")
                    : t(language, "research.workspace.fallback.compared")}
                </span>
              ) : null}
            </div>

            <div className="mt-2">
              <MarkdownAnswer
                answer={result.answer || t(language, "research.workspace.answer.empty")}
                citations={result.citations}
                showInlineCitations={false}
                enableMermaid={false}
                stripReferenceSection={true}
                stripSafetyMatrixSection={false}
                stripMermaidBlocks={true}
                stripChartSpecBlocks={true}
                uiLanguage={language}
              />
            </div>

            {result.citations.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {result.citations.map((citation, index) => (
                  <a
                    key={`answer-citation-${index + 1}`}
                    href={citation.url || `#citation-${index + 1}`}
                    target={citation.url ? "_blank" : undefined}
                    rel={citation.url ? "noreferrer" : undefined}
                    className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2.5 py-1 text-[11px] font-semibold text-[var(--status-ok-text)] transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-brand-soft)]"
                  >
                    [{index + 1}] {citation.source ?? citation.title}
                  </a>
                ))}
              </div>
            ) : null}

            {result.verificationStatus ? (
              <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                <p className="font-semibold">
                  {result.verificationStatus.verdict === "pass"
                    ? t(language, "research.workspace.verification.pass")
                    : t(language, "research.workspace.verification.needsReview")}
                  {typeof result.verificationStatus.evidenceCount === "number"
                    ? ` | ${t(language, "research.workspace.verification.evidenceCount", {
                        count: result.verificationStatus.evidenceCount
                      })}`
                    : ""}
                </p>
                {result.verificationStatus.note ? (
                  <p className="mt-1 text-[var(--text-secondary)]">{result.verificationStatus.note}</p>
                ) : null}
              </div>
            ) : null}
          </article>
        ) : null}

        {showDebugHints && result?.tier === "tier1" ? (
          <section className="rounded-[14px] border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              {t(language, "research.workspace.debug.title")}
            </p>
            <div className="mt-2 grid gap-1 text-sm text-[var(--text-secondary)]">
              <p>{t(language, "research.workspace.debug.role", { value: result.debug?.role ?? t(language, "research.workspace.debug.notAvailable") })}</p>
              <p>{t(language, "research.workspace.debug.intent", { value: result.debug?.intent ?? t(language, "research.workspace.debug.notAvailable") })}</p>
              <p>{t(language, "research.workspace.debug.confidence", { value: result.debug?.confidence ?? t(language, "research.workspace.debug.notAvailable") })}</p>
              <p>{t(language, "research.workspace.debug.model", { value: result.debug?.model_used ?? t(language, "research.workspace.debug.notAvailable") })}</p>
            </div>
          </section>
        ) : null}

        {result?.tier === "tier2" && evidenceSteps.length ? (
          <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
              {t(language, "research.workspace.analysisSteps")}
            </p>
            <ol className="mt-3 space-y-2">
              {evidenceSteps.map((step, index) => (
                <li key={`${step.title}-${index}`} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{index + 1}. {step.title}</p>
                  {step.detail ? <p className="mt-1 text-xs text-[var(--text-secondary)]">{step.detail}</p> : null}
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </section>
  );
}
