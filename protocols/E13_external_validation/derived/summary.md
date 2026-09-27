# E13 External / Independent Validation Report

- **Freeze ID:** `GLHS-EXTERNAL-VALIDATION-E13-20260928-01`
- **Git SHA:** `81f040d3e05905cc384239c5ae130f629e722d3e`
- **Adjudication Type:** `SYNTHETIC_MODEL_ADJUDICATION`
- **Human Adjudication Status:** `NOT_RUN_HUMAN_UNAVAILABLE`
- **Independent Human Claim Eligible:** `False`
- **Statistical Targets Met:** `False`
- **Total External Tasks:** `9`

## Inter-Rater Agreement & Reliability

- **Cohen's $\kappa$:** `0.0000`
- **Krippendorff's $\alpha$:** `0.0000`

## Overall External Retention & Error Rates

- **External Fact Retention Accuracy:** `100.00%` (95% CI: `70.09%` – `100.00%`)
- **False Positive Rate (FPR):** `0.00%` (95% CI: `0.00%` – `29.91%`)
- **False Negative Rate (FNR):** `0.00%` (95% CI: `0.00%` – `29.91%`)
- **State Reconstruction Accuracy:** `100.00%` (95% CI: `70.09%` – `100.00%`)

## Per-Corpus Breakdown

| Corpus | Tasks | Fact Retention (95% CI) | False Positive Rate | False Negative Rate | Cohen's $\kappa$ |
| --- | --- | --- | --- | --- | --- |
| diabetes_130 | 2 | 100.0% (34.2%-100.0%) | 0.0% | 0.0% | 1.000 |
| eicu | 2 | 100.0% (34.2%-100.0%) | 0.0% | 0.0% | 1.000 |
| mimic_on_fhir | 3 | 100.0% (43.9%-100.0%) | 0.0% | 0.0% | 0.000 |
| synthea | 2 | 100.0% (34.2%-100.0%) | 0.0% | 0.0% | 1.000 |

## Red Team (E) Compliance & Guardrails

- **Red Team Rule:** Model-based QA is strictly labeled as SYNTHETIC_MODEL_ADJUDICATION and ineligible for independent human clinical claim.
- **Disallow Model As Human Enforced:** `True`
