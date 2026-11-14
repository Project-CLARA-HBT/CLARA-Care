# AIME 2027 Novelty Contract — Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories

> **Task:** `AIME-scope` (Phase P01, venue `aime`) · **Contract version:** `1.0.0` · **Status:** PROSPECTIVE research design — no experiment has run and no result is claimed.
> **Dependencies honored:** `SH-claim_overlap` (publication overlap firewall) and `SH-literature_hardening` (verified literature ledger). All prior-work identifiers below resolve to real entries in `research/venue2027/_shared/literature_validity_ledger.csv`, `research/venue2027/_shared/publication_overlap_registry.yaml`, `research/publication_registry.yaml`, or the historical archive in `research/venue2027/_shared/tools/claim_overlap.py`.
> **Falsification rule of the whole contract:** if any row of the matrix in §3 is falsified, the corresponding novelty claim is surrendered and the study is re-scoped or downgraded; negative and equivalence outcomes are reportable results, never failures to be hidden.

## 1. Title and target reader

**Working title:** Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories.

**Target reader:** AIME 2027 reviewers and the medical-informatics audience building and auditing LLM health assistants — clinical informaticians, clinician-evaluators, and health-AI safety engineers who need to know whether a workflow that was correct at task start is still clinically appropriate *and* still permitted after the patient's consent state or medication history changes mid-task. The paper is written for readers who evaluate systems, not for readers building governance protocol internals.

## 2. One-paragraph scope

This study asks a joint longitudinal question that existing instruments split apart: when consent and medication histories change during a clinical AI task, do assistant workflows keep producing actions that are both clinically appropriate and permitted, and what does getting this wrong cost in avoidable refusals? The contribution is a paired **two-axis error decomposition** — separating (A) unauthorized or forbidden evidence use (action-eligibility mistakes against the frozen consent/policy state) from (B) clinically incorrect permitted recommendations (clinician-adjudicated clinical omissions) — on counterfactual synthetic vignette pairs (baseline history, medication update, allergy introduction, consent revocation, unrelated benign edit, clinical task), evaluated across matched provider-prompt arms with an independent authorized-evidence oracle and blinded independent clinician adjudication, reporting the avoidable-refusal cost as a first-class outcome rather than hiding it. Target cohort size is set by pilot variance and a documented power calculation before the confirmatory freeze; small LLM probes are never labeled clinical trials.

## 3. Claim-to-prior-work falsification matrix

Each row states a claimed contribution element, the closest real prior work (registry identifiers), what that prior work establishes, the condition that would falsify the claim, and the surviving distinction. Falsification of any row surrenders that claim.

| # | Claimed contribution element | Closest prior work (real ids) | What prior work establishes | Falsification condition | Surviving distinction |
|---|---|---|---|---|---|
| M1 | Joint longitudinal protocol decomposing action-eligibility errors (forbidden evidence use) from clinician-adjudicated clinical omissions under mid-task change | `medhelm2026`, `cse2026`, `healthbench25` | Broad medical-task quality and safety benchmarks for medical LLMs; physician-authored or physician-consensus scoring of clinical content | A reviewer identifies an existing benchmark that already reports this two-axis decomposition (authorization error vs clinical omission) under changing consent/medication with blinded clinician adjudication | Those benchmarks evaluate medical quality of outputs on stable tasks; none changes consent or medication mid-task, and none adjudicates the *permitted*-action axis separately from the clinical axis |
| M2 | Counterfactual vignette-pair design (baseline H / medication update / allergy / revocation / unrelated benign edit) with frozen clinical and policy labels | `amie2026` | Multivisit conversational disease management with human evaluation across visits | An equivalent paired counterfactual protocol that mutates consent and medication mid-task with independently frozen labels is found in prior literature | The prior work evaluates longitudinal conversations; it does not hold a task fixed and counterfactually mutate its authorization and medication context |
| M3 | Purpose-aware selective consent-aware context regeneration evaluated as a *workflow decision algorithm* on task completion and refusal cost | `healthinf_2026`, `fhir5` | HEALTHINF accepted work contributes a co-versioned governance protocol for admission correctness; FHIR R5 Consent structures consent resources | Governance-only mechanisms are shown to preserve task completion at reduced forbidden use under clinician adjudication — i.e., prior art already covers the workflow-utility endpoint | HEALTHINF's endpoint is governance admission correctness; FHIR is structural interoperability; neither measures clinician-adjudicated clinical appropriateness or avoidable-refusal cost of the end-to-end task |
| M4 | Avoidable-refusal cost on benign unrelated edits reported as a first-class paired outcome | `healthbench25`, `cse2026` | Quality scoring of medical LLM outputs, including calibration and safety rubrics | A prior benchmark reports unnecessary-refusal rates under benign context edits as a paired cost with blinded review | Benchmark rubrics score output quality; they do not operationalize refusal cost against a frozen benign-edit control class |
| M5 | Blinded independent clinician adjudication as the oracle for synthetic workflow safety | `who21` | WHO guidance sets the ethics and clinical-claims boundary for health AI | An existing evaluation protocol already uses blinded clinician adjudication on changing-consent synthetic vignettes with a two-axis rubric | WHO guidance is normative, not an evaluation protocol; it constrains this study's claims rather than pre-empting them |
| M6 | Any quantitative AIME claim at all | `e15_e22_frozen`, `glhs_r4`, `govred_rivf`, `govmut_soict` | Frozen GLHS R4 / GovRed / GovMut evidence covers commit-admission correctness on logical schedules | Any AIME sentence depends on frozen E15–E22, GovRed, or GovMut numbers as its evidence | Those are parent-study archives on a different scientific unit (commit admission, not clinician-adjudicated workflow vignettes); AIME runs new source-disjoint cases (`reuses_archive` is empty) |

**Matrix rule:** M1–M5 are candidate-gap claims to be re-audited by a systematic related-work search before submission (`AIME-prior`); M6 is an absolute refusal (see §7).

## 4. Distinct contribution and distinct primary endpoint

**Distinct contribution.** The contribution centres on counterfactual clinical workflow safety under CHANGING consent and medication histories: the same clinical task re-evaluated after a controlled context mutation, scored on two independent error axes with the refusal cost made visible. This is a measurement-and-adjudication protocol for task-level workflow behavior, not a new governance protocol and not a new medical benchmark.

**Distinct primary endpoint** (registered in `_shared/publication_overlap_registry.yaml`, study `aime`): **unsafe clinical action rate under consent/medication history changes**, operationalized per the anti-overlap matrix as **task-level clinical workflow eligibility and unnecessary refusal** on independently reviewed synthetic vignettes. This endpoint is distinct from every sibling 2027 study: not `forbidden commit rate under dependency-complete schedules` (compsac), not `revoked-context re-disclosure rate` (popets), not `replay acceptance rate across purpose/delegation lineage` (ifip_sec), not `delegation conformance divergence detection rate` (sacmat), not `evidence-boundary coverage matrix` (acns), not `crash-consistency violation rate after fault injection` (dsn), not `probing detection AUC at fixed false-positive budget` (dimva), not `forensic reconstructability score` (pst), and not mutation-score or governance-admission endpoints from the historical archive. The strongest competing explanation this design must defeat: *fresh full-context refresh with a policy filter (or plain output filtering) already achieves the same safety and completion, so the paired decomposition and selective regeneration add nothing.* The baselines and falsification conditions in §5–§6 are built to give that explanation every chance to win.

## 5. Research questions and estimands (exactly three)

### 5.0 Blinded clinician adjudication contract (shared independent-oracle definition)

Applies to every RQ below; deviations void the corresponding clinical-validity statement.

1. **Reviewers.** Two qualified, independent clinicians per case. A candidate-model agent is never a reviewer and never certifies its own labels. **Blinded independent clinician review is required**: with no clinician reviewer there is no clinical validity claim.
2. **Blinding.** Reviewers see the case and the arm output with model arm, provider identity, and method labels removed; presentation order is locked and randomized; reviewers never see each other's ratings before adjudication.
3. **Separate dimensions.** Reviewers rate independently: (i) medical appropriateness of the permitted recommendation, including any clinical omission (axis B); and (ii) authority/eligibility of the evidence used under the frozen consent and medication state (axis A). The rubric is frozen (`AIME-X03`) before any confirmatory run.
4. **Adjudication and uncertainty.** Reviewer disagreement goes to a predefined third-reviewer adjudication path (fixture class AIME-CASE-07). `INDETERMINATE` is a preserved, counted outcome and is never coerced into a pass, a rejection, or a safe failure.
5. **Independence boundary.** Truth labels are derived from the frozen vignette and policy state only; oracle tooling must not import candidate or baseline implementation code (the `SH-independent_oracle` boundary). Inter-rater agreement is reported, not assumed.
6. **Reviewer terms.** Reviewer consent, eligibility, and compensation are frozen before main-case release (`_shared/data_ethics_and_irb.md`).

### RQ1 — Decomposition of error mechanisms under mid-task context change

**Question (blueprint).** How often does each method make an action-eligibility mistake versus a clinical-fact omission when medications or consent change during the task?

- **Primary endpoint:** action eligibility error per independent counterfactual vignette pair, decomposed into axis A (unauthorized/forbidden evidence use against the frozen consent and medication state) and axis B (clinician-adjudicated clinical omission in a permitted recommendation); aggregated as the registered distinct endpoint, unsafe clinical action rate under consent/medication history changes.
- **Strongest competing baseline:** B1 — full per-step refresh + current policy filter, the blueprint's strongest correctness/privacy control. Competing explanation: keeping the whole context fresh every step already minimizes both error axes, so the paired two-axis decomposition adds no decision-relevant signal.
- **Independent oracle:** blinded clinician adjudication contract (§5.0); RQ1-specific targets: per-pair ratings of evidence authority under the post-change consent/medication state (axis A) and of medical appropriateness/omission of the permitted recommendation (axis B).
- **Statistical test:** paired McNemar test on per-pair binary error labels for each axis, with case-family clustered paired bootstrap confidence intervals on the paired risk difference; the independent scientific unit is the vignette pair, never per-event retries.
- **Falsification condition:** B1 is statistically indistinguishable from the candidate B4 on both axes under the margin and alpha frozen before the confirmatory run — then the two-axis decomposition is not decision-relevant for this cohort; the equivalence result is reported as the primary outcome and the mechanism claim is surrendered.

### RQ2 — Utility of purpose-aware selective regeneration

**Question (blueprint).** Does purpose-aware selective regeneration preserve appropriate task completion while reducing forbidden data use relative to full restart and static context?

- **Primary endpoint:** unnecessary-refusal rate on benign-update counterfactual pairs (the avoidable-refusal cost, reported rather than hidden), paired with useful authorized completion rate, at a frozen forbidden-data-use ceiling; token cost is co-reported.
- **Strongest competing baseline:** B3 — static model + output post-filter, the common LLM guardrail comparator, with B0 (full authorized history, single snapshot) as the completion-preserving anchor. Competing explanation: filtering outputs after the fact, or simply supplying the full static authorized history, preserves completion and suppresses forbidden use as well as regenerating context.
- **Independent oracle:** blinded clinician adjudication contract (§5.0); RQ2-specific targets: whether the refusal was clinically unnecessary given the benign edit, and whether completion remained medically appropriate and authorized.
- **Statistical test:** paired McNemar test on unnecessary-refusal labels; case-family clustered paired bootstrap confidence intervals for completion-rate and token-cost differences.
- **Falsification condition:** selective regeneration gains no utility over complete refresh — no statistically supported reduction in unnecessary refusal at equal or better forbidden-use, or completion below the frozen non-inferiority margin — then per the blueprint falsification rule the study narrows to a descriptive workflow evaluation and all superiority language is dropped.

### RQ3 — Robustness across update types, providers, and adjudicated cases

**Question (blueprint).** Are effects stable across update types, at least two actual providers, and an independent physician-adjudicated case set?

- **Primary endpoint:** stability of the RQ1 and RQ2 contrasts across update-type strata (medication update, allergy, revocation, unrelated edit), at least two verified provider families, and the independent physician-adjudicated case set; inter-rater reliability of blinded reviewers reported alongside.
- **Strongest competing baseline:** B2 — HealthBench-/MedHELM-informed evaluation rubric for clinical utility (a benchmark rubric, not a decision algorithm), with B1 re-executed per provider as the strongest decision-algorithm control. Competing explanation: observed effects are artifacts of one rubric or one provider, and rubric-style scoring alone explains the pattern without any workflow mechanism.
- **Independent oracle:** blinded clinician adjudication contract (§5.0) applied to the independently physician-adjudicated case set; the third-reviewer adjudication path and `INDETERMINATE` preservation apply unchanged.
- **Statistical test:** stratified paired contrasts (Cochran–Mantel–Haenszel across update-type and provider strata) with case-family clustered bootstrap confidence intervals; inter-rater reliability via Cohen/Fleiss kappa with confidence intervals.
- **Falsification condition:** effects are not stable — a significant stratum-by-arm interaction, a sign reversal across providers, or reviewer agreement below the frozen kappa threshold after the predefined adjudication path — then no generalization claim is made; instability is reported as the finding.

## 6. Baseline arms (from the AIME blueprint; all must satisfy parity or be marked NOT_RUN_EXTERNAL)

- **B0** — full authorized history, single snapshot: clinical information-rich static baseline.
- **B1** — full per-step refresh + current policy filter: strongest correctness/privacy control.
- **B2** — HealthBench-/MedHELM-informed evaluation rubric for clinical utility: benchmark rubric, not a decision algorithm.
- **B3** — static model + output post-filter: common LLM guardrail comparator.
- **B4** — purpose-aware selective consent-aware context regeneration: the candidate.

Arms are matched on provider, prompt, token budget, and case set with pinned upstream sources where available; a baseline that cannot be faithfully implemented is reported `NOT_RUN_EXTERNAL` and no comparative claim may lean on it. If any baseline ties or dominates the candidate on a primary endpoint, the candidate's superiority claim for that endpoint is explicitly surrendered (`falsification_log`).

## 7. Non-overlap firewall

### 7.1 Differentiation from accepted HEALTHINF work

The accepted HEALTHINF paper (recorded as accepted in `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`) contributes a **governance protocol**: a co-versioned governed read-to-commit admission mechanism whose endpoint is governance/admission correctness. This study contributes **clinical task quality**: whether an end-to-end assistant workflow produces clinically appropriate, permitted actions — and at what unnecessary-refusal cost — when consent and medication histories change mid-task, adjudicated by blinded clinicians. The two differ in research question (governance admission vs clinical workflow behavior), in primary endpoint (admission correctness vs unsafe clinical action rate under consent/medication history changes), and in evidence (this study's new source-disjoint clinician-adjudicated synthetic vignettes; the HEALTHINF evaluation design and results are not reused). HEALTHINF is disclosed and cited as background per `GATES/ANTI_SALAMI_REVIEW.md`; its mechanism is not re-evaluated here and its numbers are never re-presented as AIME results. The pair passes the five-part distinction test recorded for AIME/HEALTHINF in the anti-overlap matrix.

### 7.2 Refusal of frozen archive evidence

**Frozen GLHS R4 experiments E15–E22 are refused as new evidence — in both directions.** The sealed parent-study archives (`e15_e22_frozen`: E15 dispatch attestation, E16 five-way comparator, E17 current-state insufficiency, E18 global-vs-disclosed support, E19 transport serialization attacks, E20 provider receipt study, E21 formal novelty model, E22 hermetic reproduction audit) measure commit-admission correctness on logical schedules — a different scientific unit and question from clinician-adjudicated clinical workflow vignettes. They are **background only**; no AIME sentence may cite them as its own evidence, `reuses_archive` remains empty for study `aime`, and the `SH-claim_overlap` firewall blocks any `ARCHIVE_REUSE_AS_NEW` finding. The same refusal covers `glhs_r4`, `govred_rivf`, and `govmut_soict`. Conversely, this study's vignette results must not flow back into any parent-study claim.

### 7.3 Sibling 2027 venues

Each sibling study shares infrastructure but not the question+endpoint pair; the `SH-claim_overlap` audit over `_shared/study_claims.json` currently reports no salami pair for `aime`. If a future edit makes two studies share question and endpoint, one becomes a transfer target or a joint manuscript instead of two papers.

## 8. Clinical-venue ethics constraints (mandatory statements)

1. **No real PHI.** This study uses **no real PHI** in any form — no real patient records, no real clinical prompts, no live credentials, no re-identifiable derivatives. All cases are **synthetic vignettes only**, drawn from the registered dataset `synthetic-aime-2027` with provenance `generated_synthetic`, synthetic identities and timestamps, and stable source hashes.
2. **Blinded independent clinician review required.** Any clinical-validity statement requires the blinded independent clinician adjudication contract of §5.0, executed by qualified human reviewers; passing unit tests, checksums, or statistical confidence are never substitutes for that review.
3. **Synthetic action correctness is NOT clinical efficacy.** Correct or incorrect synthetic action labels are systems-level engineering outcomes; they establish nothing about diagnosis, treatment, or patient outcomes. No clinical efficacy claim, no diagnostic or treatment performance claim, and no clinical-trial characterization is made or implied anywhere in this study.
4. **Claim discipline.** Every results sentence must trace to a frozen run manifest under `artifacts/venue2027/aime/<run_id>/manifest.json`; unfavorable outcomes are reported; the holdout stays sealed until protocol and analysis freeze.

## 9. Decision

**Decision: GO**

The scope is executable and defensible **conditional on** the GO-side gates: (a) at least two qualified blinded clinicians secured under the §5.0 contract; (b) the source-disjoint vignette generator and frozen two-axis rubric pass independent review before the confirmatory freeze; (c) at least the B1 and B3 baselines reach implementation parity or are honestly marked `NOT_RUN_EXTERNAL` with no comparative claim attached; (d) the holdout remains sealed until protocol and analysis freeze. If (a) or (b) fails, the gate decision must revert to `NO-GO` and the effort is downgraded to a descriptive workflow evaluation or merged into a parent manuscript rather than submitted as an independent clinical-validity paper.
