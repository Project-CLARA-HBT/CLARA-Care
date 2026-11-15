# IFIP_SEC P01 · Publication and Evidence Isolation Audit (IFIP_SEC-overlap)

- **Task:** `IFIP_SEC-overlap` (Phase P01, venue `ifip_sec`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`
  (SHA-256 `79f33faca3c9d30b7cfc60573b583da39f9c9587dc16d4fcddfc44eb83d7cb0a`),
  `research/venue2027/ifip_sec/novelty_contract.md`,
  `research/venue2027/ifip_sec/threat_model.md`,
  `research/publication_registry.yaml`,
  `research/venue2027/CONTEXT/SOURCE_AUDIT_2026_11_14.md`.
- **Executable checks:** (a) the REQUIRED shared validator
  `research/venue2027/_shared/tools/overlap_contract.py` was run against this file with
  `--venue ifip_sec` and returns `ok: true` (log:
  `research/venue2027/proof/logs/IFIP_SEC-overlap.validator.log`); (b)
  `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the `ifip_sec` entry shares no
  question+endpoint pair with any other venue (log:
  `research/venue2027/proof/logs/IFIP_SEC-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).

## 1. Comparison against all nine 2027 venues

The IFIP_SEC study asks whether **replay-closed authorization across purpose, delegation and
AI proposal lineage** prevents authorized-looking replay attacks: a valid consent-purpose
receipt is delegated, refreshed and consumed across policy-epoch changes and concurrent
replay, and each authorization architecture is measured on whether it admits an invalid
replay or rejects a valid operation. Its primary endpoint is **replay acceptance rate across
purpose/delegation lineage** (registry wording), with co-endpoints duplicate consumption
races (RQ2) and token bytes / p95 verify latency / authorization DB round trips (RQ3). No
other 2027 track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with IFIP_SEC? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — transactional read-set closure under benign contention, not token/replay admission at the authorization boundary |
| popets 2027 (PoPETs) | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface (cache/prompt redisclosure after revocation), not admission-time replay closure |
| aime 2027 (AIME) | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate under consent/medication history changes | No — task-level recommendation quality, not multi-principal capability admission |
| sacmat 2027 (SACMAT) | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — cross-engine decision conformance, not single-frozen-semantics replay admission |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy (see §4 for the full mechanism-vs-SoK contrast) |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — post-crash recovery, not admission decisions; nonce-store Byzantine/storage faults are excluded here |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — campaign detection over event streams (see §5 for the full prevention-vs-detection contrast) |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc audit inference/retention, not verify-time admission; no audit-minimization analysis here |
| IFIP SEC 2027 | Replay-closed authorization across purpose, delegation and AI proposal lineage | replay acceptance rate across purpose/delegation lineage | (self) |

The machine-readable registry
(`_shared/publication_overlap_registry.yaml`, `audit_ok: true`) records `ifip_sec` with
`research_question: "Does replay-closed authorization across purpose, delegation and AI
proposal lineage prevent authorized-looking replay attacks?"`, the endpoint above, dataset
`synthetic-ifip_sec-2027`, and `reuses_archive: []`. Pairwise audit findings: none —
no `SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for ifip_sec, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness | Highest-risk neighbor (flagged in `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: "IFIP SEC … GLHS R4 E15 (high overlap risk)"). Distinction: GLHS R4's E15 measures disclosure-to-commit continuity — whether a persistent write matches the exact disclosed projection; IFIP_SEC measures admission-time replay closure across delegation lineage under epoch changes and concurrent consumption. GLHS R4's prospective protocols E15–E22 (dispatch attestation integrity, five-way comparator, current-state insufficiency witness, support separation, transport serialization, provider receipts, formal novelty model, reproducibility audit) measure none of the replay acceptance / duplicate-consumption endpoints; §6 refuses their reuse outright |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; unauthorized/stale commit acceptance | Superficially adjacent on "authorization drift"; but GovRed measures disclosure→mutation→commit drift across the real boundary, not capability-receipt replay under delegation/epoch interleavings. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — IFIP_SEC does not reuse that frozen evidence |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score | Different endpoint family (mutation-testing adequacy, W8 45-mutant corpus); per `PREVIOUS_ANTI_OVERLAP_MATRIX.md` the SACMAT–GovMut control is explicit and none of the W8 45-mutant scores can be new IFIP_SEC results either |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); registry status `NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work; cited as background per anti-salami rule 4. Its governed-commit correctness numbers are motivation, never IFIP_SEC evidence |

The AIME–HEALTHINF and SACMAT–GovMut distinctions in `ANTI_SALAMI_REVIEW.md` do not touch
IFIP_SEC's claim surface; the recorded potential merge pairs that do involve IFIP SEC
(IFIP SEC–ACNS, IFIP SEC–DIMVA) are resolved in §4 and §5.

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every row
below states what IFIP_SEC actually reuses and what is uniquely new:

| Reused artifact | Purpose in IFIP_SEC | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic 64-subject cohort *concept* (medication/allergy/history/consent domain model) | Domain background only; new principal graph and replay interleavings generated fresh | RQ1–RQ3 context | No — GLHS schedules/attack classes A01–A16 are not executed or re-scored | No | No | No — GLHS endpoints (governed read-to-proposal-to-write correctness, invalid admission of transport attacks) differ from replay acceptance rate across purpose/delegation lineage | New `synthetic-ifip_sec-2027` account fixtures; new replay case families (actor/purpose/tenant/lineage/revocation/epoch/nonce interleavings per `IFIP_SEC-X07_replay_generator`) |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No | — (citation only; see §6 refusal) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — GovRed's stale-commit acceptance is measured on a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| Macaroons (`macaroons14`), Zanzibar (`zanzibar19`), Cedar/OPA, OpenFGA, Elle (`elle20`), Silo (`silo13`), PostgreSQL | Baseline arms B0–B4 (bearer receipt, Macaroon caveats, Zanzibar consistency token, Cedar/OPA nonce registry, proposed delegated lineage transition verifier), independent linearizability checker, cost comparators | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | New replay-closure verifier with parent-reference binding and atomic nonce consumption; new epoch-interleaving attack corpus; new Pareto cost profile at equal decision safety |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as IFIP_SEC evidence. All IFIP_SEC claims must
derive from `artifacts/venue2027/ifip_sec/<run_id>/manifest.json` produced by this study's
own frozen protocol on the `synthetic-ifip_sec-2027` dataset.

## 4. ACNS contrast: prevention mechanism vs systematic literature SoK

`ANTI_SALAMI_REVIEW.md` records IFIP SEC–ACNS (mechanism vs SoK) as a potential
merge/alternative-route pair. This audit refuses the merge on endpoint separation, consistent
with `novelty_contract.md` §5.2 and `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"One is
replay-resistant admission, one is SoK bibliographic taxonomy; literature SoK must be
independent of self-referential performance results."*

- **ACNS 2027 (SoK)** builds an evidence-boundary coverage matrix of attestation in
  tool-using AI systems: a systematic literature corpus, independent human coders with
  inter-rater agreement, an executable taxonomy, and counterexample witnesses over
  *published claims*. Its evidence is bibliographic, not executable admission traces.
- **IFIP_SEC 2027** is an executable **prevention-mechanism** evaluation: admission decisions
  on a new synthetic interleaving corpus, with an independent allow/deny oracle derived from
  the frozen principal graph, baselines B0–B4, and per-history McNemar/bootstrap inference.

Controls in both directions: the SoK must not cite this study's self-referential performance
numbers as taxonomy evidence, and IFIP_SEC must not reuse ACNS's literature corpus, taxonomy
cells, or coder outputs as its own evidence. Same trust-domain problem space; different
research question, primary endpoint, and independent evaluation design — two studies, not
two venues for one manuscript.

## 5. DIMVA contrast: prevention vs detection

`ANTI_SALAMI_REVIEW.md` records IFIP SEC–DIMVA (prevention vs detection) as a potential
merge/alternative-route pair. This audit refuses the merge, consistent with
`novelty_contract.md` §5.3 and `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"One prevents invalid
tokens at verification, one detects campaigns over time, measured on independent detectors
and event streams."*

- **DIMVA 2027** detects adaptive authorization-boundary probing campaigns over time-series
  agent event streams; its endpoint is probing detection AUC at a fixed false-positive
  budget, with privacy-constrained metadata and unseen-family holdout.
- **IFIP_SEC 2027** denies invalid tokens at verification time and measures per-unique-history
  admission decisions (replay acceptance rate, duplicate consumption races, valid control
  acceptance). No detector score, AUCPR, time-to-detect, or campaign-classification metric
  may appear as an IFIP_SEC endpoint, and no IFIP_SEC admission corpus may serve as DIMVA
  training/detection data.

Detection infers attacker campaigns after the fact; replay closure decides single admissions
correctly at the boundary — different endpoint, different dataset, different oracle.

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the IFIP_SEC 2027 study, in any section, table, or figure.** They are
background and motivation only. Concretely, this audit refuses: (a) counting any frozen
E15–E22 outcome as an IFIP_SEC result; (b) reusing R4 SQLite observations as PostgreSQL
concurrency evidence — the source audit (`SOURCE_AUDIT_2026_11_14.md`) attests E15–E19
backends as `sqlite:///:memory:`, so they cannot support RQ2's PostgreSQL-specific
linearizability claims, and E20 is recorded `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`; (c)
reusing GovRed (RIVF) or GovMut (SOICT) frozen studies as IFIP_SEC results. Evidence for
every IFIP_SEC claim must derive mechanically from this study's own frozen protocol
artifacts on `synthetic-ifip_sec-2027`, after protocol freeze and without opening any holdout
early. This refusal is a binding condition inherited by all downstream IFIP_SEC tasks
(`novelty_contract.md` §5.1).

## 7. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test: (1) a replay-closure mechanism verifying the **full delegation ancestry
with parent-reference binding** and atomically consuming the nonce across policy-epoch
changes — beyond Macaroon signature-equality caveats and Zanzibar consistency reads; (2)
independently versioned consent and policy epochs, both revalidated online at verify time
inside a multi-principal delegation flow; (3) decision-level multi-hop AI proposal-lineage
closure (forgery/splicing/pruning/fan-out families) at admission time; (4) new baseline arms
B0–B4 on real PostgreSQL 16 — never SQLite stand-ins — with an Elle-style independent
linearizability checker over exported histories; (5) the quantified cost/Pareto profile of
replay closure (token bytes, p95 verify latency, DB round trips) at equal decision safety
with frozen non-inferiority margins. Sharing the repository and background methods with
prior work is acceptable; repackaging the same primary experiment is not done here.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `overlap_contract.py` gate over this document returns
`ok: true`, and the executable `claim_overlap.py` audit over `_shared/study_claims.json`
returns zero findings involving ifip_sec — no other 2027 venue shares IFIP_SEC's
question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The nine-venue comparison
(§1) and five historical comparisons (§2) show distinct questions and endpoints on every
row. (3) The artifact reuse table (§3) shows no reused raw case IDs, labels, figures, or
endpoints; all extension evidence is new. (4) Both recorded merge pairs involving IFIP SEC —
ACNS (mechanism vs SoK, §4) and DIMVA (prevention vs detection, §5) — are refused by
endpoint separation. (5) Frozen E15–E22 outcomes are explicitly not reused as new
independent evidence (§6), matching the negative gate "Same E15–E22 outcome rebranded" —
which does not occur. No duplicate primary claim or data presented twice as new exists; the
pass gate "PASS or explicit alternative-venue merger" is satisfied by PASS.
