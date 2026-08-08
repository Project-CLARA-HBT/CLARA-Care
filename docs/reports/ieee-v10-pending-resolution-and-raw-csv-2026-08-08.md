# IEEE v10 Q2 — pending-result resolution ledger

Source reviewed: `CLARA-Care_GLHS_IEEE_v10_Q2_second_round.pdf` (17 pages,
created 2026-08-08). This ledger is the authoritative replacement for every
`pending`, dash placeholder, and "generated after the frozen run" statement in
that PDF. It does **not** amend the PDF in place: the PDF must not be submitted
until its tables/figures are regenerated from the frozen artifacts cited here.

## Non-negotiable interpretation boundary

All completed runs are developer-authored structural-oracle conformance runs.
They are neither clinical validation nor a sealed independent benchmark. In
particular, `glhs_full` implements the same declared rules used by the
developer-authored oracle; its development score is not a valid independent
superiority claim. Every artifact declares `final_score_released=false`.

## Frozen runs and raw CSV inventory

| Cohort / status | Cases / subjects | Frozen summary SHA-256 | Original raw CSV files |
|---|---:|---|---|
| Developer synthetic v2 / development | 300 / 150 | `8f200a8ffa0c1b3c7b6dacf48e85c679987d68991d7430e53d92e55904b9e81c` | `artifacts/glhs-q3/2026-08-08-v2/{cases,outcomes,per_run,baseline_comparison,thss_ablation,error_analysis,scalability}.csv` |
| MIMIC-IV Demo / development structural perturbations | 100 / 100 | `73f6c0634a9a0c6fef03e5e6e82c2d66bfc53cba391be116bcc83a352231923e` | `artifacts/glhs-q3/2026-08-08-v3-mimic-iv-demo/{cases,outcomes,per_run,baseline_comparison,thss_ablation,error_analysis,scalability}.csv` |
| MIMIC-IV-ED Demo / development structural perturbations | 64 / 49 | `2649bb43bd32ac27f96fa35654058a123439d681da247552af4061c9e9834640` | `artifacts/glhs-q3/2026-08-08-v3-mimic-iv-ed-demo/{cases,outcomes,per_run,baseline_comparison,thss_ablation,error_analysis,scalability}.csv` |
| Synthea FHIR STU3 / development structural perturbations | 15,877 / 15,877 | `8f8f1959af433ff09b2bb821b6679e53fd41849790e952527a249cbb5638a56d` | `artifacts/glhs-q3/2026-08-08-v3-synthea-stu3-development/{cases,outcomes,per_run,baseline_comparison,thss_ablation,error_analysis,scalability}.csv` |

The Synthea manifest is separately stored outside the repository at
`/tmp/clara-q3-derived/synthea-stu3-development/`; its `perturbations.jsonl`
is the raw controlled input (15,877 rows; SHA-256
`c07bdc4d5c92a7588c590196f00526248f8250c927f7a8296064833868f78e4d`). It is
salted/structural and contains no clinical payload. Do not commit its local salt.

## Resolution of PDF placeholders

| PDF item | Resolution from frozen evidence | Raw CSV / status |
|---|---|---|
| Implementation Git SHA, branch/tag, clean state, policy/task/oracle hashes | `environment.json` and `evidence-manifest.json` are the only authoritative fields. The PDF's literal `pending` cannot be filled from prose. | `environment.json`; `evidence-manifest.json`. Must be copied verbatim into a regenerated manuscript. |
| 400 cases / 200 subjects, 60 sealed holdout, 120 model-backed × 3 runs | **Not executed.** Actual developer suite is 300/150; no sealed holdout; no model-backed run. Do not replace with 300/150 as though equivalent. | `cases.csv`, `per_run.csv`; report as protocol deviation/unmet requirement. |
| Fig. 3 baseline comparison | Generated, but only development structural conformance. Developer suite: GLHS 300/300, TPR 250/300, LWW/Naive/GST-less 100/300; paired GLHS–TPR RD 0.1667 (bootstrap 95% CI 0.1300–0.2033), Holm p `3.5527e-15`. | `baseline_comparison.csv`, `baseline-comparison.svg`. |
| Fig. 4 THSS privacy–utility | Generated. Authorization fixed: all 4 profiles have 0/300 unauthorized disclosures and 750/750 critical-fact recall. Nonessential disclosure: full 1750/1750; loose 1250/1750; default 500/1750; strict 0/1750. | `thss_ablation.csv`, `thss-privacy-utility.svg`. Structural minimization only; no privacy guarantee or downstream model utility. |
| Fig. 5 error analysis / conflict automation | Generated for developer suite. It reports per-system error codes, counts, safety outcome, and case identifiers; it is not clinician adjudication or auto-resolution accuracy. | `error_analysis.csv`, `error-breakdown.svg`, `conflict-automation.svg`. |
| Fig. 6 scalability/latency | Generated as 50 pure-Python samples per operation/depth 10/50/100/250. It excludes PostgreSQL, Redis, Neo4j, network, browser and LLM time. | `scalability.csv`, `scalability.svg`. |
| Table III incremental benefit/cost | Fill only with structural findings above; escalation/review burden is **not measured as human burden**, and model/context task cost is not measured. P95 must be copied from `scalability.csv`, with its simulation qualifier. | `baseline_comparison.csv`, `thss_ablation.csv`, `scalability.csv`; unmeasured cells remain `not measured`. |
| Table IV RQ1–RQ7 | RQ1/RQ2/RQ3/RQ4/RQ5/RQ6/RQ7 have structural measurements only; no RQ has clinical/user/LLM result. Detailed mapping below. | `outcomes.csv`, `thss_ablation.csv`, `scalability.csv`. |
| Table V cohort × family RD/CI | **Not available in the required PDF form.** Existing artifact has system-level comparisons, but no frozen sealed cohort/family table that makes an independent comparative claim. Keep `not measured` rather than back-fill from developer oracle. | `outcomes.csv`; new independent sealed-holdout CSV required. |
| Table VI core metrics | Fill the measured structural endpoints below; automation rate, auto-resolution precision, human escalation rate, and transition explainability are **not measured under independent human reference**. | `outcomes.csv`, `error_analysis.csv`; retain `not measured` cells. |

## RQ table — only permissible results

| RQ | Measured structural result | What remains pending/not measured |
|---|---|---|
| RQ1 late evidence | GLHS 0/300 late-evidence errors; TPR 0/300; LWW/Naive/GST-less 50/300 each in developer suite. | Independent holdout and clinical temporal correctness. |
| RQ2 reconstruction | GLHS 300/300 reconstruction correct; LWW/Naive/TPR 225/300; GST-less 200/300. | Database-backed, real EHR reconstruction and generalisation. |
| RQ3 conflicts | GLHS 0/300 silent collapse; TPR 0/300; LWW/Naive/GST-less 75/300. | Independent oracle, clinician adjudication, human review workload. |
| RQ4 provenance | GLHS 300/300 provenance-complete in the structural oracle. | Evidence/actor traceability audit on production records. |
| RQ5 THSS | Values in Fig. 4 row; authorization held fixed. | Privacy leakage at scale, downstream LLM task utility. |
| RQ6 GST | GLHS 0/300 direct-write bypass; GST-less 50/300. | Real AI attack/prompt-injection/penetration test. |
| RQ7 rebuild/scale | Rebuild correctness is structural; timing CSV covers pure-Python depths. | Production latency, throughput, cost or capacity. |

## Required CSVs still missing before IEEE submission

1. Independently authored, checksum-locked sealed-holdout `cases.csv`,
   `outcomes.csv`, `per_run.csv`, and cohort-family summary CSV; 25% of
   compositional cases must be uninspected before frozen evaluation.
2. Model/provider run CSV with model version, prompts, seeds, corpus/index,
   retrieval/reranker settings, per-run latency, tokens and cost.
3. Independent retrieval/citation, DrugBank DDI, Scribe, security,
   prompt-injection, cross-profile, usability and clinician-review result CSVs
   with reference standard and participant/adjudication metadata where relevant.

Until those CSVs exist, the PDF must retain `not measured`, not `pending`, and
must remove claims that imply the planned experiment was executed.

## Actual completed-cohort results (all numerators/denominators)

These are the values that should replace the PDF's vague `MIMIC-derived`
placeholders. Each cell is reconstructed from the named cohort's original
`outcomes.csv`; denominators are the cohort's case count. They are reported
separately because the perturbation mix differs by cohort.

### MIMIC-IV Clinical Database Demo v2.2 (100/100 structural cases)

| System | State correct | Late error | Silent conflict collapse | Unauthorized disclosure | GST bypass | Provenance complete | Reconstruction | Revocation honored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LWW | 33/100 | 18/100 | 25/100 | 16/100 | 0/100 | 92/100 | 74/100 | 84/100 |
| Naive RAG | 33/100 | 18/100 | 25/100 | 16/100 | 0/100 | 92/100 | 74/100 | 84/100 |
| TPR | 84/100 | 0/100 | 0/100 | 16/100 | 16/100 | 100/100 | 76/100 | 84/100 |
| GLHS-full | 100/100 | 0/100 | 0/100 | 0/100 | 0/100 | 100/100 | 100/100 | 100/100 |
| GLHS-no-THSS | 100/100 | 0/100 | 0/100 | 0/100 | 0/100 | 100/100 | 100/100 | 100/100 |
| GLHS-no-GST | 33/100 | 18/100 | 25/100 | 0/100 | 16/100 | 92/100 | 66/100 | 100/100 |

### MIMIC-IV-ED Demo v2.2 (64/49 structural cases/subjects)

| System | State correct | Late error | Silent conflict collapse | Unauthorized disclosure | GST bypass | Provenance complete | Reconstruction | Revocation honored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LWW | 21/64 | 12/64 | 16/64 | 10/64 | 0/64 | 59/64 | 47/64 | 54/64 |
| Naive RAG | 21/64 | 12/64 | 16/64 | 10/64 | 0/64 | 59/64 | 47/64 | 54/64 |
| TPR | 54/64 | 0/64 | 0/64 | 10/64 | 10/64 | 64/64 | 49/64 | 54/64 |
| GLHS-full | 64/64 | 0/64 | 0/64 | 0/64 | 0/64 | 64/64 | 64/64 | 64/64 |
| GLHS-no-THSS | 64/64 | 0/64 | 0/64 | 0/64 | 0/64 | 64/64 | 64/64 | 64/64 |
| GLHS-no-GST | 21/64 | 12/64 | 16/64 | 0/64 | 10/64 | 59/64 | 42/64 | 64/64 |

### Synthea FHIR STU3 (15,877/15,877 structural cases/subjects)

| System | State correct | Late error | Silent conflict collapse | Unauthorized disclosure | GST bypass | Provenance complete | Reconstruction | Revocation honored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LWW | 5,293/15,877 | 2,646/15,877 | 3,969/15,877 | 2,646/15,877 | 0/15,877 | 14,554/15,877 | 11,908/15,877 | 13,231/15,877 |
| Naive RAG | 5,293/15,877 | 2,646/15,877 | 3,969/15,877 | 2,646/15,877 | 0/15,877 | 14,554/15,877 | 11,908/15,877 | 13,231/15,877 |
| TPR | 13,231/15,877 | 0/15,877 | 0/15,877 | 2,646/15,877 | 2,646/15,877 | 15,877/15,877 | 11,908/15,877 | 13,231/15,877 |
| GLHS-full | 15,877/15,877 | 0/15,877 | 0/15,877 | 0/15,877 | 0/15,877 | 15,877/15,877 | 15,877/15,877 | 15,877/15,877 |
| GLHS-no-THSS | 15,877/15,877 | 0/15,877 | 0/15,877 | 0/15,877 | 0/15,877 | 15,877/15,877 | 15,877/15,877 | 15,877/15,877 |
| GLHS-no-GST | 5,293/15,877 | 2,646/15,877 | 3,969/15,877 | 0/15,877 | 2,646/15,877 | 14,554/15,877 | 10,585/15,877 | 15,877/15,877 |

The raw source for all three tables is each cohort's `outcomes.csv`; no values
in these tables were estimated or pooled. They are structural-development
measurements, so they do not repair the PDF's missing sealed-holdout, clinical,
LLM, DDI, retrieval, Scribe, security, or usability result CSVs.
