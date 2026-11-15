# PST P01 · Publication and Evidence Isolation Audit (PST-overlap)

- **Task:** `PST-overlap` (Phase P01, venue `pst`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/venue2027/pst/novelty_contract.md`,
  `research/publication_registry.yaml`,
  `research/venue2027/_shared/study_claims.json`.
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the `pst` entry shares no question+endpoint
  pair with any other venue and declares `reuses_archive: []` (log:
  `research/venue2027/proof/logs/PST-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).
- **Document-level validator:** this audit is machine-checked by the shared anti-salami
  validator `research/venue2027/_shared/tools/overlap_contract.py`
  (`overlap_contract.py <this file> --venue pst`, expected exit 0) and by
  `research/venue2027/pst/tests/test_overlap_audit.py`.

## 1. Comparison against all nine 2027 venues

The PST study asks how reconstructable forensic evidence is under purpose-bound audit
minimization: what fraction of legitimate forensic questions (authorization, provenance,
commit-eligibility) remain answerable from minimized receipts across retention stages, and
at what attacker-side metadata exposure. Its primary endpoint is the **forensic
reconstructability score** (registry wording), measured jointly with attacker
linkability/attribute-inference advantage under a compromised read-only audit reader with
auxiliary-data joins. No other 2027 track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with PST? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — commit admission under contention, not retained-audit reconstruction |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — pre-dispatch future-facing control; see §5 for the mandatory PST–PoPETs separation |
| AIME 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level clinical-content quality, no audit-retention surface |
| IFIP SEC 2027 | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — admission of reused receipts at verification, not post-retention forensic reading |
| SACMAT 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — policy-engine decision conformance, not audit-metadata reconstructability |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy, no benchmark run |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — post-crash durable-effect recoverability, different artifact lifecycle |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams, not measurement of retained audit artifacts |
| PST 2027 | Forensic reconstructability under purpose-bound audit minimization | forensic reconstructability score | (self) |

The machine-readable registry (`_shared/publication_overlap_registry.yaml`,
`audit_ok: true`) records `pst` with `research_question: "How reconstructable is forensic
evidence under purpose-bound audit minimization?"`, the endpoint above, dataset
`synthetic-pst-2027`, and `reuses_archive: []`. Pairwise audit findings: none — no
`SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for pst, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; `governed_read_to_proposal_to_write_correctness` | Different question (record-boundary governance binding inside one co-versioned store, not post-retention forensic reconstruction of audit artifacts); R4's frozen E15–E22 protocols measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility — none measures what remains answerable from minimized audit receipts |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; `unauthorized_or_stale_commit_acceptance_and_prohibited_disclosure` | Superficially nearest on the word "governed disclosure" (disclosure→mutation→commit drift across a real boundary); but GovRed measures stale-commit acceptance at the store boundary, not what a compromised audit reader reconstructs from retained receipts. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — PST does not reuse that frozen evidence |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; `mutation_score` | Different endpoint family (mutation-testing adequacy, W8 45-mutant corpus); no mutant score is a PST result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work per anti-salami rule 4; cited as background. Its governance numbers are motivation, never PST evidence |

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every row
below states what PST actually reuses and what is uniquely new:

| Reused artifact | Purpose in PST | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic cohort *concept* (medication/allergy/history/consent domain model) | Domain background only; new subject histories are generated fresh | RQ1–RQ3 context | No — GLHS schedules/attack classes A01–A16 are not executed or re-scored | No | No | No — GLHS endpoints differ from forensic reconstructability score | New `synthetic-pst-2027` bundle: independent synthetic case histories with longitudinal audit trails, ex-ante frozen forensic query set, auxiliary linkage tables, case-family development/confirmatory splits |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No | — (citation only; see §6 refusal) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-revocation prior work | Background | No | No | No | No — stale-commit acceptance is a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN | Named as unrelated prior surface | Background | No | No | No | No — `NOT_RUN`, nothing to reuse | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| PoPETs cached-context disclosure dataset (`synthetic-popets-2027`) | Not used — named only to document the PST–PoPETs separation | None | No | No | No | No — revoked-context re-disclosure rate is a different endpoint | Distinct public artifact: `synthetic-pst-2027`; distinct threat model (pre-dispatch future-facing vs post hoc forensic) |
| RFC 9162 (`ct9162`), Macaroons (`macaroons14`), FHIR AuditEvent/Provenance (`fhir5`), MUSE (`muse`), RATS (`rats9334`), NIST ABAC (`nistabac`), Zanzibar (`zanzibar19`), WHO guidance (`who21`) | Baseline/contrast arms (B1 hash-only digests, B3 RFC 9162-style Merkle log with authorized material retrieval, B2 encrypted full log) and prior-work falsification matrix rows CL-1..CL-9 | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | New candidate B4 (purpose-bound minimized receipt plus retention map); new reconstruction-versus-linkability frontier; adversarial attacker harness with auxiliary joins, module-isolated from B4 |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as PST evidence. All PST claims must derive
mechanically from this study's own frozen protocol and the new `synthetic-pst-2027` bundle
generated after the protocol freeze.

## 4. Secondary-endpoint sharing declaration

Bytes retained, proof-generation latency, and recovery time appear in several sibling
studies. For PST they are supporting measurements of RQ3 only (retained bytes,
proof-generation latency, authorized investigation recovery time per audit-volume and
retention-epoch condition), always subordinate to the primary endpoint. Secondary reused
measurements are declared shared context per anti-salami rule 2 and are never headline
evidence; subject-level N is counted by independent synthetic case history, never by number
of audit events, so no per-event pseudo-replication inflates evidence.

## 5. PST–PoPETs contrast: post-hoc forensic reconstruction vs future-context disclosure

`GATES/ANTI_SALAMI_REVIEW.md` records PoPETs–PST (future context vs forensic metadata) as a
potential merge/alternative-route pair, and `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` states
the control: *"Distinguish future prompt redisclosure after consent revocation from post
hoc audit-event inference and retention. Different public artifacts and threat models."*
This audit refuses the merge on the following endpoint separation:

- **PST 2027 (this study)** — *post hoc, forensic*. Question: how reconstructable is
  forensic evidence from minimized, purpose-bound audit receipts **after events have already
  been committed**, and what can a compromised read-only audit reader infer from retained
  metadata? Primary endpoint: **forensic reconstructability score** over retained artifacts
  at each retention stage, scored against an independent oracle ledger, jointly with
  attacker linkability/attribute-inference advantage. Threat model: the auditor/inspector as
  analyst, the compromised read-only audit reader as attacker combining receipts with
  auxiliary linkage tables; the measurement surface is retained audit logs and receipts, not
  model dispatches. Public artifact: `synthetic-pst-2027`.
- **PoPETs 2027** — *pre-dispatch, future-facing*. Question: after a subject revokes consent
  at time `t_r`, does any subsequent outbound model dispatch carry forbidden revoked
  attributes through transitive derived state (prompt-segment caches, cached summaries,
  embedding pointers, retry payloads, fallback transports)? Primary endpoint:
  **revoked-context re-disclosure rate** and attribute-exposure byte count on outbound
  dispatches after `t_r`. Threat model: the system itself as the leak channel; the subject
  as the injured party; control mechanism is dependency-closure invalidation at dispatch
  time. Public artifact: `synthetic-popets-2027`.

The two studies measure different quantities on different trace surfaces with different
threat models and different public artifacts. A post hoc forensic reconstructability
analysis of retained audit events cannot substitute for a future-context control that gates
outbound dispatches, and vice versa; neither study's evidence can be presented as the
other's. Per the anti-salami matrix, only a demonstrated identity of measured quantity on
the same trace surface would force a merger — that identity does not exist.

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the PST 2027 study, in any section, table, or figure.** They are
background and motivation only. Concretely, this audit refuses: (a) counting any frozen
E15–E22 outcome as a PST result; (b) reusing GovRed (RIVF 2026) or GovMut (SOICT 2026)
frozen outcomes as PST results; (c) reusing the accepted HEALTHINF #97 manuscript's
governance numbers as PST evidence; (d) any "rebranded" presentation of a same E15–E22
outcome as a new independent finding — the negative gate "Same E15–E22 outcome rebranded"
does not occur. Evidence for every PST claim must derive mechanically from this study's own
frozen protocol and the new `synthetic-pst-2027` bundle. Per the novelty contract, the
declared registry status is `reuses_archive: []`, and any E15–E22 outcome re-branded as a
PST result is refused as the negative adversarial control of `PST-overlap`. This refusal is
a binding condition inherited by all downstream PST tasks.

## 7. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test of `GATES/ANTI_SALAMI_REVIEW.md`: (1) different precise research question —
post hoc forensic reconstructability of retained audit events under purpose-bound
minimization; (2) different primary endpoint — forensic reconstructability score, distinct
from GLHS R4's `governed_read_to_proposal_to_write_correctness` and from every sibling
endpoint (§1); (3) independently frozen evaluation design — the new `synthetic-pst-2027`
bundle with an ex-ante frozen forensic query set, an independent oracle ledger the candidate
never imports, and case-family development/confirmatory splits; (4) material new
contribution — the formally defined reconstruction-versus-linkability frontier, the
purpose-bound minimized receipt and retention map (B4) as evaluation instrument (not a new
access-control mechanism, per the novelty contract's access-control boundary), an
adversarial attacker harness with auxiliary joins, and the first quantitative comparison of
minimized receipts against encryption- and transparency-based retention baselines under
equal budget; (5) candid citation duty toward `ct9162`, `macaroons14`, `fhir5`, `muse`,
`rats9334`, `nistabac`, `zanzibar19`, `who21` (all currently UNVERIFIED in
`_shared/literature_validity_ledger.csv` and therefore mandatory verification targets for
`PST-prior`, not pre-approved comparators). Sharing the repository and background methods
with prior work is acceptable; repackaging the same primary experiment is not done here.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving pst — no other 2027
venue shares the question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
shared document validator `overlap_contract.py --venue pst` passes (all eight sibling venues
named, all five historical comparators named, frozen-refusal present, exactly one decision).
(3) The nine-venue comparison (§1) and five historical comparisons (§2) show distinct
questions and endpoints on every row. (4) The artifact reuse table (§3) shows no reused raw
case IDs, labels, figures, or endpoints; all extension evidence is new. (5) The closest
merge pair PST–PoPETs is refused by the post-hoc forensic reconstruction vs future-context
disclosure endpoint separation (§5). (6) Frozen E15–E22 outcomes are explicitly not reused
as new independent evidence (§6). No duplicate primary claim or data presented twice as new
exists; the pass gate "PASS or explicit alternative-venue merger" is satisfied by PASS.
