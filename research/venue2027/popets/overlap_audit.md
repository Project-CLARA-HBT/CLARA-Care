# PoPETs P01 · Publication and Evidence Isolation Audit (POPETS-overlap)

- **Task:** `POPETS-overlap` (Phase P01, venue `popets`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/venue2027/popets/novelty_contract.md`,
  `research/publication_registry.yaml`,
  `research/venue2027/_shared/study_claims.json`.
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the popets entry shares no
  question+endpoint pair with any other venue (log:
  `research/venue2027/proof/logs/POPETS-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).
- **Document-level validator:** this audit is machine-checked by the shared
  anti-salami validator `research/venue2027/_shared/tools/overlap_contract.py`
  (`overlap_contract.py <this file> --venue popets`, expected exit 0) and by
  `research/venue2027/popets/tests/test_overlap_audit.py`.

## 1. Comparison against all nine 2027 venues

The PoPETs study asks whether **revocation-complete future-disclosure control** prevents
re-disclosure of revoked longitudinal context to AI models with caching, across every
derivation path (prompt segments, cached summaries, embedding pointers, retry payloads,
fallback transports). Its primary endpoint is the **revoked-context re-disclosure rate**
(registry wording), jointly measured with attribute-exposure byte count under a declared
observation model. No other 2027 track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with PoPETs? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — commit admission under contention, not post-revocation dispatch disclosure |
| AIME 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level clinical-content quality, no cache lineage |
| IFIP SEC 2027 | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — admission of reused receipts at verification, not dispatch content after revocation |
| SACMAT 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — policy-engine decision conformance, not cached-context leakage |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy, no benchmark run |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — post-crash durable-effect recoverability, no consent-revocation surface |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams, not prevention of dispatch disclosure |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc audit inference; see §5 for the mandatory PoPETs–PST separation |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | (self) |

The machine-readable registry
(`_shared/publication_overlap_registry.yaml`, `audit_ok: true`) records `popets` with
`research_question: "Does revocation-complete future-disclosure control prevent
re-disclosure of revoked longitudinal context to AI models with caching?"`, the endpoint
above, dataset `synthetic-popets-2027`, and `reuses_archive: []`. Pairwise audit findings:
none — no `SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for popets, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; `governed_read_to_proposal_to_write_correctness` | Different question (record-boundary governance binding inside one co-versioned store, not post-revocation model dispatch); R4's frozen E15–E22 protocols measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility — none measures what cached derivations re-disclose to models after `t_r` |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; `unauthorized_or_stale_commit_acceptance_and_prohibited_disclosure` | Superficially nearest on the word "revocation" (disclosure→mutation→commit drift across a real boundary); but GovRed measures commit acceptance, not transitive derived-cache re-disclosure to models. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — PoPETs does not reuse that frozen evidence |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; `mutation_score` | Different endpoint family (mutation-testing adequacy, W8 45-mutant corpus); no mutant score is a PoPETs result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work per anti-salami rule 4; cited as background. Its governance numbers are motivation, never PoPETs evidence |

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every row
below states what PoPETs actually reuses and what is uniquely new:

| Reused artifact | Purpose in PoPETs | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic cohort *concept* (medication/allergy/history/consent domain model) | Domain background only; new subject histories are generated fresh | RQ1–RQ3 context | No — GLHS schedules/attack classes A01–A16 are not executed or re-scored | No | No | No — GLHS endpoints differ from revoked-context re-disclosure rate | New `synthetic-popets-2027` bundle: 1200 unique synthetic subject histories (3–6 longitudinal contexts each), factorial lineage fanout, delayed cache writes, retries, policy changes |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No | — (citation only; see §6 refusal) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-revocation prior work | Background | No | No | No | No — GovRed's stale-commit acceptance is a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN | Named as unrelated prior surface | Background | No | No | No | No — `NOT_RUN`, nothing to reuse | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| Zanzibar (`zanzibar19`), Macaroons (`macaroons14`), MUSE (`muse`), OpenFGA (`openfga`), Cedar (`cedar`), OPA (`opa`), FHIR (`fhir5`), NIST ABAC (`nistabac`) | Baseline/contrast arms (B0 TTL-only, B1 coarse purge, B2 always-recompute, B3 Zanzibar-like tokens + derived-cache tagging) and prior-work falsification matrix rows | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | New candidate B4 (origin- and purpose-labeled dependency-closure invalidation); new byte-level dispatch interceptor with sealed cancellation log; new source-snapshot recomputation oracle (module-isolated from candidate) |
| PST forensic receipts / insider attack dataset (`synthetic-pst-2027`) | Not used — named only to document the PoPETs–PST separation | None | No | No | No | No — forensic reconstructability score is a different endpoint | Distinct public artifact: `synthetic-popets-2027`; distinct threat model (pre-dispatch future-facing vs post hoc forensic) |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as PoPETs evidence. All PoPETs claims must derive
from this study's own frozen protocol (`research/venue2027/popets/protocols/preregistration.yaml`
at freeze time).

## 4. Secondary-endpoint sharing declaration

Latency, bytes transferred, and rebuild cost appear in several sibling studies. For PoPETs
they are supporting measurements of RQ3 only (conditional cache hit rate and p95 latency
over subject histories), always subordinate to the primary endpoint. Secondary reused
measurements are declared shared context per anti-salami rule 2 and are never headline
evidence; subject-level N is counted by unique subject history, never by number of
dispatches, so no pseudo-replication inflates evidence.

## 5. PoPETs–PST contrast: future-context re-disclosure vs post-hoc forensic reconstruction

`ANTI_SALAMI_REVIEW.md` records PoPETs–PST (future context vs forensic metadata) as a
potential merge/alternative-route pair, and `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`
states the control: *"Distinguish future prompt redisclosure after consent revocation from
post hoc audit-event inference and retention. Different public artifacts and threat
models."* This audit refuses the merge on the following endpoint separation:

- **PoPETs 2027 (this study)** — *pre-dispatch, future-facing*. Question: after a subject
  revokes consent at time `t_r`, does any subsequent outbound model dispatch carry
  forbidden revoked attributes through transitive derived state (prompt-segment caches,
  cached summaries, embedding pointers, retry payloads, fallback transports)? Primary
  endpoint: **revoked-context re-disclosure rate** and attribute-exposure byte count on
  outbound dispatches after `t_r`. Threat model: the system itself as the leak channel;
  the subject as the injured party; control mechanism is dependency-closure invalidation at
  dispatch time. Public artifact: `synthetic-popets-2027`.
- **PST 2027** — *post hoc, forensic*. Question: how reconstructable is forensic evidence
  from minimized, purpose-bound audit receipts after events have already happened, and what
  can an insider infer from retained metadata? Primary endpoint: **forensic
  reconstructability score** over minimized receipts, with an insider attack dataset.
  Threat model: the auditor/inspector as analyst, the insider as attacker; the measurement
  surface is retained audit logs and receipts, not model dispatches. Public artifact:
  `synthetic-pst-2027`.

The two studies measure different quantities on different trace surfaces with different
threat models and different public artifacts. A future-context control that gates outbound
dispatches cannot substitute for a forensic reconstructability analysis of retained audit
events, and vice versa; neither study's evidence can be presented as the other's. Per the
anti-salami matrix, only a demonstrated identity of measured quantity on the same trace
surface would force a merger — that identity does not exist.

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the PoPETs 2027 study, in any section, table, or figure.** They are
background and motivation only. Concretely, this audit refuses: (a) counting any frozen
E15–E22 outcome as a PoPETs result; (b) reusing GovRed (RIVF 2026) or GovMut (SOICT 2026)
frozen outcomes as PoPETs results; (c) reusing the accepted HEALTHINF #97 manuscript's
governance numbers as PoPETs evidence; (d) any "rebranded" presentation of a same E15–E22
outcome as a new independent finding — the negative gate "Same E15–E22 outcome rebranded"
does not occur. Evidence for every PoPETs claim must derive mechanically from this study's
own frozen protocol and the new `synthetic-popets-2027` bundle. Additionally, per the
novelty contract: no retroactive-erasure claim is made anywhere; information already
delivered to any external provider is excluded from every leakage audit, and this
non-retractability is stated prominently in the paper. This refusal is a binding condition
inherited by all downstream PoPETs tasks.

## 7. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test of `GATES/ANTI_SALAMI_REVIEW.md`: (1) different precise research question —
post-revocation dispatch noninterference for cached model contexts across all derivation
paths; (2) different primary endpoint — revoked-context re-disclosure rate, distinct from
GLHS R4's `governed_read_to_proposal_to_write_correctness` and from every sibling endpoint
(§1); (3) independently frozen evaluation design — the new `synthetic-popets-2027` bundle
with a protocol-first, source-disjoint confirmatory holdout; (4) material new contribution —
the origin- and purpose-labeled dependency-closure invalidation algorithm plus a byte-level
dispatch leakage audit with a sealed cancellation log and a module-isolated recomputation
oracle; (5) candid citation duty toward `zanzibar19`, `macaroons14`, `muse`, `openfga`,
`cedar`, `opa`, `fhir5`, `nistabac` (all currently UNVERIFIED in
`_shared/literature_validity_ledger.csv` and therefore mandatory verification targets for
`POPETS-prior`, not pre-approved comparators). Sharing the repository and background methods
with prior work is acceptable; repackaging the same primary experiment is not done here.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving popets — no other 2027
venue shares PoPETs's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
shared document validator `overlap_contract.py --venue popets` passes (all eight sibling
venues named, all five historical comparators named, frozen-refusal present, exactly one
decision). (3) The nine-venue comparison (§1) and five historical comparisons (§2) show
distinct questions and endpoints on every row. (4) The artifact reuse table (§3) shows no
reused raw case IDs, labels, figures, or endpoints; all extension evidence is new. (5) The
closest merge pair PoPETs–PST is refused by the future-context vs post-hoc-forensic endpoint
separation (§5). (6) Frozen E15–E22 outcomes are explicitly not reused as new independent
evidence (§6). No duplicate primary claim or data presented twice as new exists; the pass
gate "PASS or explicit alternative-venue merger" is satisfied by PASS.
