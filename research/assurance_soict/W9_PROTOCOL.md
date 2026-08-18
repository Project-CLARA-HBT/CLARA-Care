# W9 Protocol — GovMut/SOICT follow-up corpus execution (design phase)

Status: **protocol definition; W9-T01..T04 design complete, execution NOT started**.
This document states what W9 execution requires. It is not an execution log.

Inputs produced by the design phase (this W9 task):
- `mutation_adequacy_audit.md` (W9-T01) — maps all 45 sealed mutants to
  invariant/enforcement site/fault family/layer and reports method-matrix and
  layer coverage gaps.
- `W9_FOLLOWUP_CORPUS_PROPOSAL.json` (W9-T02..T04) — 11 proposed mutants
  (commitment gateway 5, governance-cache 3, persistence-reconstruction 3) with
  grep-verified unique anchors. **Proposal only; no code created, not executed,
  no models called.**

## 1. New frozen protocol version (required before any execution)

W9 may not reuse the W8 freeze or run artifacts. Execution requires a new,
distinctly-versioned protocol:

- New catalog: the W9 corpus (from `W9_FOLLOWUP_CORPUS_PROPOSAL.json`) merged
  under a new catalog schema version (e.g. `govmut-w9-catalog.v1`), with the
  45 sealed mutants excluded from the W9 denominator (W8 remains a separate,
  sealed study; W9 is a distinct follow-up corpus).
- New freeze: new `freeze_id` (e.g. `govmut-soict-2026-w9-v1`), new
  `code_revision` captured at freeze time, new `final_freeze.json` style
  manifest with frozen Hypothesis version, ordered seeds, and positive limits.
- New analysis schema version distinct from `govmut-final-analysis.v1`.
- The frozen aggregation rule (`ANALYSIS_PLAN.md`, primary `detected_any_seed`,
  robustness `detected_all_seeds`, seeds are deterministic streams not
  independent N) is carried forward unchanged unless the new freeze explicitly
  revises it in writing. Any revision must be pre-registered before execution.

## 2. Hardened W7 dual-model non-equivalence review (required)

Each proposed W9 mutant must pass a hardened version of the W7 review before it
may enter a locked denominator. Hardening relative to W7 (`MODEL_REVIEW_PROTOCOL.md`,
`dual_model_review_manifest.json`):

- Same label set and decision rule as W7:
  `NON_EQUIVALENT` / `EQUIVALENT` / `INVALID` / `UNCERTAIN`, with the W7
  `final_disposition_rule` (mutual `NON_EQUIVALENT` → included; mutual
  `EQUIVALENT` → excluded_equivalent; mutual `INVALID` → excluded_unexecutable;
  all other outcomes, including disagreement after **at most one anonymous
  reconciliation round**, → unresolved).
- W7 hardening additions for W9:
  1. **Anchor re-verification at freeze revision**: the W9 anchors were verified
     against the current working tree; the review packet must re-verify every
     anchor is a unique substring (`count == 1`) in the *frozen* code revision,
     following the M02-B rebinding precedent in `final_freeze.json`
     (`rebinding_note`).
  2. **Layer/ method pairing declared per case**: each case packet states which
     of the new-layer mutants can plausibly be observed by which method
     (admission-side M0 vs replay/reconstruction paths), so a later
     "survived all methods" cannot be misread as equivalence.
  3. **No over-claim of equivalence for observer-side defects**: reviewers must
     confirm the mutant changes *enforcement*, not only a measurement path.
- Same model IDs used for W7 (`gemini-3.6-flash-high`, `claude-sonnet-4-6`) or
  a revision recorded in the new freeze. Mutually `NON_EQUIVALENT`, or mutually
  `NON_EQUIVALENT` after one reconciliation round, are the only mutants that
  enter the denominator.

## 3. New corpus freeze + M0-M3 via the existing final_runner (required)

Execution must use the existing runner on a new frozen freeze:

- `python -m evaluation.property_assurance.soict_final_runner` (wraps
  `final_runner.execute_final_run`) over the new catalog + new freeze, exactly
  as W8 did, but with the W9 corpus and new freeze inputs.
- Mutation overlay must satisfy `mutation_overlay.py` constraints
  (`govmut_overlay_anchor_not_unique`, `anchor != replacement`) — anchors are
  unique by design; any anchor that fails at execution time is an
  `INFRASTRUCTURE_ERROR`/exclusion, never a kill.
- The full 4-method grid M0/M1/M2/M3 with the new frozen ordered seeds and
  limits must be validated by `final_validate.py` (no duplicate/missing
  `(mutant, method, seed)` slots).
- Method targets: the existing method matrix targets the gateway-level test
  modules. W9 mutants were chosen to be reachable by that matrix (they live in
  `glhs/gateway.py` and `glhs/commitment_gateway.py`). API-layer mutants are
  deliberately deferred because they need new route-level method targets
  outside the existing grid (see `W9_FOLLOWUP_CORPUS_PROPOSAL.json`
  `remaining_gap`).

## 4. Paired method inference at mutant level (required)

Beyond the frozen aggregate scores, W9 requires per-mutant × per-method
inference (mutant-level `detected_any_seed`, `detected_all_seeds`,
`kill_fraction`, `seed_instability`, `first_killing_seed`,
`time_to_first_kill_ms`), followed by paired method comparisons over the same
mutant set (2x2 table, exact two-sided McNemar p-value), consistent with
`ANALYSIS_PLAN.md`. This lets W9 answer, per layer:
- whether the replay/reconstruction paths (persistence-reconstruction,
  commitment-gateway reconstruction) are observable by M0 at all, and
- whether M1/M2 add detection over M0 for the new-layer faults (the sealed study
  showed M1/M2 add almost nothing on commitment-gateway mutants).

## 5. New seal (required)

- `final_seal.py` into a **new** seal location/prefix (e.g. `seal-w9/` or a new
  freeze-named directory). Artifacts: `artifact-sha256.json`,
  `environment.json` (git SHA, Hypothesis version, limits, Python), `README.md`,
  `claim_to_evidence.csv`, plus byte hashes of the new run and analysis.
- The new seal must not overwrite, rename, or touch the W8 seal directory
  (`research/assurance_soict/seal/*`), `final_run.json`, `final_freeze.json`, or
  `results/final-analysis.json`.

## 6. W8 immutability statement

The W8 sealed 45-mutant study is **immutable and remains authoritative**:
- `research/assurance_soict/seal/*` (frozen artifacts, `govmut-soict-2026-final-v2`),
- `research/assurance_soict/final_run.json`, `final_freeze.json`,
  `results/final-analysis.json`.
- Headline scores are unchanged: M0 .356, M1 .089, M2 .133, M3 .444; M3
  subsumes M0 and significantly beats M1/M2.
W9 is a distinct, additional corpus; it does not revise W8 numbers and cannot
weaken any W8 conclusion.
