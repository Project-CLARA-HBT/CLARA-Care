"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { UILanguage } from "@/lib/ui-language";
import type { ResearchResult } from "@/components/research/lib/research-page-types";
import { isDegradedAnswer } from "@/app/chat/_v2/lib/chat-format";
import { Badge } from "@/app/chat/_v2/components/primitives";
import { citationRegistryAnchorId, injectTracedClaimAnchors } from "@/lib/research";

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
 * each matched claim and resolve into the Citation Registry appendix
 * (clara-research Requirement 11.3, 11.4). Absent/empty preserves legacy
 * rendering.
 */

export type AnswerRendererProps = {
  result: ResearchResult;
  uiLanguage: UILanguage;
};

function AnswerRenderer({ result, uiLanguage }: AnswerRendererProps) {
  const degraded = isDegradedAnswer(result);
  const baseAnswer = result.answer?.trim() || "";
  const citations = result.tier === "tier2" ? result.citations : [];
  const tracedClaims = result.tier === "tier2" ? result.tracedClaims ?? [] : [];
  const citationRegistry = result.tier === "tier2" ? result.citationRegistry ?? [] : [];
  const answer =
    tracedClaims.length && citationRegistry.length
      ? injectTracedClaimAnchors(baseAnswer, tracedClaims, citationRegistry)
      : baseAnswer;
  const isEn = uiLanguage === "en";
  const clinicalAnswer = result.tier === "tier1" ? result.clinicalAnswer : undefined;
  const triageTone = clinicalAnswer?.triage.emergency
    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
    : clinicalAnswer?.triage.level === "urgent_review"
      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
      : "border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]";

  return (
    <div className="space-y-2">
      {degraded ? (
        <Badge tone="warn">
          {isEn ? "Degraded · local fallback" : "Suy giảm · dự phòng nội bộ"}
        </Badge>
      ) : null}

      <div className="medical-markdown prose prose-sm max-w-none text-[var(--text-primary)] prose-headings:text-[var(--text-primary)] prose-a:text-[var(--text-brand)] prose-strong:text-[var(--text-primary)]">
        {answer ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            {isEn ? "(No answer text)" : "(Chưa có nội dung trả lời)"}
          </p>
        )}
      </div>

      {clinicalAnswer ? (
        <section
          className="mt-4 space-y-3 rounded-2xl border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] p-3.5"
          aria-label={isEn ? "Clinical answer workbench" : "Bàn làm việc câu trả lời lâm sàng"}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                {isEn ? "Clinical evidence workbench" : "Bàn làm việc bằng chứng lâm sàng"}
              </p>
              <p className="mt-0.5 text-sm font-semibold text-[var(--text-primary)]">
                {isEn ? "Decision-ready answer package" : "Gói trả lời sẵn sàng để rà soát"}
              </p>
            </div>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${triageTone}`}>
              {clinicalAnswer.triage.level.replaceAll("_", " ")}
            </span>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                {isEn ? "Evidence" : "Bằng chứng"}
              </p>
              <p className="mt-1 text-base font-semibold text-[var(--text-primary)]">
                {clinicalAnswer.provenance.evidence_count}
              </p>
            </div>
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                {isEn ? "Claim support" : "Mức hỗ trợ"}
              </p>
              <p className="mt-1 text-xs font-semibold text-[var(--text-primary)]">
                {clinicalAnswer.claim_support.status.replaceAll("_", " ")}
              </p>
            </div>
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                {isEn ? "Uncertainty" : "Độ bất định"}
              </p>
              <p className="mt-1 text-xs font-semibold text-[var(--text-primary)]">
                {clinicalAnswer.uncertainty.level.replaceAll("_", " ")}
              </p>
            </div>
          </div>

          {clinicalAnswer.next_actions.length ? (
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5">
              <p className="text-[11px] font-semibold text-[var(--text-primary)]">
                {isEn ? "Recommended next step" : "Bước tiếp theo được đề xuất"}
              </p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                {clinicalAnswer.next_actions[0].action}
              </p>
            </div>
          ) : null}

          {clinicalAnswer.evidence_ledger.length ? (
            <details className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5">
              <summary className="cursor-pointer text-[11px] font-semibold text-[var(--text-primary)]">
                {isEn
                  ? `Evidence ledger (${clinicalAnswer.evidence_ledger.length})`
                  : `Sổ bằng chứng (${clinicalAnswer.evidence_ledger.length})`}
              </summary>
              <ol className="mt-2 space-y-2">
                {clinicalAnswer.evidence_ledger.map((item) => (
                  <li key={item.evidence_id} className="text-xs leading-5 text-[var(--text-secondary)]">
                    <span className="font-semibold text-[var(--text-primary)]">{item.evidence_id}</span>{" "}
                    {item.url ? (
                      <a className="text-[var(--text-brand)] hover:underline" href={item.url} target="_blank" rel="noreferrer">
                        {item.title || item.source || item.url}
                      </a>
                    ) : (
                      <span>{item.title || item.source || "—"}</span>
                    )}
                    {typeof item.trust_tier === "number" ? (
                      <span className="text-[var(--text-muted)]"> · Tier {item.trust_tier}</span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <p className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-xs text-[var(--status-warn-text)]">
              {isEn
                ? "No retrievable evidence was available. Do not treat this output as decision-ready."
                : "Chưa truy xuất được bằng chứng. Không sử dụng kết quả này như một quyết định hoàn chỉnh."}
            </p>
          )}

          {clinicalAnswer.missing_information.length ? (
            <details className="px-1 text-xs text-[var(--text-secondary)]">
              <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
                {isEn
                  ? `Case context to add (${clinicalAnswer.missing_information.length})`
                  : `Ngữ cảnh ca bệnh cần bổ sung (${clinicalAnswer.missing_information.length})`}
              </summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {clinicalAnswer.missing_information.map((item) => (
                  <li key={item.field}>
                    <strong>{item.field}</strong> — {item.why_it_matters}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}

      {citationRegistry.length ? (
        <section className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {isEn ? "Citation Registry" : "Danh mục trích dẫn"}
          </h3>
          <ol className="mt-2 space-y-1.5">
            {citationRegistry.map((entry, index) => {
              const meta = [
                entry.sourceType,
                typeof entry.trustTier === "number" && Number.isFinite(entry.trustTier)
                  ? `Tier ${entry.trustTier}`
                  : null,
                entry.publishedAt,
              ].filter(Boolean);
              return (
                <li
                  key={`${entry.citationId}-${index}`}
                  id={citationRegistryAnchorId(entry.citationId)}
                  className="scroll-mt-24 text-[12px] leading-5 text-[var(--text-secondary)]"
                >
                  <span className="font-semibold text-[var(--text-primary)]">[{index + 1}]</span>{" "}
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
                    <span className="font-mono text-[var(--text-muted)]"> · {entry.studyId}</span>
                  ) : null}
                  {meta.length ? (
                    <span className="text-[var(--text-muted)]"> · {meta.join(" · ")}</span>
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
            {isEn ? `References (${citations.length})` : `Nguồn tham khảo (${citations.length})`}
          </summary>
          <ol className="mt-2 space-y-1.5">
            {citations.map((citation, index) => (
              <li key={`${citation.title}-${index}`} className="text-[12px] leading-5 text-[var(--text-secondary)]">
                <span className="font-semibold text-[var(--text-primary)]">[{index + 1}]</span>{" "}
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
                  <span className="text-[var(--text-muted)]"> · {citation.source}</span>
                ) : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
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
