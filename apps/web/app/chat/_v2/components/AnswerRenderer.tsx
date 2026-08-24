"use client";

import { memo } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { UILanguage } from "@/lib/ui-language";
import type { ResearchResult } from "@/components/research/lib/research-page-types";
import type { ResearchEvidenceReleaseReason } from "@/lib/research";
import { isDegradedAnswer } from "@/app/chat/_v2/lib/chat-format";
import { Badge } from "@/app/chat/_v2/components/primitives";
import {
  citationRegistryAnchorId,
  injectTracedClaimAnchors,
} from "@/lib/research";
import type { UserRole } from "@/lib/auth-store";
import MedicalAnswerCanvas from "@/app/chat/_v2/components/MedicalAnswerCanvas";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { sanitizeAssistantAnswer } from "@/lib/user-facing-text";
import Icon from "@/components/ui/icon";

/**
 * Modernized answer renderer for CLARA Chat with Answer-First Structure:
 * Aligned with Stitch template h_i_clara_active_conversation_refined.
 *
 * 1. Warning alert box: Safety Caveat / Degraded notice / Release boundary
 * 2. Structured answer: Short answer & Markdown clinical content
 * 3. Next Action steps: Management recommendations & Actions
 * 4. Citations tags: Evidence & Verified Badges (Guideline, Alert, Pharmacopeia tags)
 * 5. Evidence synthesis: Evidence ledger & Integrity diagnostics
 */

export type AnswerRendererProps = {
  result: ResearchResult;
  uiLanguage: UILanguage;
  role?: UserRole;
  onSaveNote?: (answerText: string) => void;
};

const RELEASE_REASON_KEYS: Record<
  ResearchEvidenceReleaseReason,
  UITranslationKey
> = {
  no_citations: "chat.answerRenderer.releaseBoundary.reason.noCitations",
  no_retrieved_evidence:
    "chat.answerRenderer.releaseBoundary.reason.noRetrievedEvidence",
  verification_unavailable:
    "chat.answerRenderer.releaseBoundary.reason.verificationUnavailable",
  verification_skipped:
    "chat.answerRenderer.releaseBoundary.reason.verificationSkipped",
  verification_invalid:
    "chat.answerRenderer.releaseBoundary.reason.verificationInvalid",
  unsupported_claims:
    "chat.answerRenderer.releaseBoundary.reason.unsupportedClaims",
  zero_claim_support:
    "chat.answerRenderer.releaseBoundary.reason.zeroClaimSupport",
};

function resolveSourceBadge(
  titleOrSource: string,
  url?: string,
  index?: number,
  language: UILanguage = "vi",
): { tag: string; label: string; colorClass: string } {
  const text = `${titleOrSource || ""} ${url || ""}`.toLowerCase();
  const num = typeof index === "number" ? `[${index + 1}] ` : "";
  if (text.includes("guideline") || text.includes("aha") || text.includes("acc") || text.includes("moh") || text.includes("by tế") || text.includes("statement")) {
    return {
      tag: language === "vi" ? "Hướng dẫn" : "Guideline",
      label: `${num}${language === "vi" ? "Hướng dẫn" : "Guideline"}`,
      colorClass: "bg-blue-900/40 text-blue-300 border-blue-700/50",
    };
  }
  if (text.includes("warning") || text.includes("cảnh báo") || text.includes("safety") || text.includes("fda") || text.includes("dav")) {
    return {
      tag: language === "vi" ? "Cảnh báo" : "Alert",
      label: `${num}${language === "vi" ? "Cảnh báo" : "Alert"}`,
      colorClass: "bg-amber-900/40 text-amber-300 border-amber-700/50",
    };
  }
  if (text.includes("rxnorm") || text.includes("drugbank") || text.includes("lexicomp") || text.includes("dược thư") || text.includes("pharmacopeia")) {
    return {
      tag: language === "vi" ? "Dược thư" : "Pharmacopeia",
      label: `${num}${language === "vi" ? "Dược thư" : "Pharmacopeia"}`,
      colorClass: "bg-emerald-900/40 text-emerald-300 border-emerald-700/50",
    };
  }
  if (text.includes("pubmed") || text.includes("pmc") || text.includes("ncbi") || text.includes("trial") || text.includes("study")) {
    return {
      tag: language === "vi" ? "Nghiên cứu" : "Study",
      label: `${num}${language === "vi" ? "Nghiên cứu" : "Study"}`,
      colorClass: "bg-cyan-900/40 text-cyan-300 border-cyan-700/50",
    };
  }
  return {
    tag: language === "vi" ? "Nguồn tham khảo" : "Reference",
    label: `${num}${language === "vi" ? "Nguồn tham khảo" : "Reference"}`,
    colorClass: "bg-[var(--surface-muted)] text-[var(--text-secondary)] border-[color:var(--shell-border)]",
  };
}

function AnswerRenderer({
  result,
  uiLanguage,
  role = "normal",
  onSaveNote,
}: AnswerRendererProps) {
  const copy = (
    key: UITranslationKey,
    values: Record<string, string | number> = {},
  ) => t(uiLanguage, key, values);
  const degraded = isDegradedAnswer(result);
  const baseAnswer = sanitizeAssistantAnswer(result.answer?.trim() || "");
  const citations = result.tier === "tier2" ? result.citations : [];
  const tracedClaims =
    result.tier === "tier2" ? (result.tracedClaims ?? []) : [];
  const citationRegistry =
    result.tier === "tier2" ? (result.citationRegistry ?? []) : [];
  const evidenceRelease =
    result.tier === "tier2" ? result.evidenceRelease : undefined;
  const presentation = result.tier === "tier2" ? result.presentation : undefined;
  const answer =
    tracedClaims.length && citationRegistry.length
      ? injectTracedClaimAnchors(baseAnswer, tracedClaims, citationRegistry)
      : baseAnswer;
  const clinicalAnswer =
    result.tier === "tier1" ? result.clinicalAnswer : undefined;

  return (
    <div className="space-y-6">
      {/* 1. WARNING ALERT BOX SECTION */}
      {degraded ? (
        <div className="flex items-center gap-2">
          <Badge tone="warn">
            {copy("chat.answerRenderer.degraded")}
          </Badge>
        </div>
      ) : null}

      {evidenceRelease && !evidenceRelease.passed ? (
        <section
          className="rounded-xl border-l-4 border-l-[color:var(--status-warn-border)] border border-[color:var(--status-warn-border)]/40 bg-[var(--status-warn-bg)]/20 p-4 sm:p-5 text-[var(--status-warn-text)]"
          role="status"
          aria-label={copy("chat.answerRenderer.releaseBoundary.aria")}
        >
          <div className="flex items-center gap-2">
            <Icon name="warning" size={18} className="text-[var(--status-warn-text)] shrink-0" />
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              {copy("chat.answerRenderer.releaseBoundary.title")}
            </p>
          </div>
          <p className="mt-1.5 text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
            {copy("chat.answerRenderer.releaseBoundary.description")}
          </p>
          {evidenceRelease.reasons.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5">
              {evidenceRelease.reasons.map((reason) => (
                <li key={reason}>{copy(RELEASE_REASON_KEYS[reason])}</li>
              ))}
            </ul>
          ) : null}
          <div className="mt-3.5">
            <Link
              href="/visits/new"
              className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--surface-panel)] px-3 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--shell-border-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]"
            >
              <Icon name="calendar" size={14} className="text-[var(--text-brand)]" />
              <span>{copy("chat.answerRenderer.releaseBoundary.prepareVisit")}</span>
            </Link>
          </div>
        </section>
      ) : null}

      {presentation?.mode === "professional" ? (
        <section
          className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-2.5"
          aria-label={copy("chat.answerRenderer.presentation.professionalAria")}
        >
          <p className="text-xs font-semibold text-[var(--text-primary)]">
            {copy("chat.answerRenderer.presentation.professionalTitle")}
          </p>
          <p className="mt-0.5 text-xs leading-5 text-[var(--text-muted)]">
            {copy("chat.answerRenderer.presentation.professionalDescription")}
          </p>
        </section>
      ) : null}

      {/* 2. STRUCTURED ANSWER SECTION */}
      <section className="space-y-3">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-brand)]">
          <Icon name="clinical-notes" size={15} />
          <span>{copy("chat.answerRenderer.section.answer")}</span>
        </h3>
        <div className="medical-markdown prose prose-sm max-w-none text-[var(--text-primary)] leading-relaxed prose-headings:text-[var(--text-primary)] prose-headings:font-bold prose-headings:tracking-tight prose-a:text-[var(--text-brand)] prose-a:underline-offset-2 hover:prose-a:underline prose-strong:text-[var(--text-primary)] prose-strong:font-semibold">
          {answer ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              {copy("chat.answerRenderer.emptyAnswer")}
            </p>
          )}
        </div>
      </section>

      {/* 3. NEXT ACTION STEPS & SAFETY CARDS SECTION */}
      {result.tier === "tier2" && result.verificationStatus ? (
        <section
          className="rounded-2xl border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)]/50 p-4 sm:p-5 shadow-xs space-y-3"
          aria-label={uiLanguage === "vi" ? "Thẻ an toàn DrugBank & FIDES" : "DrugBank & FIDES Safety Card"}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2.5">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <Icon name="medication" size={15} />
              </div>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {uiLanguage === "vi" ? "Kiểm tra Dược lý & An toàn FIDES" : "FIDES Clinical Safety & Pharmacology"}
                </h4>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--brand-500)]/60 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)]">
                <Icon name="check" size={11} />
                {result.verificationStatus.verdict ?? (uiLanguage === "vi" ? "ĐÃ KIỂM CHỨNG" : "VERIFIED")}
              </span>
              {result.policyAction ? (
                <Badge tone={result.policyAction === "allow" ? "ok" : "warn"}>
                  {result.policyAction.toUpperCase()}
                </Badge>
              ) : null}
            </div>
          </div>

          {result.verificationStatus.note ? (
            <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
              {result.verificationStatus.note}
            </p>
          ) : null}
        </section>
      ) : null}

      {clinicalAnswer ? (
        <MedicalAnswerCanvas
          answer={clinicalAnswer}
          role={role}
          uiLanguage={uiLanguage}
        />
      ) : (
        <section className="relative overflow-hidden rounded-xl border border-[color:var(--brand-500)]/30 bg-[var(--brand-600)]/5 p-5 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-brand)] mb-2.5">
            <Icon name="emergency" size={16} />
            <span>{copy("chat.answerRenderer.section.nextActions")}</span>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
            {copy("chat.composer.safetyNote")}
          </p>
          <div className="mt-3.5 flex flex-wrap items-center gap-2.5">
            <Link
              href="/visits/new"
              className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3.5 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
            >
              <Icon name="calendar" size={14} />
              <span>{copy("chat.answerRenderer.action.bookDoctor")}</span>
            </Link>
            {onSaveNote && answer ? (
              <button
                type="button"
                onClick={() => onSaveNote(answer)}
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3.5 text-xs font-semibold text-[var(--text-primary)] transition hover:bg-[var(--surface-muted)] active:scale-95"
              >
                <Icon name="clinical-notes" size={14} className="text-[var(--text-brand)]" />
                <span>{copy("chat.answerRenderer.action.saveNote")}</span>
              </button>
            ) : null}
          </div>
        </section>
      )}

      {/* 4. CITATIONS TAGS SECTION */}
      {citationRegistry.length ? (
        <section className="pt-2 border-t border-[color:var(--shell-border)]/50">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-3 flex items-center gap-1.5">
            <Icon name="scan" size={15} className="text-[var(--text-brand)]" />
            <span>{copy("chat.answerRenderer.section.citations")} ({citationRegistry.length})</span>
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {citationRegistry.map((entry, index) => {
              const badge = resolveSourceBadge(entry.sourceType || entry.title || "", entry.url, index, uiLanguage);
              return (
                <div
                  key={`${entry.citationId}-${index}`}
                  id={citationRegistryAnchorId(entry.citationId)}
                  className="scroll-mt-24 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/80 dark:bg-[#181c1f] p-3.5 text-xs transition hover:border-[color:var(--brand-500)]/40 flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span
                        className={`inline-flex items-center justify-center rounded px-2 py-0.5 text-[10px] font-bold border ${badge.colorClass}`}
                      >
                        {badge.label}
                      </span>
                      {entry.sourceType ? (
                        <span className="text-[10px] text-[var(--text-muted)]">
                          {entry.sourceType}
                        </span>
                      ) : null}
                    </div>
                    <h4 className="font-semibold text-[var(--text-primary)] line-clamp-2 leading-snug">
                      {entry.url ? (
                        <a
                          href={entry.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--text-brand)] hover:underline"
                        >
                          {entry.title || entry.studyId || "—"}
                        </a>
                      ) : (
                        entry.title || entry.studyId || "—"
                      )}
                    </h4>
                  </div>
                  {entry.url ? (
                    <a
                      href={entry.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-medium text-[var(--text-brand)] hover:underline"
                    >
                      <span>{copy("chat.answerRenderer.viewFullSource")}</span>
                      <Icon name="arrow-right" size={12} />
                    </a>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {presentation?.citationVisibility === "expanded" && citations.length && !citationRegistry.length ? (
        <section className="pt-2 border-t border-[color:var(--shell-border)]/50">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2 flex items-center gap-1.5">
            <Icon name="scan" size={15} className="text-[var(--text-brand)]" />
            <span>{copy("chat.answerRenderer.presentation.sources")}</span>
          </h3>
          <ol className="space-y-1.5">
            {citations.map((citation, index) => (
              <li
                key={`${citation.sourceId ?? citation.url ?? citation.title}-${index}`}
                className="text-xs leading-relaxed text-[var(--text-secondary)]"
              >
                <span className="font-semibold text-[var(--text-primary)]">[{index + 1}]</span>{" "}
                {citation.url ? (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--text-brand)] underline underline-offset-2"
                  >
                    {citation.title}
                  </a>
                ) : (
                  citation.title
                )}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {citations.length && !citationRegistry.length ? (
        <details className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] dark:bg-[#181c1f] p-3.5">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
            <Icon name="scan" size={15} className="text-[var(--text-brand)]" />
            <span>
              {copy("chat.answerRenderer.references", {
                count: citations.length,
              })}
            </span>
          </summary>
          <div className="mt-3.5 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {citations.map((citation, index) => {
              const badge = resolveSourceBadge(citation.source || citation.title || "", citation.url, index, uiLanguage);
              return (
                <div
                  key={`${citation.title}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)] p-3 text-xs text-[var(--text-secondary)] flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-1.5 mb-1.5">
                      <span
                        className={`inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[9px] font-bold border ${badge.colorClass}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <h4 className="font-medium text-[var(--text-primary)] line-clamp-2 leading-snug">
                      {citation.url ? (
                        <a
                          href={citation.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--text-brand)] hover:underline"
                        >
                          {citation.title || citation.source || citation.url}
                        </a>
                      ) : (
                        citation.title || citation.source || "—"
                      )}
                    </h4>
                  </div>
                  {citation.url ? (
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 text-[11px] font-medium text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                    >
                      <span>{copy("chat.answerRenderer.viewFullSource")}</span>
                      <Icon name="arrow-right" size={12} />
                    </a>
                  ) : null}
                </div>
              );
            })}
          </div>
        </details>
      ) : null}

      {/* 5. EVIDENCE SYNTHESIS SECTION */}
      {result.tier === "tier2" && (role === "researcher" || role === "admin") ? (
        <details className="mt-3 rounded-2xl border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] dark:bg-[#111C29] p-4">
          <summary className="cursor-pointer text-xs sm:text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <Icon name="check" size={16} className="text-[var(--text-brand)]" />
            <span>{copy("chat.answerRenderer.integrity.title")}</span>
          </summary>
          <section aria-label={copy("chat.answerRenderer.integrity.aria")} className="mt-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-xs text-[var(--text-muted)]">
                {copy("chat.answerRenderer.integrity.description")}
              </p>
              {result.policyAction ? (
                <Badge tone={result.policyAction === "allow" ? "ok" : "warn"}>
                  {result.policyAction}
                </Badge>
              ) : null}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <ResearchMetric
                label={copy("chat.answerRenderer.integrity.sources")}
                value={result.citations.length}
              />
              <ResearchMetric
                label={copy("chat.answerRenderer.integrity.tracedClaims")}
                value={result.tracedClaims.length}
              />
              <ResearchMetric
                label={copy("chat.answerRenderer.integrity.deepPasses")}
                value={result.deepPassCount ?? 0}
              />
              <ResearchMetric
                label={copy("chat.answerRenderer.integrity.verification")}
                value={
                  result.verificationStatus?.verdict ??
                  copy("chat.answerRenderer.integrity.notReported")
                }
              />
            </div>
            {result.verificationStatus?.note ? (
              <p className="mt-2 rounded-xl bg-[var(--surface-panel)] px-3 py-2 text-xs leading-5 text-[var(--text-secondary)]">
                {result.verificationStatus.note}
              </p>
            ) : null}
          </section>
        </details>
      ) : null}
    </div>
  );
}

function ResearchMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-semibold">
        {label}
      </p>
      <p className="mt-0.5 truncate text-xs font-bold text-[var(--text-primary)]">
        {value}
      </p>
    </div>
  );
}

/**
 * Memoized: answer rendering parses markdown on every render, so we avoid
 * re-rendering when the owning turn is unchanged.
 */
export default memo(AnswerRenderer);
