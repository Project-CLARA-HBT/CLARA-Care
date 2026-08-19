# GovRed publication routing (E-011, GRD-06)

Decision date: 2026-08-19.

## Primary archival venue

**IEEE-RIVF 2026** (official CFP receipt:
`venue_cfp_receipt_20260817.json`; extended deadline 2026-08-31, tentative).
RIVF is the **primary** paper because final-003 is its sealed study:

- the GovRed-Health authorization-drift study was built, executed, and sealed
  as `2026-08-17-rivf-final-003` under the RIVF run identity;
- the frozen manifest, statistics plan, reconciliation, and residual taxonomy
  all carry the RIVF run id;
- the three-state primary table (`final-003-three-state-primary.json`) is
  derived directly from that sealed analysis.

## BigData Healthcare — held / extension-only

**BigData Healthcare is NOT a second independent full paper from final-003
alone.** Per GRD-06, a second paper requires **materially new frozen evidence**:

1. resolved concurrency (repetition protocol v1 executed with DB commit-order
   evidence, moving INDETERMINATE residuals to a resolved classification);
2. an executed fresh holdout (E-009/GRD-05) with closed manual authorship gate;
3. additional backend/attack-family evidence (E-005 Not Run families executed
   via persisted governance writers, or a real model-mediated attack protocol
   per E-006).

Until at least one of those is frozen and sealed, BigData Healthcare may hold
an extension/continuation note only. No submission is authorized from
final-003 alone to both venues.

## Routing rules

- No manuscript generation is authorized before the chosen venue's evidence is
  frozen and sealed (see `venue_cfp_receipt_20260817.json` non-authorizations).
- Recheck the RIVF CFP immediately before final formatting and again before
  submission.
- If a later paper is pursued, it must cite the primary and carry the
  materially-new-evidence delta; it must never re-present final-003 binary
  numbers as a new result.