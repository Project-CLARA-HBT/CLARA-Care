# AIME P01 · Publication and Evidence Isolation Audit (AIME-overlap)

- **Task:** `AIME-overlap` (Phase P01, venue `aime`, priority `P0`)
- **Signature:** `audit(study) -> OverlapDecision`
- **Pass gate:** `PASS` or an explicit alternative-venue merger.
- **Inputs read before this audit:** `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`,
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
  `research/venue2027/_shared/publication_overlap_registry.yaml`,
  `research/venue2027/aime/novelty_contract.md`,
  `research/publication_registry.yaml`.
- **Executable check:** `research/venue2027/_shared/tools/claim_overlap.py` was run against
  `research/venue2027/_shared/study_claims.json`; the aime entry shares no question+endpoint
  pair with any other venue (log:
  `research/venue2027/proof/logs/AIME-overlap.claim_overlap.log`, report:
  `research/venue2027/proof/SH-claim_overlap.json`, status `PASS`, `audit_ok: true`).
- **Document gate:** this audit is validated by
  `research/venue2027/_shared/tools/overlap_contract.py --venue aime`
  (log: `research/venue2027/proof/logs/AIME-overlap.validator.log`, `ok: true`).

## 1. Comparison against all nine 2027 venues

The AIME study asks a joint longitudinal question: when consent and medication histories
change during a clinical AI task, do assistant workflows keep producing actions that are
both clinically appropriate and permitted, and what does getting this wrong cost in
avoidable refusals? Its primary endpoint is **unsafe clinical action rate under
consent/medication history changes** (registry wording), decomposed into axis A
(action-eligibility errors against the frozen consent/policy state) and axis B
(clinician-adjudicated clinical omissions in permitted recommendations), with the
avoidable-refusal cost on benign edits reported as a first-class paired outcome. No other
2027 track shares that question or endpoint:

| Venue | Question focus | Primary endpoint | Shared with AIME? |
|---|---|---|---|
| COMPSAC 2027 | Dependency-complete optimistic admission for concurrent clinical AI writes | forbidden commit rate under dependency-complete schedules | No — concurrent-write admission correctness, not task-level clinical workflow quality |
| PoPETs 2027 | Revocation-complete future-disclosure control with caches | revoked-context re-disclosure rate | No — privacy surface after revocation, no clinician-adjudicated workflow endpoint |
| IFIP SEC 2027 (`ifip_sec`) | Replay-closed authorization across purpose/delegation/lineage | replay acceptance rate across purpose/delegation lineage | No — token/replay admission, not clinical task quality |
| SACMAT 2027 | Temporal conformance testing across policy engines | delegation conformance divergence detection rate | No — policy decision conformance, not clinical appropriateness |
| ACNS 2027 (SoK) | Evidence boundaries of attestation in tool-using AI | evidence-boundary coverage matrix | No — systematic literature taxonomy, no benchmark run |
| DSN 2027 | Recoverable safety journals under crash/fault injection | crash-consistency violation rate after fault injection | No — durable-state recoverability, not clinical workflow behavior |
| DIMVA 2027 | Detecting adaptive authorization-boundary probing | probing detection AUC at fixed false-positive budget | No — detection over event streams, not clinical task quality |
| PST 2027 | Forensic reconstructability under audit minimization | forensic reconstructability score | No — post hoc forensic inference, not workflow adjudication |
| AIME 2027 | Counterfactual clinical workflow safety under changing consent/medication history | unsafe clinical action rate under consent/medication history changes | (self) |

The machine-readable registry
(`_shared/publication_overlap_registry.yaml`, `audit_ok: true`) records `aime` with
`research_question: "Does counterfactual clinical workflow safety under changing consent
and medication history reduce unsafe recommendations?"`, the endpoint above, dataset
`synthetic-aime-2027`, and `reuses_archive: []`. Pairwise audit findings: none — no
`SALAMI_SAME_QUESTION_AND_ENDPOINT`, no `SHARED_PRIMARY_ENDPOINT`, no
`SHARED_RESEARCH_QUESTION` for aime, and no `ARCHIVE_REUSE_AS_NEW`.

## 2. Comparison against historical GLHS R4 / GovRed / GovMut / CareGuard / HEALTHINF

| Historical study | Question / endpoint | Overlap verdict |
|---|---|---|
| GLHS R4 (`glhs-journal`) | Co-versioned disclosure-to-commit binding; governed read-to-proposal-to-write correctness | Different scientific unit: commit admission on logical schedules, not clinician-adjudicated clinical workflow vignettes. R4's prospective protocols E15–E22 measure dispatch attestation, comparator architecture, insufficiency witnesses, support separation, transport attacks, provider receipts, novelty models, reproducibility — none measures unsafe clinical action rate under consent/medication history changes |
| GovRed / RIVF 2026 (`govred-rivf-2026`) | Mutations after governed disclosure invalidating a later commit; unauthorized/stale commit acceptance | Different question (disclosure→mutation→commit drift across the real boundary); AIME does not reuse that frozen evidence and measures no commit acceptance |
| GovMut / SOICT 2026 (`assurance-soict-2026`) | Which governance faults survive which testing strategies; mutation score | Different endpoint family (mutation testing adequacy, W8 45-mutant corpus); no mutant score is an AIME result |
| CareGuard-VN (`careguard-vn`) | Source-bound medication identity gating reducing false-clear DDI conclusions | Unrelated surface (DDI screening identity); `NOT_RUN`, no frozen evidence exists to reuse; AIME measures no DDI false-clear rate |
| HEALTHINF 2026 (#97, accepted) | Co-versioned governance protocol for read-to-commit admission correctness | Disclosed as prior/accepted work and cited as background; the dedicated contrast is §3 — its mechanism is not re-evaluated here and its numbers are never re-presented as AIME results |

## 3. AIME–HEALTHINF contrast: clinical task quality vs governance protocol

`ANTI_SALAMI_REVIEW.md` records AIME–HEALTHINF (clinical task quality vs governance
protocol) as a potential merge/alternative-route pair. This audit refuses the merge on
question, endpoint, and evidence separation, consistent with
`CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`: *"AIME/HEALTHINF: AIME clinical workflow task
validity, not resubmitting co-versioned governance protocol or prior synthetic correctness
numbers."*

- **HEALTHINF 2026 (accepted)** contributes a **governance protocol**: a co-versioned
  governed read-to-commit admission mechanism. Its endpoint is governance/admission
  correctness — whether a write is admitted against the co-versioned consent/policy state.
  It is a systems mechanism paper; it does not adjudicate whether the *content* of an
  assistant's recommendation remains clinically appropriate, and it reports no
  unnecessary-refusal cost.
- **AIME 2027** contributes **clinical task quality under changing consent/medication
  history**: the same clinical task re-evaluated after a controlled counterfactual context
  mutation (baseline history, medication update, allergy introduction, consent revocation,
  unrelated benign edit), scored on two independent error axes (axis A authorization,
  axis B clinician-adjudicated clinical appropriateness) by blinded independent clinicians,
  with the avoidable-refusal cost made visible. AIME builds no admission mechanism and
  re-evaluates none; the HEALTHINF evaluation design and results are not reused.

A governance-admission result is not a clinician-adjudicated workflow-quality result, and
vice versa. Neither study's evidence can substitute for the other's; the pair passes the
five-part distinction test (different question, different primary endpoint, independently
frozen evaluation design, material new contribution, candid citation). Should the two
studies ever collapse onto one question+endpoint pair, HEALTHINF remains the accepted prior
work and AIME becomes a transfer target or an expanded joint manuscript rather than a
second paper.

## 4. Artifact reuse table

`reuses_archive: []` is enforced both by declaration and by the executable audit. Every row
below states what AIME actually reuses and what is uniquely new:

| Reused artifact | Purpose in AIME | RQ | Raw case IDs reused? | Labels reused? | Figures reused? | Endpoint shared? | Unique extension evidence (new, this study) |
|---|---|---|---|---|---|---|---|
| GLHS synthetic cohort *concept* (medication/allergy/history/consent domain model) | Domain background only; new source-disjoint vignettes are generated fresh under `synthetic-aime-2027` | RQ1–RQ3 context | No — GLHS schedules/attack classes are not executed or re-scored | No | No | No — GLHS endpoints differ from unsafe clinical action rate | New counterfactual vignette-pair families (baseline history, medication update, allergy introduction, consent revocation, unrelated benign edit) with frozen clinical and policy labels |
| R4 E15–E22 protocol *titles* | Cited as prior-work context in the novelty contract | Background | No | No | No | No | — (citation only; see §6 refusal) |
| GovRed frozen manifest (`2026-08-17-rivf-final-003`) | Cited as closest governed-commit prior work | Background | No | No | No | No — GovRed's stale-commit acceptance is a different surface | — |
| GovMut W8 45-mutant corpus | Cited as testing-adequacy prior work | Background | No | No | No | No — mutation score is a different endpoint family | — |
| CareGuard-VN manuscript draft | Cited as DDI-screening identity background | Background | No | No | No | No — `NOT_RUN`, no frozen evidence exists | — |
| HEALTHINF #97 accepted manuscript | Cited, disclosed (anti-salami rule 4) | Background | No | No | No | No — governance admission correctness, not clinical task quality | — |
| MedHELM (`medhelm2026`), HealthBench (`healthbench25`), CSE (`cse2026`) rubrics | Baseline arm B2 comparator (benchmark rubric, not a decision algorithm) | RQ1–RQ3 | No | No | No | No — these are comparators, not reused results | New arms B0–B4 on matched provider-prompt pairs; new two-axis rubric `AIME-X03`; new independent authorized-evidence oracle |
| FHIR R5 Consent (`fhir5`) | Structural consent vocabulary background | Background | No | No | No | No — interoperability structure, not an evaluation | — |

No manuscript section text, raw case IDs, labels, figures, or primary endpoint from any
historical or sibling 2027 study is reused as AIME evidence. All AIME claims must derive
from `artifacts/venue2027/aime/<run_id>/manifest.json` produced by this study's own frozen
protocol.

## 5. Unique extension evidence summary

Material new contributions beyond GLHS/HEALTHINF/GovRed/GovMut, per the five-part
distinction test: (1) a joint longitudinal protocol with a paired two-axis error
decomposition (axis A unauthorized evidence use vs axis B clinician-adjudicated clinical
omission) under mid-task consent/medication change — no prior benchmark reports this
decomposition; (2) counterfactual vignette-pair design with independently frozen clinical
and policy labels, source-disjoint from every prior corpus; (3) the avoidable-refusal cost
on benign unrelated edits as a first-class paired outcome; (4) blinded independent
clinician adjudication with a predefined third-reviewer path and preserved `INDETERMINATE`
outcomes; (5) matched baseline arms B0–B4 including the strongest competing explanations
(full per-step refresh plus policy filter; static model plus output post-filter) with
pre-registered falsification conditions. Sharing the repository and background methods with
prior work is acceptable; repackaging the same primary experiment is not done here. Per
`PREVIOUS_ANTI_OVERLAP_MATRIX.md`, AIME is one of the three priority independent papers
(together with COMPSAC and PoPETs) if resources allow only three.

## 6. Frozen E15–E22 refusal (mandatory statement)

**The frozen E15–E22 outcomes from the parent GLHS R4 study are NOT reused as new
independent evidence in the AIME 2027 study, in any section, table, or figure.** They are
background and motivation only. Concretely, this audit refuses: (a) counting any frozen
E15–E22 outcome as an AIME result; (b) importing commit-admission, dispatch-attestation, or
transport-attack numbers as clinical workflow evidence — they measure a different
scientific unit; (c) reusing GovRed (RIVF), GovMut (SOICT), or CareGuard-VN frozen studies
as AIME results. Evidence for every AIME claim must derive mechanically from this study's
own frozen protocol artifacts; `reuses_archive` remains empty for study `aime`, and the
`SH-claim_overlap` firewall blocks any `ARCHIVE_REUSE_AS_NEW` finding. Conversely, this
study's vignette results must not flow back into any parent-study claim. This refusal is a
binding condition inherited by all downstream AIME tasks (`novelty_contract.md` §7.2).

## 7. Synthetic-only and no-clinical-efficacy language (mandatory statements)

1. **Synthetic-only.** This study uses **synthetic vignettes only** — the registered
   dataset `synthetic-aime-2027` with provenance `generated_synthetic`, synthetic
   identities and timestamps, and stable source hashes. **No real PHI** is used in any
   form: no real patient records, no real clinical prompts, no live credentials, no
   re-identifiable derivatives.
2. **No clinical efficacy claim.** Synthetic action correctness is NOT clinical efficacy.
   Correct or incorrect synthetic action labels are systems-level engineering outcomes;
   they establish nothing about diagnosis, treatment, or patient outcomes. No clinical
   efficacy claim, no diagnostic or treatment performance claim, and no clinical-trial
   characterization is made or implied anywhere in this study.
3. **Blinded independent clinician review required.** Any clinical-validity statement
   requires the blinded independent clinician adjudication contract of
   `novelty_contract.md` §5.0, executed by qualified human reviewers; passing unit tests,
   checksums, or statistical confidence are never substitutes for that review.

## 8. Decision

Decision: PASS

**Justification.** (1) The executable `claim_overlap.py` audit over
`_shared/study_claims.json` returns ok with zero findings involving aime — no other 2027
venue shares AIME's question+endpoint pair, and no `ARCHIVE_REUSE_AS_NEW` exists. (2) The
nine-venue comparison (§1) and five historical comparisons (§2) show distinct questions and
endpoints on every row. (3) The AIME–HEALTHINF merge pair is refused by explicit
question/endpoint/evidence separation (§3). (4) The artifact reuse table (§4) shows no
reused raw case IDs, labels, figures, or endpoints; all extension evidence is new. (5)
Frozen E15–E22 outcomes are explicitly not reused as new independent evidence (§6),
matching the negative gate "Same E15–E22 outcome rebranded" — which does not occur. (6)
The study is synthetic-only and makes no clinical efficacy claim (§7). No duplicate primary
claim or data presented twice as new exists; the pass gate "PASS or explicit
alternative-venue merger" is satisfied by PASS.
