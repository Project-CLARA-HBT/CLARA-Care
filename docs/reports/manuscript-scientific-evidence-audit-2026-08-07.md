# Scientific-evidence audit — CLARA-Care manuscript (2026-08-07)

> **Q3 addendum (2026-08-08).** The frozen GLHS structural protocol is
> documented in `evaluation/glhs_q3/` and its claim boundary in
> `docs/reports/glhs-q3-claim-to-evidence-matrix-2026-08-08.md`. In addition to
> the historical v2 synthetic run, separate development structural runs exist
> for MIMIC-IV Demo, MIMIC-IV-ED Demo and a supplied Synthea FHIR STU3 archive
> (15,877 salted cases from a complete 1,594,095-bundle scan; summary SHA-256
> `8f8f1959af433ff09b2bb821b6679e53fd41849790e952527a249cbb5638a56d`).
> Each explicitly has `final_score_released=false`. They test only predeclared
> structural perturbation oracles; they do **not** provide clinical validation,
> an independent sealed holdout, provider/model evaluation, clinician review or
> patient-level outcome evidence.

## Scope and method

This audit reviews the latest manuscript, `THT FINAL _ CLARA Care.docx`, against
the peer-review file `Major Weaknesses Critical.txt` and the repository revision
`524907ccc59ff1677e22e48990620fd014810d13`. It treats checked-in source,
versioned evaluation manifests, generated evaluation artifacts, and executable
tests as evidence of implemented software behaviour only. It does **not** infer
clinical safety, clinical usefulness, diagnostic performance, real-world
workflow benefit, cost, latency, or external validity from those materials.

## Verified evidence state

| Class | Repository evidence | Permitted conclusion | Prohibited conclusion |
| --- | --- | --- | --- |
| Implemented software controls | API/ML/web source and contract tests; governed task-contract manifest | The corresponding mechanism is implemented or configured in this revision. | The mechanism is clinically safe, effective, complete, or used in practice. |
| Newly generated structural result | `python3 -m evaluation.clara_eval.run --config evaluation/configs/smoke.yaml --output artifacts/clara-eval-vn/smoke` on 2026-08-06T19:25:39Z | All 9 declared synthetic fixtures passed checksum/count-manifest validation (9/9; Wilson 95% interval 0.701–1.000). | Any product-quality, clinical, latency, cost, usability, or external-validation result. |
| Configured but not executed | `artifacts/clara-eval-vn/smoke/model-manifest.json` | Versioned task contracts and prompt versions were captured. | A provider/model ran with that configuration or attained a quality result. |
| Explicitly not measured | Smoke report: 28 product-quality metrics are `not_measured` | The listed evidence gap exists and its next measurement command is known. | A missing metric is zero, acceptable, or implicitly passed. |
| Historical internal snapshots | `docs/hackathon/kpi-snapshot.md` (62 local DDI rules, 50 internal cases, 217 aliases, 10/10 pre-check) | These are asset/small-gate inventory snapshots with stated limits. | DDI sensitivity/specificity, general safety, jailbreak robustness, or real-world accuracy. |
| Historical Deep Beta note | `docs/hackathon/deepbeta-research-benchmark-2026-04-19.md` | A historical exploratory note exists. Its referenced JSON report is absent from this checkout. | A reproducible result, external comparison, or evidence of current performance. |

The exact fixture manifest declares nine synthetic datasets with 12 total
records. They contain no PHI or secrets and are expressly non-representative:
they do not include a clinical corpus, licensed full DrugBank data, a retrieval
snapshot, clinician adjudication, consented audio, user-study data, or provider
telemetry. The integrity result is therefore deliberately narrow.

## Peer-review response matrix

| Review weakness | Audit finding | Manuscript action |
| --- | --- | --- |
| 1. No empirical results for RQ1–RQ6 | Correct. No adequate measured result exists for any RQ. | Reclassify all six as pre-specified protocol questions; state that none is accepted or rejected. |
| 2. Small pre-checks overinterpreted | Correct. 10/10 and 100% gate claims are small internal gates. | Retain only as labelled asset/pre-check inventory, with denominator and no performance interpretation. |
| 3. Dataset/reference standards unspecified | Correct for any outcome evaluation. | Specify the only present synthetic fixture manifest; explicitly list absent labels, annotators, adjudication, licensing, and representativeness. |
| 4. Statistics absent | Correct. | Report Wilson interval only for the 9/9 artifact-integrity observation; prescribe paired resampling, effect sizes, multiplicity handling, and sample-size planning for future studies. |
| 5. Human/expert studies absent | Correct. | State no participants, clinician reviewers, or timing study were conducted; make RQ4–RQ6 future work requiring approved protocols. |
| 6. External safety/validity untested | Correct. | State that no external, prospective, multi-site, subgroup, penetration, calibration, or independent clinical review has been performed. |
| 7. Novelty not compared to baselines | Correct. | Define contribution as an integrated prototype/architecture claim only, not demonstrated superiority. |
| 8. Reproducibility details missing | Partly addressed by versioned manifests but no execution trace. | Bind the one structural result to commit, commands, manifest and timestamp; state all runtime/retrieval/model evidence remains unavailable. |
| 9. Intended use too broad | Correct. | Separate implemented multi-module product scope from the unperformed study; nominate a narrow, clinician-reviewed Vietnamese evidence-retrieval study for the next protocol. |
| 10. Conclusions exceed evidence | Correct. | Replace readiness, benefit, coordination, and scalability conclusions with a limited implementation/protocol conclusion. |

## What the revised manuscript must and must not claim

The revised document may state that CLARA-Care is an implemented integrated
prototype with versioned guards, contracts, and synthetic-fixture integrity
checks. It may state that these mechanisms are testable in the repository.

It must not state or imply that CLARA-Care improves clinical decisions,
diagnosis, treatment, mortality, costs, documentation time, duplicate entry,
patient outcomes, clinical safety, or coordination; that it outperforms named
or generic baselines; or that a clinical/user/expert/external validation was
conducted. The document must distinguish an implementation claim from a future
study design every time.

## Minimum evidence required before a scientific performance claim

1. Freeze code commit, model/provider identifiers, prompts, parameters,
   retrieval index/corpus snapshot, hardware/runtime, randomization controls,
   and per-query usage/cost accounting.
2. Use a versioned, licensed/de-identified task dataset with explicit inclusion
   and exclusion criteria, sampling, subgroup composition, reference standard,
   annotator expertise, independence, adjudication, agreement, and access
   conditions.
3. For RQ1/RQ2, evaluate paired retrieval and claim-grounding outcomes against
   specified baselines using paired bootstrap intervals and a multiplicity plan.
4. For RQ3, use a licensed, frozen DDI reference and report sensitivity,
   specificity, precision, false-alert rate, severity-stratified failures, and
   confidence intervals.
5. For RQ4/RQ5/RQ6, obtain ethics/consent where required and perform a
   pre-specified, adequately powered study with independent clinician/user
   assessment, comparator workflow, order control, and error/harms reporting.
6. Conduct external and robustness evaluation before deployment claims:
   independent Vietnamese sites or held-out data, regional/language subgroups,
   adversarial prompt/file-injection testing, cross-profile security testing,
   privacy review, calibration analysis, and prospective monitoring.
