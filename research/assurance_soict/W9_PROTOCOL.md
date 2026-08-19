# W9 Protocol — GovMut/SOICT follow-up corpus execution (design phase)

Status: **corpus/protocol frozen; anchor gate complete at the pre-commit current
HEAD, human MANUAL gate OPEN, execution NOT started**.

Workstream F made **no LLM calls**. No model output, placeholder, or automated
classification may satisfy the human gate below.
This document states what W9 execution requires. It is not an execution log.

Inputs produced by the design phase (this W9 task):
- `mutation_adequacy_audit.md` (W9-T01) — maps all 45 sealed mutants to
  invariant/enforcement site/fault family/layer and reports method-matrix and
  layer coverage gaps.
- `W9_FOLLOWUP_CORPUS_PROPOSAL.json` (W9-T02..T04) — 11 proposed mutants
  (commitment gateway 5, governance-cache 3, persistence-reconstruction 3) with
  grep-verified unique anchors. **Proposal only; no code created, not executed,
  no models called.**
- `w9_anchor_verification.json` — all 11 anchors verified against the committed
  current-HEAD source blobs before any outcome observation.

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

## 6. Human non-equivalence review — MANUAL precondition (required before denominator freeze)

Status: **design specified; not yet executed.** This is a MANUAL gate
(GMT-02 / F-005 / F-006). It is a human task; it SHALL NOT be simulated,
approximated, or delegated to an LLM, including for "pilot" or "sanity"
purposes. A simulated human review does not satisfy this gate.

### 6.1 Ordering and precondition

1. The human review must complete **before** the W9 denominator freeze
   (`w9_final_freeze.json` promotion, Step 5 of `W9_EXECUTION_PLAN.md`).
2. Each of the 11 W9 candidates receives independent human non-equivalence
   review **before** its disposition enters the W9 denominator.
3. Any separately recorded auxiliary review remains distinct; it does not
   substitute for, and must not be conflated with, the human review. Workstream
   F does not invoke an LLM to produce or simulate this artifact.

### 6.2 Reviewer requirements and background fields

One reviewer is the minimum; **two independent reviewers are preferred** and
are required for the agreement statistic (6.5). The preferred profile is an
independent software/verification engineer with no authorship stake in the
GovMut result, no knowledge of the W8 or W9 outcome labels, and sufficient
fluency in the Python/SQLAlchemy governance code to evaluate a one-change
overlay. Recorded per reviewer:

- `reviewer_id` (anonymized or named, per project policy);
- `background` — role/title, years of software-verification or security
  experience, familiarity with mutation testing and with the CLARA governance
  layer;
- `reviewer_independence_declaration` — confirming no prior exposure to the
  W9 strategy outcomes or W8 survivor labels;
- `review_date`.

### 6.3 Blind packet structure

Each candidate is delivered as an independent, isolated packet. Strategy
outcomes (M0/M1/M2/M3 kill/survive) MUST remain hidden during review:

- `case_id` (e.g. `W9-C01`);
- the exact one-change overlay: `source_path`, `anchor`, `replacement`;
- the invariant the mutation would violate (from `W9_MUTATION_CATALOG.json`);
- the fault family and layer (from the proposal);
- the frozen code revision the anchor was verified against;
- a "no extra context" rule: packets contain no method scores, no W8
  comparisons, no survivor lists, and no reviewer-community discussion.

Reviewers review each candidate independently; packets are exchanged between
reviewers only after both have recorded their own dispositions.

### 6.4 Rubric and disposition categories

Rubric (same behavioral test as W7, applied by humans):

> Determine whether the one-change mutation can change observable governed-system
> behavior under the CLARA governance invariants. This is a software-assurance
> non-equivalence review, not a clinical-safety review.

Disposition categories (exactly one per reviewer per candidate):

- `NON_EQUIVALENT` — the overlay can produce an observable behavioral
  difference in governed behavior;
- `EQUIVALENT` — no observable behavioral difference is possible;
- `INVALID` — the overlay is malformed, unanchored, or cannot apply;
- `UNCERTAIN` — evidence insufficient for a confident disposition.

Per-candidate final dispositions (from the two reviewers):

- both `NON_EQUIVALENT` → `included`;
- both `EQUIVALENT` → `excluded_equivalent`;
- both `INVALID` → `excluded_unexecutable`;
- any disagreement or `UNCERTAIN` after adjudication (6.6) → `unresolved`,
  excluded transparently — never counted killed or survived.

### 6.5 Agreement statistic

When two reviewers are used, compute **Cohen's kappa** over the 11-candidate
packet using the reviewer disposition categories (weighted for
`NON_EQUIVALENT` vs the other labels, or unweighted, per the frozen analysis
plan; the choice is recorded before scoring). Report:

- the 11 x 11 (or 2 x 2 collapsed) reviewer disposition table;
- `kappa` with a confidence interval where computable;
- a qualitative agreement note (e.g. `substantial`, `moderate`, `poor` via the
  standard Landis–Koch bands), used only as context, never as a pass/fail
  gate on its own.

### 6.6 Disagreement adjudication

- Initial independent dispositions are recorded before any discussion.
- Disagreement (labels differ, or either reviewer used `UNCERTAIN`) triggers
  exactly one anonymous adjudication round (reviewers exchange anonymized
  rationales without strategy outcomes).
- If dispositions still differ after that round, the candidate is
  `unresolved` and excluded transparently.
- `NON_EQUIVALENT` vs `EQUIVALENT` after the round → `unresolved` (never
  forced to either side).

### 6.7 Records and artifact

The human review produces `research/assurance_soict/w9_human_review.json`
(schema `govmut-w9-human-review.v1`) with: reviewer fields (7.2), packet
references (7.3), per-candidate dispositions per reviewer, the kappa statistic
(6.5), adjudication outcomes and date (6.6), and the overall completion date.
`w9_final_freeze.json` records `human_review.status == completed` and the
artifact hash, mirroring how the dual-model review is recorded. Without this
artifact the W9 denominator MUST NOT freeze. The executable `w9_final_runner`
and budget-fair runner both fail closed on this gate.

## 7. W8 immutability statement

The W8 sealed 45-mutant study is **immutable and remains authoritative**:
- `research/assurance_soict/seal/*` (frozen artifacts, `govmut-soict-2026-final-v2`),
- `research/assurance_soict/final_run.json`, `final_freeze.json`,
  `results/final-analysis.json`.
- Headline scores are unchanged: M0 .356, M1 .089, M2 .133, M3 .444; M3
  subsumes M0 and significantly beats M1/M2.
W9 is a distinct, additional corpus; it does not revise W8 numbers and cannot
weaken any W8 conclusion.
