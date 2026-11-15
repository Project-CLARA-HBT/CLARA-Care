# DIMVA P01 · Publication and Evidence Isolation Audit (DIMVA-overlap)

- **Task:** `DIMVA-overlap` (Phase P01, venue `dimva`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/dimva/novelty_contract.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/publication_registry.yaml`.
- **Executable check:** `research/venue2027/_shared/tools/overlap_contract.py` (the required
  P01 overlap validator) is run against this file; and
  `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`: the `dimva` entry shares no
  question+endpoint pair with any other venue and declares `reuses_archive: []`
  (report: `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`).

## 1. Comparison against all eight sibling 2027 venues

The DIMVA study (GovernanceTrace) asks whether **adaptive authorization-boundary probing
campaigns** — paced, multi-step sequences of purpose hopping, receipt/lineage reuse,
delegation abuse and permission discovery — can be **detected from minimal agent events**
(event kind, scoped actor/tenant/purpose, logical time, payload digest references) while raw
clinical content is never logged and rejection reason codes are masked in the primary
leak-safe test. Its primary endpoint is **probing detection AUC at fixed false-positive budget**
(registry wording), operationalized as campaign-level PR-AUC over independent
attack campaigns with recall at a preregistered false-alarm budget per 1,000 benign sessions
as co-primary summary. None of the eight sibling venues shares that question or endpoint:

| Sibling venue | Question focus | Primary endpoint | Shared with DIMVA? |
|---|---|---|---|
| compsac 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — admission decides whether a write may commit while the system is up; DIMVA never admits or blocks a single request, it detects campaigns over event streams |
| popets 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface for cached AI context after revocation; no detector, no campaign oracle, no false-alarm budget |
| aime 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level recommendation quality on synthetic vignettes; no probing-campaign notion or telemetry detection window |
| ifip_sec 2027 (IFIP SEC) | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — verification-time prevention; contrast formalized in §4 |
| sacmat 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — decision-time conformance divergence between policy-engine implementations, not adversarial multi-step campaign detection from minimized agent events at a fixed false-alarm budget |
| acns 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy with counterexamples; no detector, oracle or benchmark |
| dsn 2027 | Recoverable safety journals under crash fault injection | crash-consistency violation rate after fault injection | No — durable-state crash/recovery semantics over joint write outcomes; no event-stream detection window |
| pst 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc audit inference and metadata retention; DIMVA detects in-stream while raw content and reason codes are withheld |

The machine-readable registry (`_shared/publication_overlap_registry.yaml`, `audit_ok: true`)
records `dimva` with `research_question: "Can adaptive authorization-boundary probing be
detected from minimal agent events?"`, the endpoint above, dataset `synthetic-dimva-2027`,
and `reuses_archive: []`. The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns zero findings involving dimva: no
`SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION`, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness on a single database boundary | Different question (governance binding and admission, not campaign detection). The truly distinct endpoint is stated in `dimva/novelty_contract.md`: GLHS R4's historical E15–E22 evidence attests dispatch-attestation and governance-integrity (admission/prevention) endpoints, and E15–E19 ran on `sqlite:///:memory:` with E20 `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`, so those frozen numbers cannot support event-stream detection claims; DIMVA measures campaign-level PR-AUC at a fixed false-positive budget on independently generated multi-stage traces. DIMVA does not reuse that frozen evidence |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; stale-commit acceptance | Superficially shares the words "governed" and "commit"; but GovRed measures disclosure→mutation→commit drift, not probing-campaign detection over telemetry. `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — that frozen evidence is not counted as a DIMVA result |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score (W8 45-mutant corpus) | Different endpoint family (mutation-testing adequacy); no GovMut mutant score is a DIMVA detection result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `frozen_manifest: NOT_RUN`, no frozen evidence exists to reuse |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`, the AIME–HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work, cited as background per anti-salami rule 4; its governance-protocol correctness numbers are motivation, never DIMVA evidence |

Of the potential merge/alternative-route pairs recorded in `ANTI_SALAMI_REVIEW.md`
(DSN–COMPSAC, PoPETs–PST, IFIP SEC–ACNS, SACMAT–GovMut, AIME–HEALTHINF), none touches
DIMVA's claim surface. The one recorded pair involving this venue is **IFIP SEC–DIMVA
(prevention vs detection)**, resolved in §4 below.

## 3. Artifact reuse table

`reuses_archive: []` is enforced both by the registry declaration and by the executable
audit. Every row states what DIMVA actually reuses and what is uniquely new:

| Artifact | Purpose in DIMVA | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS append-only listener + governance domain model (`services/api/src/clara_api/glhs`) | Engineering substrate / background method only; cited, never counted as evidence | Context for RQ1–RQ3 | No — GLHS schedules, attack classes A01–A16, and case IDs are not executed or re-scored | No | No | No — GLHS endpoints (governed read-to-proposal-to-write correctness) differ from campaign-level probing detection AUC | GovernanceTrace minimal event schema, sequence detector, and independently generated synthetic multi-stage campaign corpus |
| Frozen parent GLHS E15–E22 outcomes | Historical background and motivation only (see §5 statement) | Background | No | No | No | No — dispatch attestation, comparator decision safety, witnesses, state-space checks, transport attacks, provider receipts, novelty models, reproducibility; none measures campaign detection over event streams | — (citation only) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — stale-commit acceptance is a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN records | Cited as related medication-identity work | Background | No | No | No | No — false-clear DDI rate is unrelated | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No | — |
| `agentdojo24`, `toolemu24`, `tauben25`, `injecagent24` (verified ledger ids) | Attack/benchmark context for the claim-to-prior-work falsification matrix in `dimva/novelty_contract.md` | RQ1–RQ2 | No | No | No | No — none defines a campaign-level detection endpoint at a fixed false-positive budget with unseen-family holdout | New B0–B4 baseline arms (counting threshold, temporal rule/FSM, Isolation Forest, gradient-boosted trees, sequence model) under equal data access and equal compute budget, on traces split by attack family and synthetic tenant |
| `sommer10`, `zanzibar19`, `macaroons14` (verified ledger ids) | Motivation for cross-family holdout (environment memorization), and for the verification-time vs detection-over-time boundary | RQ1–RQ3 | No | No | No | No — enforcement/verification mechanisms, not detection endpoints | Sealed campaign-intent oracle (`truth.json`) that never imports candidate or baseline detector code; reason-code masking ablation as a dedicated secondary experiment |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as DIMVA evidence. All DIMVA claims must derive
mechanically from `artifacts/venue2027/dimva/<run_id>/manifest.json` produced by this study's
own frozen protocol.

## 4. DIMVA–IFIP SEC contrast: detection vs prevention

`ANTI_SALAMI_REVIEW.md` records IFIP SEC–DIMVA as a potential merge/alternative-route pair.
This audit refuses the merge on endpoint separation, consistent with
`CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"IFIP/DIMVA: One prevents invalid tokens at
verification, one detects campaigns over time, measured on independent detectors and event
streams."* The same probing campaign is never reused as two independent primary studies.

- **IFIP SEC 2027 (prevention).** Strengthens verification itself: replay-closed
  authorization across purpose, delegation and AI proposal lineage, with consumed-once
  receipts. Unit of analysis is one authorization request/receipt; primary endpoint is
  replay acceptance rate across purpose/delegation lineage; artifacts are the
  receipt/consumed-once mechanism and the replay threat corpus. It decides each request's
  admission at verification time.
- **DIMVA 2027 (detection).** Does not strengthen verification and never decides a single
  request's admission. Unit of analysis is one multi-event campaign; primary endpoint is
  campaign-level PR-AUC at a fixed false-positive budget over event streams; artifacts are
  the GovernanceTrace minimal event schema, the sequence detector and the synthetic campaign
  set, evaluated under data minimization (no raw clinical content, reason codes masked in
  the primary test) with unseen-family holdout.

Four-part distinction per `dimva/novelty_contract.md`: (1) research question — does
verification-time replay closure prevent authorized-looking replay vs can probing campaigns
be detected from telemetry; (2) unit of analysis — one authorization request/receipt vs one
multi-event campaign; (3) primary endpoint — replay acceptance rate vs campaign-level PR-AUC
at a fixed false-positive budget; (4) artifacts — receipt/consumed-once mechanism and replay
threat corpus vs the minimal event schema, detector and synthetic campaign set. A prevention
result at verification time is not a detection result over time, and vice versa; neither
study's evidence can substitute for the other's. Only repository background and governance
vocabulary are shared, and they are cited, not cannibalized.

## 5. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the DIMVA 2027 study, in any section, table, figure, or statistical
test.** They are background and motivation only. This audit refuses: (a) counting any frozen
E15–E22 outcome as a DIMVA detection result — per the anti-salami gate, frozen E15–E22 data,
GovRed results, and GovMut results cannot be counted as any of the nine independent 2027
results — and, symmetrically per the falsification matrix (C8), claiming any DIMVA detection
result as validating the archive's prevention claims; (b) reusing R4 SQLite in-memory
observations as event-stream detection evidence — the source audit
(`SOURCE_AUDIT_2026_11_14.md`) attests E15–E19 backends as `sqlite:///:memory:` and E20 as
`NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`, so those frozen numbers cannot support
PostgreSQL-specific concurrency claims, let alone campaign-detection claims over independent
multi-stage traces; (c) reusing GovRed (RIVF) or GovMut (SOICT) frozen studies as DIMVA
results. Every DIMVA claim must derive mechanically from this study's own frozen protocol
artifacts. This refusal is a binding condition inherited by all downstream DIMVA tasks
(`dimva/novelty_contract.md` §5, "Archive refusal").

## 6. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut/CareGuard, per the five-part
distinction test: (1) the research question itself — adaptive authorization-boundary probing
detection from minimal agent events — is not asked by any sibling or historical study;
(2) the primary endpoint, campaign-level PR-AUC at a preregistered fixed false-positive
budget with recall-at-budget as co-primary summary, is a temporal detection metric no cited
prior work or sibling defines; (3) the evaluation design is independently frozen in
`VENUES/dimva/CASE_MATRIX.md` (independently generated multi-stage traces split by attack
family and synthetic tenant, sealed campaign-intent oracle, preregistered false-alarm
budget, every scientific unit an independent campaign or benign session); (4) material new
artifacts: the GovernanceTrace minimal event schema, the sequence detector, the synthetic
campaign corpus, and the B0–B4 baseline set under equal budget; (5) candid citation of the
closest prior work (agentdojo24, toolemu24, tauben25, injecagent24, sommer10, zanzibar19,
macaroons14) with explicit falsification conditions. Sharing the repository and background
methods with prior work is acceptable; repackaging the same primary experiment is not done
here.

## 7. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving dimva — no other 2027
venue shares DIMVA's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
shared `overlap_contract.py` validator accepts this document against all eight sibling
venues and the five historical comparators. (3) The nine-venue comparison (§1) and five
historical comparisons (§2) show distinct questions and endpoints on every row. (4) The
artifact reuse table (§3) shows no reused raw case IDs, labels, figures, or endpoints; all
extension evidence is new. (5) The IFIP SEC–DIMVA merge pair is declined by endpoint
separation (§4): prevention at verification vs detection over time on independent detectors
and event streams. (6) Frozen E15–E22 outcomes are explicitly excluded as new independent
evidence in both directions (§5), matching the negative gate "Same E15–E22 outcome
rebranded" — which does not occur. No duplicate primary claim or data presented twice as new
exists; the pass gate "PASS or explicit alternative-venue merger" is satisfied by PASS.
