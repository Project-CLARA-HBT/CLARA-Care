# AIME · independently executable study implementation book

**Paper:** Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories

**Proposed contribution:** A paired *two-axis error decomposition* separating unauthorized data use from clinically incorrect permitted recommendations under longitudinal context change, with avoidable-refusal cost reported rather than hidden.

**Literature gap and competing explanation:** MedHELM, HealthBench and clinical safety benchmarks evaluate medical quality; existing governance systems evaluate authorization. A joint longitudinal workflow protocol with independent clinician adjudication may expose the gap between clinically correct advice and *permitted* actions.

**Three research questions**

**RQ1: How often does each method make an action-eligibility mistake versus a clinical-fact omission when medications or consent change during the task?**
**RQ2: Does purpose-aware selective regeneration preserve appropriate task completion while reducing forbidden data use relative to full restart and static context?**
**RQ3: Are effects stable across update types, at least two actual providers, and an independent physician-adjudicated case set?**

**Falsification criterion:** No clinician reviewer or independent original vignettes = no clinical validity claim. If selective regeneration gains no utility over complete refresh, narrow to a descriptive workflow evaluation.

**Method architecture:** Compare four truly matched provider-prompt arms on case histories with independently frozen clinical and policy labels. Reviewers separately rate medical appropriateness and authority of used evidence, blinded to method.

**Planned study population / resources:** Synthetic source-disjoint vignettes with counterfactual pairs: baseline H, medication update, allergy, revocation, unrelated edit, clinical task. Target N determined by pilot variance and planned power; never label small LLM probes clinical trials.

**Independent oracle:** Independent authorized evidence oracle and qualified clinician review; patient-level paired bootstrap/clustered CI.

**Required metrics:** action eligibility error, clinician adjudicated clinical omission, unnecessary refusal, useful authorized completion, token cost, inter-rater reliability

## Strong baselines and purpose

| Arm | Baseline | Scientific role |
|---|---|---|
| B0 | full authorized history, single snapshot | clinical information-rich static baseline |
| B1 | full per-step refresh + current policy filter | strong correctness/privacy control |
| B2 | HealthBench-/MedHELM-informed evaluation rubric for clinical utility | benchmark rubric, not a decision algorithm |
| B3 | static model + output post-filter | common LLM guardrail comparator |
| B4 | proposed selective consent-aware context regeneration | candidate |

All baseline implementations must use pinned real upstream sources if available, fidelity vectors and equal budget. `NOT_RUN_EXTERNAL` is permitted as a transparent status but prevents unsupported comparative claims.

## Phases and execution

- `P01`: 5 tasks; see `PHASES/P01.md`.
- `P02`: 6 tasks; see `PHASES/P02.md`.
- `P03`: 4 tasks; see `PHASES/P03.md`.
- `P04`: 4 tasks; see `PHASES/P04.md`.
- `P05`: 4 tasks; see `PHASES/P05.md`.
- `P06`: 2 tasks; see `PHASES/P06.md`.
- `P07`: 1 tasks; see `PHASES/P07.md`.
- `P08`: 4 tasks; see `PHASES/P08.md`.
- `P09`: 3 tasks; see `PHASES/P09.md`.

Use `python3 scripts/taskctl.py ready --venue aime` to obtain ready tasks. All tasks have individually versioned contracts and sample report schemas in `TASKS/`.

## Evidence and reproducibility contract

- Only synthetic, licensed or openly permitted benchmark datasets. No actual patient records.
- Primary scientific unit is a unique case, independent history, clinical vignette, corpus paper, or campaign as defined by the frozen protocol; never per-event pseudo-replication.
- Development split permits design changes; confirmatory holdout is inaccessible until protocol and analysis freeze.
- Results filenames and claims must derive mechanically from `artifacts/venue2027/aime/<run_id>/manifest.json`.
- Parent GLHS E15–E22 results and accepted HEALTHINF paper are *background*, not new venue experiments.
- Stop on scientific/technical critical failures; report meaningful negative results without hiding them.
