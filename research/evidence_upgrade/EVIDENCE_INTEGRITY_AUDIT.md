# EVIDENCE_INTEGRITY_AUDIT — W0 (evidence-integrity repair)

Date: 2026-08-18
Scope: RIVF final-003 + GLHS final run headline results only (SOICT/GovMut out of
scope; the running SOICT background process is untouched). Generated from immutable
artifacts; no raw result rows, claim ledgers, or manuscript files were modified.

## Machine status

- Generator: `evaluation/evidence_program/render_status.py` (W0-T08)
- Machine status output: `research/glhs_journal/CURRENT_EVIDENCE_STATUS.json`
  (`clara-w0-machine-status.v1`)
- Rendered status: `research/FINAL_PRE_CAREGUARD_STATUS.md` (RIVF/GLHS sections are
  machine-generated; hand-edited claims cannot override machine state)
- Consistency tests: `evaluation/evidence_program/test_render_status.py` (W0-T09)

`render_status.py` validation result on the current tree: **errors = [] (PASS)** for
every W0-T09 fail condition (SEALED-without-seal, frozen-plan-bytes, rate
reproducibility, missing claim artifact, run/source SHA mismatch).

## Inputs bound to exact bytes

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| RIVF provenance reconciliation | `research/govred_rivf/provenance/final-003-reconciliation.json` | (machine-generated record) |
| RIVF frozen manifest | `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json` | `f5b20de13854a1d47f5496e4e4c3052f235c416bf4a4df6909c8091da8939378` |
| RIVF frozen statistics plan | `artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_statistics_plan.json` | `db5da691f648dc8d6c9db4a673580ed81913e8076c3a5df0052f3c414768cdbc` |
| RIVF raw rows (4 arms) | `artifacts/govred/2026-08-17-rivf-final-003/{ARM}/raw_results.csv` | all match reconciliation `raw_results_sha256` |
| RIVF v2 analysis | `research/govred_rivf/results/final-003-analysis-v2.json` | (machine-readable canonical analysis) |
| GLHS run analysis | `research/glhs_journal/results/analysis.json` | `86fc839df2cd7d2c732696e5173b2ce6a9e1e500ebddd88abae401b67cfc44fb` |
| GLHS model-review agreement | `research/glhs_journal/model_review_run/agreement.json` | (kappa 1.0, unresolved 0) |
| Sealed-run inventory | `research/evidence_upgrade/audit/sealed_run_inventory.json` | (W0-T02 record) |

## Provenance findings

### RIVF final-003 (run `2026-08-17-rivf-final-003`, source SHA `5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb`)

- **F1 — Provenance binding reconciled (RESOLVED).** Reconciliation
  (`final-003-reconciliation.json`) records the exact final manifest SHA
  (`f5b20de…`), exact final statistics-plan SHA (`db5da691…`), exact
  adapter/source SHA (`5b2c0dbf…`), and exact endpoint/environment manifest SHA
  (`cd0c7a0d…`). On-disk bytes match every recorded hash; raw per-arm rows match
  `raw_results_sha256` exactly (verified by `render_status.py`).
- **F2 — Manifest-embedded stats-plan SHA matches no on-disk bytes (RESOLVED_HISTORICAL_METADATA).**
  `final_locked_manifest.json` embeds `final_statistics_plan_sha256:
  b1420da26b720b3b31d6bd6e1f3060daef7fa5b171f714be357fbcf7461a702c`, which
  corresponds to no file present in the artifact store. The machine-generated
  W0-T03 reconciliation binds the governing frozen stats-plan bytes as
  `db5da691…` (exact file present, hash matches). The manifest field is stale
  self-referential metadata and is superseded by the reconciliation record; it is
  documented, not silently ignored.
- **F3 — RIVF dual-model protocol QA is `NOT_RUN_pending_router_key` (RECORDED, NOT CLAIMED).**
  `final_locked_manifest.json` → `independent_curator_attestation.
  dual_model_protocol_review = "NOT_RUN_pending_router_key"`. RIVF headline
  claim eligibility is therefore limited to `SEALED_CLAIM_ELIGIBLE` for the
  executable primary schedules (ledger `RIVF-RESULT-001/002`); no dual-model
  protocol QA result is asserted.
- **F4 — Exact p-value, not an underflowed zero (RESOLVED, AUD-004).**
  `final-003-analysis-v2.json` stores the exact two-sided McNemar probability
  `p_exact = 1.6155871338926322e-27` (`log10_p = -26.791669614094328`; discordant
  pairs `b=90`, `c=0`). The exact probability never underflowed to zero; the
  manuscript may state `p < 0.0001`, but machine-readable output stores the exact
  value.
- **F5 — Primary rates reproduce from denominators (PASS).** All four arms:
  `primary_failures / primary_endpoint_n (210)` reproduces the declared
  `primary_rate` to 6 decimals (e.g. GLHS_STRICT 30/210 = 0.142857); NOT_RUN
  (180/arm) is excluded from every denominator.

### GLHS run (run `GLHS-POSTGRES-TOCTOU-FINAL-20260817-01`, source SHA `2074f87550c5ee32302bde47bc0b9e6be6af36b5`)

- **F6 — Run/source SHA consistent (PASS).** `results/analysis.json` `code_revision`
  == sealed-run inventory `source_sha` == run ID; the sealed artifact inventory
  resolves all 3 entries against actual bytes.
- **F7 — Headline facts match sealed artifacts (PASS).** 5 frozen logical schedules
  executed; 4 rejected; 1 committed transition (TOCTOU-03) with ordering classified
  **INDETERMINATE** (overlapping commit/revoke windows, never called safe); 0
  forbidden commits observed.
- **F8 — Dual-model protocol QA complete (PASS).** `model_review_run/agreement.json`:
  pre-reconciliation agreement 1.0, Cohen's kappa 1.0, unresolved 0. Blinded
  protocol-review surrogate only — not human/clinician adjudication.
- **F9 — Frozen plan bytes present (PASS).** `postgres_toctou_statistics_plan.json`,
  `postgres_toctou_schedule_manifest.json`, and `postgres_toctou_observer_contract.json`
  all exist and are `FROZEN_FINAL_REVIEWED`.

## Gate conclusion

**Zero unresolved provenance contradictions on any headline result.**

- RIVF final-003: all discrepancies are resolved by exact on-disk bytes bound by
  the machine-generated reconciliation; the pending dual-model protocol QA is
  recorded, not claimed (F3); exact p-value documented (F4).
- GLHS final run: no provenance contradiction found (F6–F9).

**Gate: PASS.**

Residual caveats (not contradictions): RIVF dual-model protocol QA must be run
with a router key before any claim-bearing RIVF analysis; older readiness prose
(`research/govred_rivf/READINESS.md`, `research/glhs_journal/REVISION_READINESS.md`)
remains historical and is superseded for current status by the machine-generated
`CURRENT_EVIDENCE_STATUS.json` / `FINAL_PRE_CAREGUARD_STATUS.md`.
