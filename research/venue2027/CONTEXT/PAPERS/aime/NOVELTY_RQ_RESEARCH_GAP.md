# Research novelty dossier — Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories

**Target:** 06 AIME 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

A paired *two-axis error decomposition* separating unauthorized data use from clinically incorrect permitted recommendations under longitudinal context change, with avoidable-refusal cost reported rather than hidden.

## 2. Gap against strongest published systems

MedHELM, HealthBench and clinical safety benchmarks evaluate medical quality; existing governance systems evaluate authorization. A joint longitudinal workflow protocol with independent clinician adjudication may expose the gap between clinically correct advice and *permitted* actions.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
How often does each method make an action-eligibility mistake versus a clinical-fact omission when medications or consent change during the task?
**Unit / primary endpoint:** independent study unit / action eligibility error. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Does purpose-aware selective regeneration preserve appropriate task completion while reducing forbidden data use relative to full restart and static context?
**Unit / primary endpoint:** independent study unit / action eligibility error. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
Are effects stable across update types, at least two actual providers, and an independent physician-adjudicated case set?
**Unit / primary endpoint:** independent study unit / action eligibility error. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Compare four truly matched provider-prompt arms on case histories with independently frozen clinical and policy labels. Reviewers separately rate medical appropriateness and authority of used evidence, blinded to method.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | full authorized history, single snapshot | clinical information-rich static baseline | NOT_RUN on new study |
| B1 | full per-step refresh + current policy filter | strong correctness/privacy control | NOT_RUN on new study |
| B2 | HealthBench-/MedHELM-informed evaluation rubric for clinical utility | benchmark rubric, not a decision algorithm | NOT_RUN on new study |
| B3 | static model + output post-filter | common LLM guardrail comparator | NOT_RUN on new study |
| B4 | proposed selective consent-aware context regeneration | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| A novel evaluation benchmark for medical LLMs illuminating safety and effectiveness in clinical domains | npj Digital Medicine (2026) | Physician-consensus evaluation quality baseline, not a tested consent-enforcement system | https://www.nature.com/articles/s41746-025-02277-8 |
| Holistic evaluation of large language models for medical tasks with MedHELM | Nature Medicine (2026) | Broad clinical task taxonomy; evaluate workflows, not MCQ clinical recall | https://www.nature.com/articles/s41591-025-04151-2 |
| HealthBench: A benchmark for AI systems and human health | OpenAI 2025 research benchmark | Doctor-authored multi-turn health scoring; no automatic clinical validation | https://openai.com/index/healthbench/ |
| Towards conversational artificial intelligence for disease management | Nature 2026 | Multivisit medical management, human evaluation; not a direct static record benchmark | https://doi.org/10.1038/s41586-026-10764-5 |
| FHIR R5 Consent, AuditEvent, Provenance resources | HL7 FHIR specification | Structure / interoperability only; FHIR compliance is not clinical safety | https://hl7.org/fhir/R5/ |
| Ethics and Governance of Artificial Intelligence for Health | World Health Organization | Ethics, purpose and clinical claims boundary | https://www.who.int/publications/i/item/9789240029200 |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Synthetic source-disjoint vignettes with counterfactual pairs: baseline H, medication update, allergy, revocation, unrelated edit, clinical task. Target N determined by pilot variance and planned power; never label small LLM probes clinical trials.

**Independent oracle:** Independent authorized evidence oracle and qualified clinician review; patient-level paired bootstrap/clustered CI.

**Experimental measurements:** action eligibility error; clinician adjudicated clinical omission; unnecessary refusal; useful authorized completion; token cost; inter-rater reliability.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

No clinician reviewer or independent original vignettes = no clinical validity claim. If selective regeneration gains no utility over complete refresh, narrow to a descriptive workflow evaluation.

**Feasibility risk:** High dependency on physician reviewers, model access costs, and exact clinical statements. Short paper only if results and validation adequate.

## 9. Reviewer objections to anticipate

- Strong prior work may already implement the mechanism; require a distinguishing observation from the strongest baseline.
- Benchmark and baseline adaptations may alter threat model or semantics; validate equivalence using official examples and an independent oracle.
- Synthetic-data efficacy may not transfer to clinical settings or adversarial deployments; report domain shift and a negative generalization test.
- Checksums and passing unit tests do not prove the comparative claim or its statistical power.
- Existing GLHS/HEALTHINF/RIVF/SOICT evidence may overlap; independently define contribution, results and publication relationship.

# Cross-study integrity rules

- **Status:** prospective research; source code and publication package are not experimental evidence.
- **Clinical separation:** Synthetic data is not clinical validation; no real patients, live medical actions, or unverifiable provider output.
- **Source of truth:** Git SHA, immutable protocol freeze and raw JSONL must be consistent; checksums do not prove backend truthfulness or design novelty.
- **Real baselines:** Literature references are not executable baselines by themselves. Original external code/adapter must run, or status is NOT_RUN_EXTERNAL (not a weak substitute).
- **Priority:** a strong negative result or equivalence with prior art is more publishable than false superiority.
- **Paper integrity:** Verify corresponding author status, policies on generative AI, author anonymity, copyright and fees before submission. Do not send overlapping contributions to multiple venues at the same time.

