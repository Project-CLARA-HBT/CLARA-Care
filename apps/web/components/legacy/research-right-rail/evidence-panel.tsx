"use client";

import { Tier2Citation } from "@/lib/research";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

type EvidencePanelProps = {
  citations: Tier2Citation[];
};

export default function EvidencePanel({ citations }: EvidencePanelProps) {
  const language = useUILanguage();

  return (
    <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          {t(language, "research.workspace.evidence.title")}
        </p>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
          {citations.length}
        </span>
      </div>

      {citations.length ? (
        <div className="mt-3 space-y-2">
          {citations.map((citation, index) => (
            <article
              id={`citation-${index + 1}`}
              key={`${citation.title}-${index}`}
              className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
            >
              <p className="text-xs font-semibold text-[var(--text-brand)]">
                [{index + 1}] {citation.source ?? citation.title}
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {citation.title}
              </p>
              {citation.trustTier !== undefined || citation.publishedAt ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {citation.trustTier !== undefined ? (
                    <span className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--status-ok-text)]">
                      {t(language, "research.workspace.evidence.tier", {
                        tier: citation.trustTier,
                      })}
                    </span>
                  ) : null}
                  {citation.publishedAt ? (
                    <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                      {citation.publishedAt}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {citation.snippet ? (
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {citation.snippet}
                </p>
              ) : null}
              {citation.url ? (
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {t(language, "research.workspace.evidence.openSource")}
                </a>
              ) : (
                <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                  {t(language, "research.workspace.evidence.internalSource")}
                </p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          {t(language, "research.workspace.evidence.empty")}
        </p>
      )}
    </section>
  );
}
