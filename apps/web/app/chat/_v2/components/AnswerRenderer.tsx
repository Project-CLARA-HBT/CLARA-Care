"use client";

import { memo } from "react";
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

/**
 * Typographic answer renderer for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Renders the answer markdown (GFM tables, lists, links) with readable
 * hierarchy (Requirement 2.2) and a clear "degraded" badge when the run fell
 * back to local synthesis (Requirement 3.4; design Property P5). Citations are
 * surfaced compactly beneath the answer.
 *
 * When the tier2 result carries claim-to-study traceability (`tracedClaims`)
 * and a `citationRegistry`, inline sentence-level anchors are injected after
 * each matched claim and resolve into the citation appendix
 * (clara-research Requirement 11.3, 11.4). Absent/empty preserves legacy
 * rendering.
 */

export type AnswerRendererProps = {
  result: ResearchResult;
  uiLanguage: UILanguage;
  role?: UserRole;
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

function AnswerRenderer({
  result,
  uiLanguage,
  role = "normal",
}: AnswerRendererProps) {
  const copy = (
    key: UITranslationKey,
    values: Record<string, string | number> = {},
  ) => t(uiLanguage, key, values);
  const degraded = isDegradedAnswer(result);
  const baseAnswer = result.answer?.trim() || "";
  const citations = result.tier === "tier2" ? result.citations : [];
  const tracedClaims =
    result.tier === "tier2" ? (result.tracedClaims ?? []) : [];
  const citationRegistry =
    result.tier === "tier2" ? (result.citationRegistry ?? []) : [];
  const evidenceRelease =
    result.tier === "tier2" ? result.evidenceRelease : undefined;
  const answer =
    tracedClaims.length && citationRegistry.length
      ? injectTracedClaimAnchors(baseAnswer, tracedClaims, citationRegistry)
      : baseAnswer;
  const clinicalAnswer =
    result.tier === "tier1" ? result.clinicalAnswer : undefined;

  return (
    <div className="space-y-2">
      {degraded ? (
        <Badge tone="warn">
          {copy("chat.answerRenderer.degraded")}
        </Badge>
      ) : null}

      {evidenceRelease && !evidenceRelease.passed ? (
        <section
          className="rounded-2xl border border-amber-300/60 bg-amber-50/85 p-3 text-amber-950 dark:border-amber-700/50 dark:bg-amber-950/35 dark:text-amber-100"
          role="status"
          aria-label={copy("chat.answerRenderer.releaseBoundary.aria")}
        >
          <p className="text-sm font-semibold">
            {copy("chat.answerRenderer.releaseBoundary.title")}
          </p>
          <p className="mt-1 text-xs leading-5">
            {copy("chat.answerRenderer.releaseBoundary.description")}
          </p>
          {evidenceRelease.reasons.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5">
              {evidenceRelease.reasons.map((reason) => (
                <li key={reason}>{copy(RELEASE_REASON_KEYS[reason])}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <div className="medical-markdown prose prose-sm max-w-none text-[var(--text-primary)] prose-headings:text-[var(--text-primary)] prose-a:text-[var(--text-brand)] prose-strong:text-[var(--text-primary)]">
        {answer ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            {copy("chat.answerRenderer.emptyAnswer")}
          </p>
        )}
      </div>

      {clinicalAnswer ? (
        <MedicalAnswerCanvas
          answer={clinicalAnswer}
          role={role}
          uiLanguage={uiLanguage}
        />
      ) : null}

      {result.tier === "tier2" ? (
        <section
          className="mt-4 rounded-2xl border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] p-3"
          aria-label={copy("chat.answerRenderer.integrity.aria")}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-[var(--text-brand)]">
                {copy("chat.answerRenderer.integrity.title")}
              </p>
              <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                {copy("chat.answerRenderer.integrity.description")}
              </p>
            </div>
            {result.policyAction ? (
              <Badge
                tone={result.policyAction === "allow" ? "ok" : "warn"}
              >
                {result.policyAction}
              </Badge>
            ) : null}
          </div>
          <div className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
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
      ) : null}

      {citationRegistry.length ? (
        <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {copy("chat.answerRenderer.citationRegistry")}
          </h3>
          <ol className="mt-2 space-y-1.5">
            {citationRegistry.map((entry, index) => {
              const meta = [
                entry.sourceType,
                typeof entry.trustTier === "number" &&
                Number.isFinite(entry.trustTier)
                  ? copy("chat.answerRenderer.trustTier", {
                      tier: entry.trustTier,
                    })
                  : null,
                entry.publishedAt,
              ].filter(Boolean);
              return (
                <li
                  key={`${entry.citationId}-${index}`}
                  id={citationRegistryAnchorId(entry.citationId)}
                  className="scroll-mt-24 text-[12px] leading-5 text-[var(--text-secondary)]"
                >
                  <span className="font-semibold text-[var(--text-primary)]">
                    [{index + 1}]
                  </span>{" "}
                  {entry.url ? (
                    <a
                      href={entry.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--text-brand)] underline-offset-2 hover:underline"
                    >
                      {entry.title || entry.studyId || entry.url}
                    </a>
                  ) : (
                    <span>{entry.title || entry.studyId || "—"}</span>
                  )}
                  {entry.studyId && entry.title ? (
                    <span className="font-mono text-[var(--text-muted)]">
                      {" "}
                      · {entry.studyId}
                    </span>
                  ) : null}
                  {meta.length ? (
                    <span className="text-[var(--text-muted)]">
                      {" "}
                      · {meta.join(" · ")}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      {citations.length ? (
        <details className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {copy("chat.answerRenderer.references", {
              count: citations.length,
            })}
          </summary>
          <ol className="mt-2 space-y-1.5">
            {citations.map((citation, index) => (
              <li
                key={`${citation.title}-${index}`}
                className="text-[12px] leading-5 text-[var(--text-secondary)]"
              >
                <span className="font-semibold text-[var(--text-primary)]">
                  [{index + 1}]
                </span>{" "}
                {citation.url ? (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--text-brand)] underline-offset-2 hover:underline"
                  >
                    {citation.title || citation.source || citation.url}
                  </a>
                ) : (
                  <span>{citation.title || citation.source || "—"}</span>
                )}
                {citation.source && citation.title ? (
                  <span className="text-[var(--text-muted)]">
                    {" "}
                    · {citation.source}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
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
      <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 truncate text-xs font-semibold text-[var(--text-primary)]">
        {value}
      </p>
    </div>
  );
}

/**
 * Memoized: answer rendering parses markdown (and optionally injects traced
 * claim anchors) on every render, so we avoid re-rendering when the owning turn
 * is unchanged (Requirement 7.2, Property P9). `result` is a stable reference
 * per turn, so referential equality is the correct bailout signal.
 */
export default memo(AnswerRenderer);
