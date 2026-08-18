# NEGATIVE_RESULTS — W3 comparator refinement / W6 external-utility preparation

Date: 2026-08-18
Scope: this file records, for the frozen RIVF/GLHS/external-structural evidence
and the W6 utility preparation, everything that was **not** established,
**not** run, or was left explicitly indeterminate. NOT_RUN / missing / unclear
results are never converted into zeros or successes. No git commit, no
CareGuard/SOICT/remote-VPS changes, and no router call are part of this record.

## 1. GLHS TOCTOU-03 — INDETERMINATE, not converted to success

- 5 frozen schedules executed; 4 rejected; **1 committed transition (TOCTOU-03)
  with ordering classified `INDETERMINATE`** (`forbidden_commit_observed: null`).
- The overlapping commit/revoke interleaving could not be established from the
  observer records; it is never recoded as safe or as a success. The claim
  ledger wording (`GLHS-TOCTOU-001`) explicitly keeps this schedule
  indeterminate.
- Negative-results reading: GLHS concurrency evidence does **not** establish
  ordering guarantees for genuinely overlapping races; only 4/5 schedules are
  shown rejected, with 0 forbidden commits.

## 2. RIVF mandatory-primary NOT_RUN — 180/arm, not counted as zero

- `NOT_RUN = 180` per arm (protocol exclusions / unsupported adapter families)
  in run `2026-08-17-rivf-final-003`.
- These are **excluded from every denominator** and are **never recorded as zero
  failures**. The frozen statistics plan keeps missing work an explicit
  category. Any summary that implies 270 executed primary cases per arm would
  be wrong: primary_endpoint_n = 210 per arm.

## 3. RIVF dual-model protocol QA — NOT_RUN_pending_router_key

- `final_locked_manifest.json` → `independent_curator_attestation.
  dual_model_protocol_review = "NOT_RUN_pending_router_key"`.
- RIVF claim eligibility is therefore limited to `SEALED_CLAIM_ELIGIBLE` for
  the executable primary schedules; **no RIVF dual-model protocol QA result is
  asserted**. The GLHS dual-model QA (kappa 1.0) is a different run and does
  not cover RIVF.

## 4. Audit reconstruction — commits-by-design not primary, partial

- `audit_reconstruction_complete` is a **descriptive / partially observed**
  endpoint, not the primary endpoint: GLHS_STRICT 60/270,
  SNAPSHOT_BOUND_STATE_ONLY 120/270, STATE_VERSION_ONLY 0/270, UNBOUND 0/270.
- Commits-by-design mean complete audit reconstruction is not expected for every
  transition; the strongest observed arm (SNAPSHOT_BOUND_STATE_ONLY) is not the
  CLARA production arm, and no paired test is reported for this contrast.
  The comparison table marks this row `NOT_COMPARABLE` accordingly.

## 5. No clinical validation available

- All RIVF, GLHS, and external-structural evidence is on **synthetic or
  de-identified source-derived data** with synthetic governed records; it is a
  controlled software robustness / structural-mechanics demonstration.
- There is **no clinical-effectiveness, clinician-adjudicated, or production
  deployment result**. The external structural (eICU) protocol explicitly sets
  `clinical_oracle: false` and `headline_eligible: false`; targets are
  source-offset-derived, not clinician-adjudicated.

## 6. No faithful same-task MemTX/MemTxn/CommitGuard execution — ASSET_GATED

- MemTX, MemTxn, and CommitGuard remain `ASSET_GATED` with an explicit upgrade
  path to `DIRECTLY_COMPARABLE`. No same-task mapping and no verified,
  license-compatible assets exist at freeze time, so **no numerical comparison
  is made and none of these systems is claimed as beaten**.
- This applies to the whole nearest-neighbor set in
  `evaluation/comparator_studies/published_systems.yaml`: the remainder are
  `MECHANISM_REFERENCE_ONLY` (STALE, Cordon, TOKI), `TASK_MISMATCH`
  (Mem2ActBench), or `ASSET_GATED` (MemClaw, SuperLocalMemory_4,
  ContinuityKernel, GateMem). A citation alone never licenses a numerical
  comparison.

## Honesty rule restated

NOT_RUN / missing / indeterminate / not-established outcomes are preserved as
explicit categories in `PRIOR_WORK_COMPARISON.csv`, `CLAIM_TO_EVIDENCE.csv`,
`estimands.yaml`, and this file. No row is upgraded, no p-value is invented,
and no comparison is fabricated.
