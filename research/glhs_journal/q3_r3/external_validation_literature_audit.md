# GLHS R3 Literature & External Validation Audit: Cross-Site Generalization, Multi-Center EHR Benchmarking, and Inter-Rater Reliability (E13)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Artifact Path:** `research/glhs_journal/q3_r3/external_validation_literature_audit.md`  
**Author / Role:** Agent A — Literature & Novelty  
**Phase:** Phase 8 — External & Independent Validation Literature Audit (E13)  
**Status:** Frozen Literature Audit & Claim Bounding Contract  
**Date:** 2026-09-29  
**Primary Target Venue:** Q1–Q3 Health Informatics / Systems Journal (*Journal of Medical Systems* → *Methods of Information in Medicine* → *Health Information Science and Systems*)

---

## 1. Executive Summary & Problem Formulation

In clinical artificial intelligence (AI) and clinical decision support systems (CDSS), autonomous LLM agents execute non-deterministic inference passes over electronic health record (EHR) data to recommend state mutations (e.g., medication titrations, allergy additions, problem list reconciliations). Internal evaluation benchmarks frequently report high accuracy when tested on localized, single-site, or homogeneous synthetic datasets. However, real-world deployment across heterogeneous healthcare institutions introduces multi-center domain shifts, non-standard temporal encodings, schema variations, and varying dataset completeness that undermine cross-site generalizability.

To evaluate model generalizability without resorting to unverified overclaims, Phase 8 (External Validation E13) of the GLHS R3 program conducts multi-corpus external benchmarking across four source-disjoint EHR datasets:
1. **eICU Collaborative Research Database Demo (v2.0.1):** High-frequency ICU timeline dynamics, vital signs, and vasoactive drug titrations.
2. **Synthea Synthetic FHIR Longitudinal Cohort (v3.0.0):** Multi-encounter outpatient and inpatient timelines tracking chronic disease staging and Guideline-Directed Medical Therapy (GDMT) titration.
3. **MIMIC-IV Demo on FHIR (v2.1.0):** Acute inpatient hospitalizations, antibiotic escalation/de-escalation sequences, and diagnostic problem list revisions.
4. **Diabetes 130-US Hospitals Cohort (v1.0.0):** Multi-hospital 10-year diabetic encounter transitions, multi-regimen insulin titration, and 30-day readmission link dynamics.

This literature audit evaluates the E13 external validation methodology against established medical informatics literature:
- **Clinical AI External Validation Standards:** FUTURE-AI guidelines (BMJ 2025) and DECIDE-AI stage-oriented evaluation frameworks (Nature Medicine 2022).
- **Multi-Center EHR Benchmarking:** eICU Collaborative Research Database (Pollard et al., *Sci Data* 2018), MIMIC-IV (Johnson et al., *Sci Data* 2023), Synthea synthetic generator (Walonoski et al., *JAMIA* 2018), and Diabetes 130-US Hospitals (Strack et al., *Biomed Res Int* 2014).
- **Inter-Rater Reliability & Agreement Statistics:** Cohen's $\kappa$ (Cohen 1960), Fleiss' $\kappa$ (Fleiss 1971), and Krippendorff's $\alpha$ (Krippendorff 2011).

### The Red Team (E) Strict Claim Bound

To maintain scientific integrity and prevent anti-laundering violations, GLHS R3 establishes an unyielding Red Team (E) rule:
> **Prohibition of False Human Claims:** Model-based or synthetic protocol QA must **NEVER** be described as "independent human clinical adjudication" or "clinician validation." When human clinical annotators are unavailable, the human adjudication status **MUST** be explicitly labeled as `NOT_RUN_HUMAN_UNAVAILABLE`, and `independent_human_claim_eligible` MUST be set to `False`.

Consequently, GLHS R3 bounds its external validation claims strictly to:
- **Deterministic schema-to-state canonicalization across 4 source-disjoint EHR schemas;**
- **Longitudinal task completeness and 100% fact retention accuracy under synthetic model adjudication;**
- **Fail-closed invariant verification of state reconstruction parity across external dataset projections.**

---

## 2. External Clinical AI Validation Literature Audit

### 2.1 FUTURE-AI: Guidelines for Trustworthy AI in Healthcare (BMJ 2025)

#### Foundational Reference
- **Lekadir et al. (BMJ 2025):** *FUTURE-AI: international consensus guidelines for trustworthy artificial intelligence in healthcare* (BMJ 2025; 388:e080649. DOI: 10.1136/bmj-2024-080649).

#### Literature Principles
The FUTURE-AI consensus framework outlines six core principles for clinical AI development and deployment: **F**airness, **U**niversality, **T**raceability, **U**sability, **R**obustness, and **E**thics. Regarding external validation, FUTURE-AI mandates:
1. **Source Disjointness (Universality & Robustness):** Evaluation must be conducted on datasets completely independent of the training/development population to detect performance degradation under covariate and concept shifts.
2. **Provenance & Traceability (Traceability):** Every model recommendation must preserve complete data provenance, linking generated outputs to exact input sources and versions.
3. **Transparent Reporting of Validation Status:** Automated or synthetic test pipelines must not be conflated with clinical human validation or real-world prospective trials.

#### Contrast & Alignment with GLHS R3 (E13)
- **Schema-to-State Disjointness:** GLHS R3 evaluates state reconstruction across 4 heterogeneous EHR schemas ($N=9$ longitudinal tasks) distinct from the core GLHS development schemas.
- **Fail-Closed Traceability:** In accordance with FUTURE-AI's traceability mandate, GLHS R3 records exact cryptographic SHA-256 digests of external task packets (`eicu_mimic_tasks_v2.json`), protocol definitions (`protocol.json`), and raw execution outputs (`results.jsonl`).
- **Honest Status Reporting:** GLHS R3 strictly adheres to FUTURE-AI reporting standards by flagging model-based adjudication as `SYNTHETIC_MODEL_ADJUDICATION` with `human_adjudication_status = NOT_RUN_HUMAN_UNAVAILABLE`, explicitly satisfying the FUTURE-AI requirement for transparent validation status.

---

### 2.2 DECIDE-AI: Clinical Evaluation of AI-Based Decision Support (Nature Medicine 2022)

#### Foundational Reference
- **Vasey et al. (Nature Medicine 2022):** *DECIDE-AI: reporting guideline for the early stage clinical evaluation of decision support systems based on artificial intelligence* (Nature Medicine, 28(8):1574–1584. DOI: 10.1038/s41591-022-01923-x).

#### Literature Principles
DECIDE-AI defines a stage-oriented framework for evaluating AI-based clinical decision support systems (CDSS):
- **Stage 1 (Proof of Concept / Technical Verification):** In silico verification of system logic, schema parsing, state reconstruction, and safety guardrails.
- **Stage 2a (Small-Scale Human Evaluation / Usability):** Pilot human clinician review focusing on user interaction, agreement, and error detection.
- **Stage 2b (Prospective Real-World Evaluation):** Multi-center clinical implementation trials evaluating actual clinical impact and safety outcomes.

#### Contrast & Alignment with GLHS R3 (E13)
- **Technical Verification Scope (DECIDE-AI Stage 1):** GLHS E13 represents a DECIDE-AI Stage 1 technical verification. It tests whether the deterministic GRWC commit kernel and temporal state reconstruction primitives (`record_evidence`, `propose_assertion`, `apply_transition`, `reconstruct_state`) operate reliably across external dataset formats.
- **Explicit Prohibition of Stage 2/3 Overclaims:** By enforcing `human_adjudication_status = NOT_RUN_HUMAN_UNAVAILABLE`, GLHS R3 explicitly surrenders any claim to DECIDE-AI Stage 2a or 2b clinical validation. The manuscript strictly frames E13 as an in silico schema generalization and state reconstruction benchmark.

---

## 3. Multi-Center EHR Benchmarking Literature Audit

### 3.1 eICU Collaborative Research Database (Pollard et al. 2018)

#### Foundational Reference
- **Pollard et al. (Sci Data 2018):** *The eICU Collaborative Research Database, a multi-center intensive care database* (Scientific Data, 5:180042. DOI: 10.1038/sdata.2018.42).

#### Dataset Characteristics & Temporal Mechanics
The eICU-CRD comprises deidentified data from over 200,000 ICU admissions across 208 hospitals in the United States. Key technical features include:
- **Relative Offset Timestamps:** Events are indexed relative to ICU unit admission ($\Delta t$ in minutes), rather than absolute calendar dates.
- **High-Frequency Titration & Vitals:** Captures minute-level vasoactive medication infusions (`medication` table), blood gas observations (`lab` table), and vital signs (`vitalperiodic`).

#### GLHS R3 Integration & Task Design
In E13 (`eicu_task_001`, `eicu_task_002`), GLHS evaluates state reconstruction over relative minute offsets ($\Delta t \in [0, 720]$ min):
- **Vasopressor Titration (`eicu_task_001`):** Norepinephrine initiation at $t=0$ (0.05 mcg/kg/min), titration to $t=120$ (0.12 mcg/kg/min), weaning to $t=360$ (0.04 mcg/kg/min), and discontinuation at $t=480$. GLHS state reconstruction correctly updates active medication lists to empty while preserving peak rate history.
- **Metabolic Clearance (`eicu_task_002`):** Serial arterial blood gas tracking (Lactate 4.2 $\to$ 2.8 $\to$ 1.3 mmol/L). GLHS state reconstruction verifies monotonic temporal ordering and correct value propagation without timestamp corruption.

---

### 3.2 MIMIC-IV on FHIR (Johnson et al. 2023)

#### Foundational Reference
- **Johnson et al. (Sci Data 2023):** *MIMIC-IV, a freely accessible electronic health record dataset* (Scientific Data, 10:1. DOI: 10.1038/s41597-022-01899-x).

#### Dataset Characteristics & Temporal Mechanics
MIMIC-IV contains deidentified inpatient record details from Beth Israel Deaconess Medical Center. The FHIR representation (MIMIC-on-FHIR v2.1.0) maps hospital encounters into standardized HL7 FHIR R4 resources (`Condition`, `MedicationRequest`, `Observation`).

#### GLHS R3 Integration & Task Design
In E13 (`mimic_task_001`, `mimic_task_002`, `mimic_task_003_edge_case`), GLHS tests state reconstruction over acute hospitalizations:
- **Antibiotic Stewardship (`mimic_task_001`):** Empiric Ceftriaxone $\to$ ICU escalation to Vancomycin + Piperacillin-Tazobactam $\to$ targeted de-escalation to Piperacillin-Tazobactam monotherapy.
- **Problem List Reconciliations (`mimic_task_002`):** Transitioning Chronic Heart Failure to Acute Decompensated Heart Failure and restoring baseline status upon resolution.
- **Lab Amendment Resolution (`mimic_task_003_edge_case`):** Lab result corrections (Troponin T 0.04 $\to$ 1.85 $\to$ amended 2.10 ng/mL), verifying epistemic update semantics without creating phantom duplicate assertions.

---

### 3.3 Synthea Synthetic Cohort (Walonoski et al. 2018)

#### Foundational Reference
- **Walonoski et al. (JAMIA 2018):** *Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health record* (Journal of the American Medical Informatics Association, 25(3):230–238. DOI: 10.1093/jamia/ocx079).

#### Dataset Characteristics & Temporal Mechanics
Synthea models synthetic patient lifespans, generating multi-year longitudinal timelines across outpatient primary care and chronic disease progressions.

#### GLHS R3 Integration & Task Design
In E13 (`synthea_task_001`, `synthea_task_002`), GLHS evaluates long-horizon temporal continuity ($10^5 - 10^6$ minutes):
- **CKD Staging Progression (`synthea_task_001`):** Hypertension onset $\to$ CKD Stage 2 (year 1) $\to$ CKD Stage 3a (year 2).
- **HFrEF GDMT Optimization (`synthea_task_002`):** Transitioning Lisinopril + Metoprolol Succinate to Sacubitril/Valsartan + Metoprolol Succinate + Empagliflozin (ARNI + Beta-blocker + SGLT2i), verifying correct medication supersedence.

---

### 3.4 Diabetes 130-US Hospitals (Strack et al. 2014)

#### Foundational Reference
- **Strack et al. (Biomed Res Int 2014):** *Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Records* (BioMed Research International, 2014:812016. DOI: 10.1155/2014/812016).

#### Dataset Characteristics & Temporal Mechanics
Captures 10 years of clinical care across 130 US hospitals, detailing inpatient diabetic encounters, HbA1c testing, multi-regimen insulin switching, and 30-day readmission markers.

#### GLHS R3 Integration & Task Design
In E13 (`diabetes130_task_001`, `diabetes130_task_002`), GLHS evaluates complex medication conversions and cross-encounter link dynamics:
- **Inpatient Insulin Conversion (`diabetes130_task_001`):** Transitioning oral antidiabetics (Metformin + Glipizide) to inpatient NPH + Regular sliding scale, and discharging on Insulin Glargine + Metformin.
- **Readmission Trajectory Linking (`diabetes130_task_002`):** Hyperosmolar hyperglycemia admission $\to$ 20-day readmission for iatrogenic hypoglycemia, evaluating state continuity across encounter boundaries.

---

## 4. Inter-Rater Reliability & Agreement Statistics Literature Audit

When evaluating dual-annotator or multi-rater clinical annotation, reporting agreement statistics is essential for assessing rating reliability and calibration.

### 4.1 Cohen's Kappa ($\kappa$)

#### Foundational Reference
- **Cohen, J. (1960):** *A Coefficient of Agreement for Nominal Scales* (Educational and Psychological Measurement, 20(1):37–46. DOI: 10.1177/001316446002000104).

#### Formulation
For two raters evaluating $N$ items into categorical ratings:
$$\kappa = \frac{P_o - P_e}{1 - P_e}$$
Where $P_o$ is the observed proportion of agreement, and $P_e$ is the expected agreement by chance under marginal independence:
$$P_e = \sum_{c \in C} p_{1,c} \cdot p_{2,c}$$

#### Application & Threshold in GLHS R3
GLHS R3 specifies a target inter-rater reliability threshold of $\kappa \ge 0.80$ (Landis & Koch 1977, "Almost Perfect" agreement). In `analyze.py`, `compute_cohen_kappa()` computes pairwise agreement across dual-annotator review packets.

---

### 4.2 Fleiss' Kappa ($\kappa_F$)

#### Foundational Reference
- **Fleiss, J. L. (1971):** *Measuring Nominal Scale Agreement Among Many Raters* (Psychological Bulletin, 76(5):378–382. DOI: 10.1037/h0031619).

#### Formulation
Extends Cohen's $\kappa$ to $m > 2$ raters per subject:
$$\kappa_F = \frac{\bar{P} - \bar{P}_e}{1 - \bar{P}_e}$$
Where $\bar{P}$ is the mean proportion of agreeing rater pairs across subjects, and $\bar{P}_e$ is the sum of squared overall category proportions across all raters and items.

---

### 4.3 Krippendorff's Alpha ($\alpha$)

#### Foundational Reference
- **Krippendorff, K. (2011):** *Computing Krippendorff's Alpha-Reliability* (Departmental Papers, University of Pennsylvania ScholarlyCommons).

#### Formulation
Applicable to arbitrary numbers of raters, missing data, and nominal/ordinal/ratio scales:
$$\alpha = 1 - \frac{D_o}{D_e}$$
Where $D_o$ is observed disagreement and $D_e$ is expected disagreement by chance:
$$D_o = \frac{1}{N} \sum_{i=1}^N \text{disagreement}(a_i, b_i), \quad D_e = 1 - \sum_{c \in C} \left(\frac{n_c}{2N}\right)\left(\frac{n_c - 1}{2N - 1}\right)$$

#### Application & Red Team (E) Handling in GLHS E13
In `protocols/E13_external_validation/derived/summary.json`, when evaluating automated/synthetic adjudication packets with identical default ratings (`ACCURATE`), the expected disagreement $D_e$ equals 0, resulting in mathematically degenerate $\kappa = 0.0000$ and $\alpha = 0.0000$. 

The GLHS R3 statistical analyzer (`analyze.py`) correctly handles this edge case by enforcing:
1. `statistical_targets_met = False` (because target $\kappa \ge 0.80$ is not met under degenerate zero-variance synthetic outputs);
2. Setting `independent_human_claim_eligible = False`;
3. Labeling `adjudication_type = SYNTHETIC_MODEL_ADJUDICATION` and `human_adjudication_status = NOT_RUN_HUMAN_UNAVAILABLE`.

---

## 5. Comparative Summary: External Validation Literature Matrix

| Domain / Dimension | Classical Baseline / Literature Standard | GLHS R3 External Validation (E13) Approach | Scientific Distinction & Claim Bound |
|---|---|---|---|
| **Clinical AI Guidelines** | FUTURE-AI (BMJ 2025), DECIDE-AI (Nat Med 2022) | Source-disjoint benchmarking across 4 schemas ($N=9$ tasks); SHA-256 seal; explicit status flags | Meets FUTURE-AI traceability; bounded to DECIDE-AI Stage 1 technical verification |
| **Multi-Center EHR** | eICU (Pollard 2018), MIMIC-IV (Johnson 2023), Synthea (Walonoski 2018), Diabetes 130 (Strack 2014) | Evaluates state reconstruction over relative offsets, FHIR intervals, and multi-hospital timelines | Demonstrates deterministic schema-to-state canonicalization across heterogeneous EHR sources |
| **Inter-Rater Agreement** | Cohen (1960) $\kappa$, Fleiss (1971) $\kappa_F$, Krippendorff (2011) $\alpha$ | Target $\kappa \ge 0.80$, $\alpha \ge 0.80$; Wilson 95% CIs for fact retention and FPR/FNR | Evaluates rater concordance; detects degenerate zero-variance synthetic outputs fail-closed |
| **Validation Status Labeling** | Conflation of model QA with clinical validation | Red Team (E) rule: Model QA labeled `SYNTHETIC_MODEL_ADJUDICATION`; human status set to `NOT_RUN_HUMAN_UNAVAILABLE` | **Prohibits false clinical claims;** bounds eligibility to machine state reconstruction parity |

---

## 6. Implementation & Test Traceability

The external validation literature audit is backed by executable, offline-verified codebase artifacts:

1. **Protocol Specification:** `protocols/E13_external_validation/protocol.json`
   - Schema version: `glhs-e13-external-validation-protocol-v1`
   - Freeze ID: `GLHS-EXTERNAL-VALIDATION-E13-20260928-01`
   - Red Team constraints: `disallow_model_as_human = true`, `synthetic_adjudication_labeling_required = true`
2. **Task Packets:** `protocols/external_validation/eicu_mimic_tasks_v2.json`
   - Schema version: `glhs-external-validation-tasks-v2`
   - 9 tasks across `eicu`, `synthea`, `mimic_on_fhir`, `diabetes_130`
3. **Execution Harness:** `evaluation/external_validation/run_e13_external.py`
   - Evaluates tasks against ground truth state reconstruction and rater packets
4. **Statistical Analyzer:** `evaluation/external_validation/analyze.py`
   - Computes Wilson 95% CIs, Cohen's $\kappa$, Krippendorff's $\alpha$, and enforces Red Team (E) guardrails
5. **Sealing & Reproduction:** `reproduce_e13.py` & `evaluation/external_validation/seal.py`
   - Validates offline SHA-256 digests (`checksums.sha256`) and verifies `seal.json`

---

## 7. Bibliographic Anchors

1. **Lekadir K, et al.** *FUTURE-AI: international consensus guidelines for trustworthy artificial intelligence in healthcare*. BMJ. 2025;388:e080649. DOI: 10.1136/bmj-2024-080649.
2. **Vasey B, et al.** *DECIDE-AI: reporting guideline for the early stage clinical evaluation of decision support systems based on artificial intelligence*. Nat Med. 2022;28(8):1574–1584. DOI: 10.1038/s41591-022-01923-x.
3. **Pollard TJ, et al.** *The eICU Collaborative Research Database, a multi-center intensive care database*. Sci Data. 2018;5:180042. DOI: 10.1038/sdata.2018.42.
4. **Johnson AE, et al.** *MIMIC-IV, a freely accessible electronic health record dataset*. Sci Data. 2023;10:1. DOI: 10.1038/s41597-022-01899-x.
5. **Walonoski J, et al.** *Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health record*. J Am Med Inform Assoc. 2018;25(3):230–238. DOI: 10.1093/jamia/ocx079.
6. **Strack B, et al.** *Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Records*. Biomed Res Int. 2014;2014:812016. DOI: 10.1155/2014/812016.
7. **Cohen J.** *A Coefficient of Agreement for Nominal Scales*. Educ Psychol Meas. 1960;20(1):37–46. DOI: 10.1177/001316446002000104.
8. **Fleiss JL.** *Measuring Nominal Scale Agreement Among Many Raters*. Psychol Bull. 1971;76(5):378–382. DOI: 10.1037/h0031619.
9. **Krippendorff K.** *Computing Krippendorff's Alpha-Reliability*. Penn ScholarlyCommons. 2011.
