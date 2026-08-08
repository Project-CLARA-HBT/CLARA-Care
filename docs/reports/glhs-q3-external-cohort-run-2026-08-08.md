# GLHS Q3 — external structural cohort run (2026-08-08)

## Verdict on the “perfect score”

There is **no final GLHS benchmark score** in this run.  `glhs_full` is the
declared reference-policy model and shares the structural rules used by the
oracle; its 100% development value is expected conformance, not independent
evidence that a deployed system is perfect.  Both outputs therefore set
`score_release.final_score_released=false`.

The numerical values below must not be used in an abstract, conclusion, or
claim of clinical safety/effectiveness.  They are development structural
robustness checks after controlled perturbations, not clinical labels,
medication-reconciliation accuracy, external validation, or real-world
privacy/security testing.

## Cohorts run separately

| Cohort | Source data read in full | Structural cases / subject tokens | Partition | Final score released |
|---|---|---:|---|---|
| MIMIC-IV Clinical Database Demo v2.2 | `admissions.csv.gz` (275 rows) + `prescriptions.csv.gz` (18,087 rows); 100 source subjects in each table | 100 / 100 | development | No |
| MIMIC-IV-ED Demo v2.2 | `edstays.csv.gz` (222 rows, 64 subjects) + `medrecon.csv.gz` (2,764 rows, 49 subjects) | 64 / 64 | development | No |

The cohort preparer consumes source data only locally.  It emits only a salted,
one-way subject token, source-row-derived episode count, and a predeclared
structural perturbation/oracle.  It emits **no** direct subject ID, medication
name, dose, timestamp, diagnosis, laboratory value, free text, or source row.
The salt is local under `/tmp` and is not part of this repository or artifact.

## Measured outputs

Each cell is `state correct / total`; `unauthorized` and `GST bypass` are raw
event counts.  The strong temporal/provenance resolver is intentionally a
baseline that handles valid-time/provenance patterns but lacks consent, GST and
projection governance.

### MIMIC-IV Demo

Frozen output: `artifacts/glhs-q3/2026-08-08-v3-mimic-iv-demo/`
`summary.json` SHA-256: `73f6c0634a9a0c6fef03e5e6e82c2d66bfc53cba391be116bcc83a352231923e`

| Structural model | State correct | Unauthorized / 100 | GST bypass / 100 |
|---|---:|---:|---:|
| LWW | 33/100 | 16 | 0 |
| Naive RAG | 33/100 | 16 | 0 |
| Temporal/provenance resolver | 84/100 | 16 | 16 |
| GLHS reference policy | 100/100 | 0 | 0 |
| GLHS without THSS | 100/100 | 0 | 0 |
| GLHS without GST | 33/100 | 0 | 16 |

### MIMIC-IV-ED Demo

Frozen output: `artifacts/glhs-q3/2026-08-08-v3-mimic-iv-ed-demo/`
`summary.json` SHA-256: `2649bb43bd32ac27f96fa35654058a123439d681da247552af4061c9e9834640`

| Structural model | State correct | Unauthorized / 64 | GST bypass / 64 |
|---|---:|---:|---:|
| LWW | 21/64 | 10 | 0 |
| Naive RAG | 21/64 | 10 | 0 |
| Temporal/provenance resolver | 54/64 | 10 | 10 |
| GLHS reference policy | 64/64 | 0 | 0 |
| GLHS without THSS | 64/64 | 0 | 0 |
| GLHS without GST | 21/64 | 0 | 10 |

These figures are not combined because the cohorts differ in source schema,
case count and perturbation mix.  The reference-policy values remain
development conformance only; a stronger baseline makes the comparison less
trivial, but it does not make the result independent.

### User-supplied Synthea FHIR STU3

Frozen output: `artifacts/glhs-q3/2026-08-08-v3-synthea-stu3-development/`
`summary.json` SHA-256: `8f8f1959af433ff09b2bb821b6679e53fd41849790e952527a249cbb5638a56d`

The one-pass preparer scanned all 22,339,056,743 bytes of the supplied nested
archive: 1,594,095 patient bundles across 12 inner archives. It emitted no
clinical payload: 15,877 salted, structural perturbation cases (1% deterministic
hash sampling; `c07bdc4d5c92a7588c590196f00526248f8250c927f7a8296064833868f78e4d`).
The raw archive checksum is `c3dc791804fc206191c80ca022baef3a736626b2b9b736c591dbda998b1d5e0e`.

| Structural model | State correct | Unauthorized / 15,877 | GST bypass / 15,877 |
|---|---:|---:|---:|
| LWW | 5,293/15,877 | 2,646 | 0 |
| Naive RAG | 5,293/15,877 | 2,646 | 0 |
| Temporal/provenance resolver | 13,231/15,877 | 2,646 | 2,646 |
| GLHS reference policy | 15,877/15,877 | 0 | 0 |
| GLHS without THSS | 15,877/15,877 | 0 | 0 |
| GLHS without GST | 5,293/15,877 | 0 | 2,646 |

This is a synthetic structural-development cohort and must remain separate
from MIMIC. Its score release is explicitly `false`; it is not an external
clinical benchmark or sealed holdout.

## Provenance and reproduction

The source checksums and row/subject counts are stored in each output under
`cohorts.external.source_provenance`; `evidence-manifest.json` links every CSV
and SVG.  The relevant source table SHA-256 values are:

| Cohort | Tables |
|---|---|
| MIMIC-IV Demo | admissions `910b9f160ffdf1e08ea673585393f347c773ccc87d66875c627584a903ae8493`; prescriptions `33c392ba5b9299b08eca0a61911ba106f0aebdba26ed31b856bb9ffd49fe3654` |
| MIMIC-IV-ED Demo | ED stays `fc185cb111a70e9dfd8457c6e1da4f9366dee729e072282995dcd7045a5a3c52`; medication reconciliation `efdab040cede0ef19997d6c5f55f3e8cbaccdfdf7b502fc779420ddcbf47804c` |

The exact commands are documented in
[`evaluation/glhs_q3/README.md`](../../evaluation/glhs_q3/README.md).  The
preparer is [`prepare_external_cohort.py`](../../evaluation/glhs_q3/prepare_external_cohort.py).

## Still required before a final score

1. An evaluator who did not implement/tune the policy must freeze at least 25%
   compositional cases as a separate holdout, record a curator identity,
   independence attestation, freeze ID, oracle SHA-256 and development-set
   SHA-256, and run it only after implementation freeze.  The runner enforces
   those fields for `partition=sealed_holdout`; it cannot prove the human
   attestation itself.
2. MIMIC-IV on FHIR v2.1 was **not** downloaded or run: its PhysioNet page
   indicates required training/DUA.  It remains the interoperability cohort
   once lawful access is explicitly supplied.
3. The local Synthea FHIR **STU3** scan is complete, but it is synthetic,
   development-only and therefore cannot substitute for an independently frozen
   perturbation holdout or MIMIC-on-FHIR interoperability evaluation.
4. The current preparation uses source records to establish longitudinal shape,
   then injects fixed structural perturbations.  It does not evaluate clinical
   truth, medication terminology/normalisation, clinical DDI correctness,
   clinician judgement, patient outcomes, or production API/LLM latency.

## Official source pages

- MIMIC-IV Clinical Database Demo v2.2: <https://physionet.org/content/mimic-iv-demo/2.2/>
- MIMIC-IV-ED Demo v2.2: <https://physionet.org/content/mimic-iv-ed-demo/2.2/>
- MIMIC-IV on FHIR v2.1: <https://www.physionet.org/content/mimic-iv-fhir/2.1/>
- Synthea downloads: <https://synthea.mitre.org/downloads>
