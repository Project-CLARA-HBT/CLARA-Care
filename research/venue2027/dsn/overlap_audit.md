# DSN P01 · Publication and Evidence Isolation Audit (DSN-overlap)

- **Task:** `DSN-overlap` (Phase P01, venue `dsn`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/dsn/novelty_contract.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/publication_registry.yaml`.
- **Executable check:** `research/venue2027/_shared/tools/overlap_contract.py` (the required
  P01 overlap validator) is run against this file; and
  `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`: the `dsn` entry shares no
  question+endpoint pair with any other venue and declares `reuses_archive: []`
  (report: `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`).

## 1. Comparison against all eight sibling 2027 venues

The DSN study asks whether **recoverable safety journals** make the *joint* outcome of a
clinical row, an immutable AI-decision receipt, and an asynchronous side-effect record
crash-consistent for AI-mediated health-state mutations under fault injection. Its primary
endpoint is **crash-consistency violation rate after fault injection** (registry wording),
with co-endpoints duplicate externally visible side effects, phantom user-visible success,
and recovery-time (RTO p99) cost after crash cut-points. None of the eight sibling venues
shares that question or endpoint:

| Sibling venue | Question focus | Primary endpoint | Shared with DSN? |
|---|---|---|---|
| popets 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface for cached AI context, no crash/recovery semantics |
| aime 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level recommendation quality, no durable-state fault injection |
| ifip_sec 2027 (IFIP SEC) | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — verification-time replay prevention, not post-crash storage reconciliation |
| sacmat 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — policy decision conformance, not joint-outcome recoverability |
| acns 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy, no benchmark or crash oracle |
| compsac 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — concurrent-write admission under benign contention; contrast formalized in §4 |
| dimva 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams, no durable-write crash windows |
| pst 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc audit inference, not crash-window joint outcomes |

The machine-readable registry (`_shared/publication_overlap_registry.yaml`, `audit_ok: true`)
records `dsn` with `research_question: "Are recoverable safety journals crash-consistent for
AI-mediated health-state mutations?"`, the endpoint above, dataset `synthetic-dsn-2027`, and
`reuses_archive: []`. The executable `claim_overlap.py` audit over `_shared/study_claims.json`
returns zero findings involving dsn: no `SALAMI_SAME_QUESTION_AND_ENDPOINT`, no
`SHARED_PRIMARY_ENDPOINT`, no `SHARED_RESEARCH_QUESTION`, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness on a single database boundary | Different question (governance binding, not crash recoverability). The truly distinct endpoint is stated in `dsn/novelty_contract.md` §4: GLHS R4's historical E15–E19 backend attestation is `sqlite:///:memory:` and therefore cannot support PostgreSQL crash-recovery claims; DSN measures joint crash-window recoverability across three persistence boundaries on real PostgreSQL |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; stale-commit acceptance | Superficially shares the word "commit"; but GovRed measures disclosure→mutation→commit drift, not orphaned durable effects after crash cut-points. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — DSN does not reuse that frozen evidence |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score (W8 45-mutant corpus) | Different endpoint family (mutation-testing adequacy); no GovMut mutant score is a DSN result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `frozen_manifest: NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`, the AIME–HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work, cited as background per anti-salami rule 4; its governed-commit correctness numbers are motivation, never DSN evidence |

The PoPETs–PST, IFIP SEC–ACNS, IFIP SEC–DIMVA, SACMAT–GovMut, and AIME–HEALTHINF potential
merge pairs recorded in `ANTI_SALAMI_REVIEW.md` do not touch DSN's claim surface. The one
recorded merge pair involving this venue is **DSN–COMPSAC (crash correctness vs
concurrency)**, resolved in §4 below.

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by the registry declaration and by the executable
audit. Every row states what DSN actually reuses and what is uniquely new:

| Artifact | Purpose in DSN | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS append-only listener + governance domain model (`services/api/src/clara_api/glhs`) | Engineering substrate / background method only; cited, never counted as evidence | Context for RQ1–RQ3 | No — GLHS schedules, attack classes A01–A16, and case IDs are not executed or re-scored | No | No | No — GLHS endpoints (governed read-to-proposal-to-write correctness) differ from crash-consistency violation rate | New crash-window fault scheduler: 48 crash windows × 4 orderings × 3 delivery schedules × 5 seeds (post-dedup), workers 1/2/4/8 |
| Frozen parent GLHS E15–E22 outcomes | Historical background and motivation only (see §5 refusal) | Background | No | No | No | No — dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility; none measures post-crash joint recoverability | — (citation only) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — stale-commit acceptance is a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN records | Cited as related medication-identity work | Background | No | No | No | No — false-clear DDI rate is unrelated | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| Elle/Jepsen (`elle20`), Silo (`silo13`), Zanzibar (`zanzibar19`), Macaroons (`macaroons14`), FHIR R5 (`fhir5`), RFC 9162 (`ct9162`) | Baseline arms B1/B2 semantics, independent Elle-compatible history oracle, authorization/consent context | RQ1–RQ3 | No | No | No | No — comparators, not reused results | New B0–B3 arms on real PostgreSQL; new recoverable-outcome function with explicit INDETERMINATE terminal state; new reconciliation safety journal (B3) |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as DSN evidence. All DSN claims must derive
mechanically from `artifacts/venue2027/dsn/<run_id>/manifest.json` produced by this study's
own frozen protocol.

## 4. DSN–COMPSAC contrast: crash consistency vs concurrent-write admission

`ANTI_SALAMI_REVIEW.md` records DSN–COMPSAC as a potential merge/alternative-route pair.
This audit refuses the merge on endpoint separation, consistent with
`CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"DSN needs crash cut-points; COMPSAC needs
benign-contention and dependency scope."* The same concurrency schedule is never reused as
two independent primary studies.

- **DSN 2027 (crash consistency).** Injects crash cut-points and recovery fault schedules
  into a real PostgreSQL backend and measures the joint outcome of the clinical row, the
  decision receipt, and the outbox record *after bounded recovery*: crash-consistency
  violation rate, orphan clinical writes, phantom user-visible success, duplicate side
  effects, and RTO p99. Includes at-least-once duplicate delivery, concurrent consent
  revocation, and an explicit INDETERMINATE terminal label.
- **COMPSAC 2027 (concurrent-write admission).** Injects no crash cut-points, builds no
  recovery journal, and measures no reconciliation. Its schedules are disjoint from DSN's
  crash schedules by design; the workload is *benign contention* (concurrent legitimate
  writers) plus omitted-dependency faults, measured as false-stale rejection, forbidden
  commit rate, and throughput under dependency-scoped optimistic admission.

A commit-correctness result under contention is not a recoverability result after crashes,
and vice versa: admission decides *whether a write may commit while the system is up*;
recoverability decides *whether the joint effect survives a crash mid-flight and is honestly
reconciled afterwards*. Neither study's evidence can substitute for the other's.

## 5. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the DSN 2027 study, in any section, table, figure, or statistical
test.** They are background and motivation only. This audit refuses: (a) counting any frozen
E15–E22 outcome as a DSN result — per the anti-salami gate, frozen E15–E22 data, GovRed
results, and GovMut results cannot be counted as any of the nine independent 2027 results;
(b) reusing R4 SQLite observations as PostgreSQL crash-recovery evidence — the source audit
(`SOURCE_AUDIT_2026_11_14.md`) attests E15–E19 backends as `sqlite:///:memory:`, so they
cannot support crash-window claims on a real backend; (c) reusing GovRed (RIVF) or GovMut
(SOICT) frozen studies as DSN results. Every DSN claim must derive mechanically from this
study's own frozen protocol artifacts. This refusal is a binding condition inherited by all
downstream DSN tasks (`dsn/novelty_contract.md` §5).

## 6. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut/CareGuard, per the five-part
distinction test: (1) the recoverable-outcome function over the *joint* tri-state
(COMMITTED/REJECTED/INDETERMINATE) of row + decision receipt + side-effect record — no cited
prior work defines it; (2) a crash-window fault-injection scheduler (48 windows × 4
commit/revocation orderings × 3 delivery schedules × 5 seeds) with an Elle-compatible
independent oracle; (3) the reconciliation safety journal candidate (B3) against fully
implemented B0–B2 baselines on real PostgreSQL under equal budget and pinned versions;
(4) reconciliation-fraction and RTO endpoints never measured by any sibling or historical
study; (5) the explicit refusal discipline for INDETERMINATE evidence. Sharing the
repository and background methods with prior work is acceptable; repackaging the same
primary experiment is not done here.

## 7. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving dsn — no other 2027
venue shares DSN's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
shared `overlap_contract.py` validator accepts this document against all eight sibling
venues and the five historical comparators. (3) The nine-venue comparison (§1) and five
historical comparisons (§2) show distinct questions and endpoints on every row. (4) The
artifact reuse table (§3) shows no reused raw case IDs, labels, figures, or endpoints; all
extension evidence is new. (5) The DSN–COMPSAC merge pair is refused by endpoint separation
(§4). (6) Frozen E15–E22 outcomes are explicitly NOT reused as new independent evidence
(§5), matching the negative gate "Same E15–E22 outcome rebranded" — which does not occur.
No duplicate primary claim or data presented twice as new exists; the pass gate "PASS or
explicit alternative-venue merger" is satisfied by PASS.
