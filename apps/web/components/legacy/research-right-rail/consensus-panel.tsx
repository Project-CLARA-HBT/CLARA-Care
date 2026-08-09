import { ResearchTier2ConsensusEntry } from "@/lib/research";

type ConsensusPanelProps = {
  /**
   * Per-key-claim evidence-agreement counts. Surfaced only when the
   * `RESEARCH_CONSENSUS_ENABLED` flag emitted a consensus section
   * (Requirement 9.3); an empty list renders nothing so legacy results are
   * unchanged.
   */
  consensus: ResearchTier2ConsensusEntry[];
};

/**
 * Evidence Agreement (Consensus) view (Requirement 9.3, design §9).
 *
 * Displays the support / contrast / neutral source counts for each key claim,
 * derived by the orchestrator from per-source NLI verdicts. This is a
 * user-facing summary (not admin-gated telemetry) and is shown only when the
 * orchestrator provides consensus counts.
 */
export default function ConsensusPanel({ consensus }: ConsensusPanelProps) {
  if (!consensus.length) return null;

  return (
    <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          Đồng thuận bằng chứng
        </p>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
          {consensus.length}
        </span>
      </div>

      <ul className="mt-3 space-y-2">
        {consensus.map((entry, index) => (
          <li
            key={`${entry.claim}-${index}`}
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
          >
            <p className="text-sm font-medium text-[var(--text-primary)]">{entry.claim}</p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span
                className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--status-ok-text)]"
                title="Số nguồn ủng hộ"
              >
                Ủng hộ {entry.support}
              </span>
              <span
                className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--status-danger-text)]"
                title="Số nguồn phản bác"
              >
                Phản bác {entry.contrast}
              </span>
              <span
                className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]"
                title="Số nguồn trung lập"
              >
                Trung lập {entry.neutral}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
