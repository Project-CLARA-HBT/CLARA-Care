# ACNS P01 · Publication and Evidence Isolation Audit (ACNS-overlap)

- **Task:** `ACNS-overlap` (Phase P01, venue `acns`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Paper:** *SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems*
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/venue2027/_shared/study_claims.json`,
  `research/venue2027/acns/novelty_contract.md` (§5 non-overlap declaration, Decision GO),
  `research/venue2027/acns/threat_model.md`,
  `research/publication_registry.yaml`,
  `research/venue2027/CONTEXT/SOURCE_AUDIT_2026_11_14.md`.
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the acns entry shares no
  question+endpoint pair with any other venue (log:
  `research/venue2027/proof/logs/ACNS-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).
- **Document gate:** this audit validates against the shared overlap-audit contract
  `research/venue2027/_shared/tools/overlap_contract.py` (`OVERLAP_AUDIT_VERSION 1.0.0`)
  via `overlap_contract.py research/venue2027/acns/overlap_audit.md --venue acns`
  (log: `research/venue2027/proof/logs/ACNS-overlap.validator.log`).

## 1. Comparison against all nine 2027 venues

The ACNS study is a **Systematization of Knowledge**: it asks what the attestation
evidence published in tool-using AI systems actually supports, and populates a
pre-registered evidence-boundary coverage matrix (six evidence classes: assembly, egress,
transport acknowledgment, provider-attested receipt, execution trace, semantic
consumption) by extraction from a 2019–2026 literature corpus, double-coded by independent
human raters with mechanized counterexample witnesses. Its primary endpoint is the
**evidence-boundary coverage matrix** (registry wording), with inter-rater Cohen's κ,
ambiguous-claim fraction, and counterexample reproduction rate as co-endpoints. It runs no
benchmark, trains no detector, admits no commits, and evaluates no runtime system. No
other 2027 track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with ACNS? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — transactional runtime benchmark; ACNS runs no system, measures no commits |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy re-disclosure over prompts/caches; ACNS has no cache or disclosure surface |
| AIME 2027 | Counterfactual clinical workflow safety under changing history | unsafe clinical action rate | No — task-level recommendation quality; ACNS claims no clinical or recommendation result (novelty contract F5) |
| SACMAT 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — cross-engine policy decision conformance; ACNS codes literature, not policy engines |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — crash recoverability; ACNS injects no faults and journals nothing |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams (§4 contrast); ACNS reports no detection metric |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc forensic inference; ACNS performs no forensic reconstruction |
| IFIP SEC 2027 | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — new mechanism vs SoK (§3 contrast); ACNS proposes no mechanism |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | (self) |

The machine-readable registry (`_shared/publication_overlap_registry.yaml`,
`audit_ok: true`) records `acns` with `research_question: "What are the evidence
boundaries of attestation in tool-using AI systems (SoK)?"`, the endpoint above, dataset
`synthetic-acns-2027`, and `reuses_archive: []`. Pairwise audit findings: none — no
`SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for acns, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness | Different question (runtime governance binding, not literature evidence semantics). R4's prospective protocols E15–E22 measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility — none is a double-coded corpus analysis of published attestation claims. GLHS R4 E15/E20 rows additionally carry unreproduced `sqlite:///:memory:` backends and `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE` receipts (source audit 2026-11-14), so no frozen GLHS number is even citable as a claim instance in the ACNS matrix |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; unauthorized/stale commit acceptance | Different surface entirely (disclosure→mutation→commit drift across the real boundary). `overlap_status: same-frozen-evidence; second-venue-requires-material-extension` — ACNS does not reuse that frozen evidence; GovRed measures no attestation claim semantics and contributes no corpus case |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score | Different endpoint family (mutation testing adequacy, W8 45-mutant corpus); no mutant score is an ACNS result and no W8 fault is an ACNS corpus case |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `frozen_manifest: NOT_RUN`, no frozen evidence exists to reuse; medication-identity claims are outside the ACNS attestation-evidence lattice |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol companion (per `PREVIOUS_ANTI_OVERLAP_MATRIX.md`: AIME/HEALTHINF separation is "clinical task quality vs governance protocol") | Disclosed as prior/accepted work and cited as background per anti-salami rule 4, never silently cannibalized. Its governance-correctness numbers are motivation for why attestation overclaims matter; they are not coded as ACNS corpus results supporting the SoK's own claims |

The potential merge/alternative pairs recorded in `ANTI_SALAMI_REVIEW.md` that do not
involve ACNS (DSN–COMPSAC, PoPETs–PST, SACMAT–GovMut, AIME–HEALTHINF) do not touch the
ACNS claim surface; the pairs that do are resolved in §3 and §4.

## 3. IFIP SEC contrast: mechanism vs SoK evidence-boundary taxonomy

`ANTI_SALAMI_REVIEW.md` records **IFIP SEC–ACNS (mechanism vs SoK)** as a potential
merge/alternative-route pair, and `PREVIOUS_ANTI_OVERLAP_MATRIX.md` fixes the control:
*"IFIP/ACNS: One is replay-resistant admission, one is SoK bibliographic taxonomy;
literature SoK must be independent of self-referential performance results."* This audit
refuses the merge on contribution-class separation:

- **IFIP SEC 2027** is a **new-mechanism** study: replay-closed authorization across
  purpose, delegation, and AI proposal lineage, evaluated by executed adversarial
  schedules (`synthetic-ifip_sec-2027`) on the candidate mechanism vs baselines; its
  primary endpoint is the replay acceptance rate across purpose/delegation lineage — a
  property of the mechanism's admission decisions.
- **ACNS 2027** is a **SoK**: it proposes no mechanism, no protocol, no detector, and no
  attestation scheme (novelty contract §1). Its evaluation object is **the published
  literature's claim–evidence structure**, coded against the extended lattice with
  independently adjudicated human coders; its witnesses demonstrate where existing
  evidence semantics break — they are falsification instruments, not deployable
  enforcement. ACNS consumes **zero** IFIP SEC experimental inputs: the
  attestation-adjacent IFIP receipt constructs appear only as cited related work and,
  where relevant, as corpus items coded exactly like any other published system
  (novelty contract §5.2). Conversely, the SoK's coverage matrix is never presented as
  evidence of the IFIP mechanism's effectiveness.

A taxonomy of what published evidence proves is not a replay-resistant admission
decision, and vice versa. Neither study's evidence can substitute for the other's.

## 4. DIMVA contrast: detection vs evidence-semantics mapping

`ANTI_SALAMI_REVIEW.md` records **IFIP SEC–DIMVA (prevention vs detection)**; ACNS is
orthogonal to both because it is neither prevention nor detection but **evidence-semantics
mapping**. `PREVIOUS_ANTI_OVERLAP_MATRIX.md` sets DIMVA's conflict to check as the "IFIP
rejection vs detection distinction" — ACNS sits outside it:

- **DIMVA 2027** (GovernanceTrace) is a **detection** study: campaign-level probing
  detection PR-AUC at a fixed false-alarm budget, from minimal agent event telemetry, with
  held-out attacker families, a telemetry detector, and a synthetic campaign set
  (`synthetic-dimva-2027`).
- **ACNS 2027** has **no detector, no training data, no event-stream evaluation, and no
  detection metric**. It never sees a telemetry stream; its units of analysis are
  extracted claims from published papers, not agent events. No ACNS counterexample
  witness is a detection mechanism, no witness reports a PR-AUC/FPR-style rate as a
  defense, and no DIMVA result may populate the ACNS coverage matrix (threat model
  preamble cross-study firewall).

## 5. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every
row below states what ACNS actually reuses and what is uniquely new:

| Reused artifact | Purpose in ACNS | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic 64-subject cohort *concept* (medication/allergy/history/consent domain model) | Motivating context only (why attestation overclaims matter in health AI) | RQ1–RQ3 motivation | No — GLHS schedules and attack classes A01–A16 are not executed, re-scored, or cited as ACNS evidence | No | No | No — GLHS endpoints (invalid admission, transport rejection, checksum concordance) are not the coverage matrix | Pre-registered 2019–2026 corpus + frozen extraction manual (ACNS-X05); extended six-class evidence-to-claim lattice |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No — see §6 refusal; E15–E22 outcomes are never presented as ACNS results | — (citation only) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — unauthorized/stale commit acceptance is a different endpoint family | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN registry entry | Disclosed as NOT_RUN related work | Background | No | No | No | No — no frozen CareGuard evidence exists at all | — |
| HEALTHINF #97 accepted manuscript | Cited and disclosed (anti-salami rule 4) | Background | No | No | No | No — co-versioned governance protocol, not corpus coding | — |
| RFC 9334/RATS (`rats9334`), W3C PROV / FHIR R5 (`fhir5`), AgentDojo (`agentdojo24`), ToolEmu (`toolemu24`), tau-bench (`tauben25`), RFC 9162 (`ct9162`) | Baselines B0–B3: normative attestation taxonomy, retrospective lineage, benchmark observability categories, generic-coding comparator arm | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | Coverage of published AI systems against the **extended** axes (tool dispatch, provider receipt, execution trace, semantic consumption) that B0/B1/B2 do not enumerate |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as ACNS evidence. All ACNS claims must derive
from `artifacts/venue2027/acns/<run_id>/manifest.json` produced by this study's own frozen
protocol (pre-registered corpus, published extraction rules, adjudicated selection
ledger).

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the ACNS 2027 study, in any section, table, figure, or corpus
row.** They are background and motivation only. Concretely, this audit refuses: (a)
counting any frozen E15–E22 outcome as an ACNS result or as a corpus "system" case; (b)
rebranding E15–E22 as the SoK's empirical basis — per
`SOURCE_AUDIT_2026_11_14.md`, historical E15–E19 runs attested `sqlite:///:memory:`
backends and E20 provider receipts were `NOT_RUN_PROVIDER_ATTESTATION_UNAVAILABLE`, so
these historical-frozen rows are **unreproduced mixed-version evidence** and are excluded
from any ACNS claim under the execution contract's "no claim derived from unreproduced,
mixed-version or historical-frozen evidence" rule; (c) reusing GovRed (RIVF), GovMut
(SOICT), or CareGuard frozen studies as ACNS results; (d) citing the accepted HEALTHINF
paper's numbers as independently generated ACNS evidence. Evidence for every ACNS claim
must derive mechanically from this study's own frozen protocol artifacts. This refusal is
a binding condition inherited by all downstream ACNS tasks (`novelty_contract.md` §5.1).

## 7. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test: (1) the pre-registered, reproducibly extracted **evidence-to-claim
lattice** covering six evidence classes (assembly, egress, transport acknowledgment,
provider-attested receipt, execution trace, semantic consumption) with observation/trust
axes that RFC 9334, PROV/FHIR, and AgentDojo/ToolEmu categories do not enumerate; (2) the
mechanically enumerated **evidence-boundary gap register** (G1–G9: transport-ACK⇒processed,
receipt⇒executed, trace⇒committed, signature⇒context, mint-valid⇒rely-valid,
timestamp⇒ordering, Ln⇒Ln+1, P1⇒P2 authority, published⇒supported) with paired
clean/adversarial rows; (3) the **counterexample-witness gallery** (ACNS-X07) as
falsification instruments for implication pairs, with verdicts frozen before execution;
(4) published extraction rules and an independently adjudicated study-selection ledger
with dual human coding (κ) and third-party adjudication; (5) new `synthetic-acns-2027`
coding fixtures under the ACNS-CASE contract. Sharing the repository and background
methods with prior work is acceptable; repackaging the same primary experiment is not
done here — and the SoK framing itself is the guard: nothing here is claimed as a new
mechanism, protocol, detector, or benchmark.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving acns — no other 2027
venue shares ACNS's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
nine-venue comparison (§1) and five historical comparisons (§2) show distinct questions
and endpoints on every row. (3) The IFIP SEC merge pair (mechanism vs SoK) is refused by
contribution-class separation (§3) and the DIMVA prevention/detection axis is shown
orthogonal (§4). (4) The artifact reuse table (§5) shows no reused raw case IDs, labels,
figures, or endpoints; all extension evidence is new. (5) Frozen E15–E22 outcomes are
explicitly not reused as new independent evidence (§6), matching the negative gate "Same
E15–E22 outcome rebranded" — which does not occur. No duplicate primary claim or data
presented twice as new exists; the pass gate "PASS or explicit alternative-venue merger"
is satisfied by PASS.
