# COMPSAC P01 · Publication and Evidence Isolation Audit (COMPSAC-overlap)

- **Task:** `COMPSAC-overlap` (Phase P01, venue `compsac`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/venue2027/compsac/novelty_contract.md`,
  `research/publication_registry.yaml`,
  `research/venue2027/CONTEXT/SOURCE_AUDIT_2026_11_14.md`.
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the compsac entry shares no
  question+endpoint pair with any other venue (log:
  `research/venue2027/proof/logs/COMPSAC-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).

## 1. Comparison against all nine 2027 venues

The COMPSAC study asks whether **automatically derived, semantically required
cross-resource dependencies** for AI-generated clinical writes reduce unnecessary aborts
without increasing forbidden commits, and where dependency-scope overhead erases throughput
gains against PostgreSQL SERIALIZABLE. Its primary endpoint is **forbidden commit rate under
dependency-complete schedules** (registry wording), with co-endpoints oracle-defined
false-stale rejection and committed throughput under *benign contention*. No other 2027
track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with COMPSAC? |
|---|---|---|---|
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — crash recoverability, not benign-contention admission |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface, no commit admission |
| IFIP SEC 2027 | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — token/replay admission, not transactional read-set closure |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature, no benchmark run |
| AIME 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level recommendation quality, not concurrent writes |
| SACMAT 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — policy decision conformance, not OCC admission |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams, not commit correctness |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc forensic inference, not concurrency |
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | (self) |

The machine-readable registry
(`_shared/publication_overlap_registry.yaml`, `audit_ok: true`) records `compsac` with
`research_question: "Compared with globally versioned OCC, does a dependency-complete read
set reduce unnecessary aborts without increasing forbidden commits?"`, the endpoint above,
dataset `synthetic-compsac-2027`, and `reuses_archive: []`. Pairwise audit findings: none —
no `SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for compsac, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness | Different question (governance binding, not concurrency admission); R4's prospective protocols E15–E22 measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility — none measures false-stale/forbidden-commit under benign contention |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; unauthorized/stale commit acceptance | Superficially nearest on the word "commit"; but GovRed measures disclosure→mutation→commit drift across the real boundary, not dependency-derived read sets under concurrent workers. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — COMPSAC does not reuse that frozen evidence |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score | Different endpoint family (mutation testing adequacy, W8 45-mutant corpus); no mutant score is a COMPSAC result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work; cited as background. Its governed-commit correctness numbers are motivation, never COMPSAC evidence |

The AIME–HEALTHINF distinction and the SACMAT–GovMut distinction in
`ANTI_SALAMI_REVIEW.md` do not touch COMPSAC's claim surface; the recorded potential merge
pair that does involve COMPSAC is DSN–COMPSAC, resolved in §4.

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every row
below states what COMPSAC actually reuses and what is uniquely new:

| Reused artifact | Purpose in COMPSAC | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic 64-subject cohort *concept* (medication/allergy/history/consent domain model) | Domain background only; new deterministic schedule families are generated fresh | RQ1–RQ3 context | No — GLHS schedules/attack classes A01–A16 are not executed or re-scored | No | No | No — GLHS endpoints (invalid admission, transport rejection, checksum concordance) differ from forbidden commit rate | New `synthetic-compsac-2027` schedules; new challenge families F1–F5 (concurrent medication writes, allergy races, grant revocation races, omitted-dependency write skew, Zipf contention) |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No | — (citation only; see §5 refusal) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — GovRed's stale-commit acceptance is measured on a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| Silo (`silo13`), Elle (`elle20`), Zanzibar (`zanzibar19`), Macaroons (`macaroons14`), PostgreSQL SSI (Ports & Grittner 2012) | Baseline arms B1/B2, independent history checker, permission-consistency contrast | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | New arms B0–B4 on real PostgreSQL; new dependency-closure oracle; new fanout/contention frontier |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as COMPSAC evidence. All COMPSAC claims must
derive from `artifacts/venue2027/compsac/<run_id>/manifest.json` produced by this study's
own frozen protocol.

## 4. DSN contrast: crash consistency vs concurrent-write admission

`ANTI_SALAMI_REVIEW.md` records DSN–COMPSAC (crash correctness vs concurrency) as a
potential merge/alternative-route pair. This audit refuses the merge on endpoint
separation, consistent with `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"DSN needs crash
cut-points; COMPSAC needs benign-contention and dependency scope."*

- **DSN 2027** injects crash cut-points and recovery fault schedules; its primary endpoint
  is duplicate/lost durable effects after crashes (crash-consistency violation rate). It
  builds a recovery journal and measures post-crash reconciliation.
- **COMPSAC 2027** injects no crash cut-points, builds no recovery journal, and measures no
  reconciliation. Its schedules are disjoint from DSN's crash schedules by design; the
  workload is *benign contention* (concurrent legitimate writers) plus omitted-dependency
  faults, measured as false-stale rejection, forbidden commits, and throughput under
  dependency-scoped admission (RQ1–RQ3).

A commit-correctness result under contention is not a recoverability result after crashes,
and vice versa. Neither study's evidence can substitute for the other's; the same
concurrency schedule is never reused as two independent primary studies.

## 5. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the COMPSAC 2027 study, in any section, table, or figure.** They are
background and motivation only. Concretely, this audit refuses: (a) counting any frozen
E15–E22 outcome as a COMPSAC result; (b) reusing R4 SQLite observations as PostgreSQL
performance — the source audit (`SOURCE_AUDIT_2026_11_14.md`) attests E15–E19 backends as
`sqlite:///:memory:`, so they cannot support any SSI/serializability claim, and the task's
own risk register states "never reuse R4 SQLite as PG performance"; (c) reusing GovRed
(RIVF) or GovMut (SOICT) frozen studies as COMPSAC results. Evidence for every COMPSAC
claim must derive mechanically from this study's own frozen protocol artifacts. This
refusal is a binding condition inherited by all downstream COMPSAC tasks
(`novelty_contract.md` §5.2).

## 6. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test: (1) a machine-checkable dependency-closure oracle deriving per-operation
required cross-resource read sets (including consent/policy epochs) — no prior system
derives them; (2) baseline arms B0–B4 (global-profile version OCC, Silo-style entity readset
OCC, PostgreSQL SERIALIZABLE SSI, entity-OCC ablation without dependency closure, and the
dependency-complete candidate) on real PostgreSQL; (3) the two-sided safety/throughput
frontier with crossover fanout/contention analysis; (4) new synthetic-compsac-2027 schedule
families and challenge families F1–F5; (5) independent Elle-based adjudication of exported
histories. Sharing the repository and background methods with prior work is acceptable;
repackaging the same primary experiment is not done here.

## 7. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving compsac — no other 2027
venue shares COMPSAC's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
nine-venue comparison (§1) and five historical comparisons (§2) show distinct questions and
endpoints on every row. (3) The artifact reuse table (§3) shows no reused raw case IDs,
labels, figures, or endpoints; all extension evidence is new. (4) The DSN–COMPSAC merge
pair is refused by endpoint separation (§4). (5) Frozen E15–E22 outcomes are explicitly not
reused as new independent evidence (§5), matching the negative gate "Same E15–E22 outcome
rebranded" — which does not occur. No duplicate primary claim or data presented twice as
new exists; the pass gate "PASS or explicit alternative-venue merger" is satisfied by PASS.
