# Formal Specification: Multi-Corpus External Validation Pipeline Architecture, Task Packet Schema, and Invariant Verification (E13)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Phase:** Phase 8 — External & Independent Validation (E13)  
**Module:** `protocols/external_validation/` & `evaluation/external_validation/`  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Systems Specification  
**Date:** Tue Sep 29 2026  
**Canonical Schemas:**  
- Task Packet: `glhs-external-validation-tasks-v2`  
- Protocol: `glhs-e13-external-validation-protocol-v1`  
- Run Manifest: `clara-common-offset-glhs-run.v1` / `glhs-e13-external-run-v1`  
- Summary: `glhs-e13-external-summary-v1`  
- Seal: `glhs-e13-external-validation-seal-v1`  

---

## 1. Executive Summary & Problem Formulation

In clinical artificial intelligence systems, internal validation benchmarks frequently overstate operational robustness due to shared institutional data structures, uniform electronic health record (EHR) schemas, and synthetic or localized labeling artifacts. When autonomous clinical AI agents evaluate patient health trajectories across time, domain shifts, non-standard timestamp representations, multi-encounter chronic disease progressions, and complex medication titration sequences can compromise state reconstruction and lead to severe clinical inaccuracies.

To establish true generalizability without introducing unverified claims or post-hoc data fabrication, GLHS R3 Phase 8 (External Validation E13) formalizes:
1. **Multi-Corpus External Diversity Across 4 Heterogeneous Schemas:**
   - **eICU Collaborative Research Database Demo (v2.0.1):** High-frequency ICU timeline dynamics, vital signs, and continuous vasoactive drug titrations.
   - **Synthea Synthetic FHIR Longitudinal Cohort (v3.0.0):** Multi-encounter outpatient and inpatient timelines tracking chronic disease staging and Guideline-Directed Medical Therapy (GDMT) titration.
   - **MIMIC-IV Demo on FHIR (v2.1.0):** Inpatient acute care hospitalizations, antibiotic escalation/de-escalation sequences, and diagnostic problem list revisions.
   - **Diabetes 130-US Hospitals Cohort (v1.0.0):** Multi-hospital 10-year diabetic encounter transitions, multi-regimen insulin titration, and 30-day readmission link dynamics.
2. **Canonical External Task Packet Schema (`glhs-external-validation-tasks-v2`):** A strictly versioned, standardized JSON envelope providing longitudinal event sequences, explicit ground truth state reconstruction criteria, and blinded dual-annotator plus adjudicator review packets.
3. **Deterministic Ingestion & Abstract Temporal Coordinate Mapping:** Ingestion mechanics that map non-standard relative offsets and FHIR event intervals into production GLHS primitives (`record_evidence`, `propose_assertion`, `apply_transition`, `reconstruct_state`) without fabricating absolute calendar dates or unobserved source knowledge times.
4. **Formal Invariant Checking Pipeline:** Mathematical verification of state reconstruction parity, monotonic state version advancement, temporal sequence ordering, and inter-rater reliability metrics ($\kappa, \alpha$).
5. **Red Team (E) Guardrails & Anti-Laundering Claim Bounds:** Enforcing fail-closed separation between synthetic model-based QA and independent human clinical adjudication, preventing automated evaluations from being misrepresented as human clinical validation.

---

## 2. Multi-Corpus External Diversity & Schema Audit

The external validation suite spans 4 distinct EHR schemas, each representing a unique clinical environment, temporal granularity, and state transition topology.

```text
+--------------------------------------------------------------------------------------------------+
|                                    GLHS R3 External Schemas                                      |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  [1] eICU-CRD Demo (v2.0.1)             [2] Synthea FHIR (v3.0.0)                                |
|  - High-frequency ICU offsets           - Multi-year outpatient / inpatient spans                |
|  - Relative minutes from admission      - FHIR Condition, MedicationRequest, Encounter           |
|  - Continuous vasoactive titration      - GDMT titration & CKD staging progression               |
|                                                                                                  |
|  [3] MIMIC-IV Demo on FHIR (v2.1.0)     [4] Diabetes 130-US Hospitals (v1.0.0)                   |
|  - Acute inpatient stays                - 10-year multi-hospital longitudinal encounters         |
|  - FHIR MedicationRequest, Observation  - Inpatient multi-regimen insulin switching              |
|  - Antibiotic escalation / de-escalation- 30-day readmission link dynamics                       |
+--------------------------------------------------------------------------------------------------+
```

### 2.1 eICU Collaborative Research Database (ICU Offset Dynamics & Vasoactive Titration)

- **Source Dataset & Version:** eICU Collaborative Research Database Demo v2.0.1 (Philips Healthcare / MIT LCP).
- **Clinical Focus:** High-frequency, acute critical care monitoring. Captures minute-level vital sign shifts, blood gas clearance, and rapid continuous infusion titrations.
- **Temporal Coordinate Representation:**
  - Events are recorded as relative minute offsets $\Delta t \in \mathbb{Z}$ from ICU unit admission:
    $$\text{offset\_minutes} = t_{\text{event}} - t_{\text{ICU\_admission}}$$
  - Anchor: `icu_unit_admission`.
  - Absolute clinical calendar time and source recording knowledge times are unavailable and strictly marked `UNAVAILABLE_NOT_ESTIMATED`.
- **Exemplar Clinical Dynamics (`eicu_task_001`, `eicu_task_002`):**
  - *Vasoactive Titration:* Septic shock resuscitation requiring Norepinephrine infusion starting at 0.05 mcg/kg/min ($t=0$), up-titration to 0.12 mcg/kg/min ($t=120$), down-titration to 0.04 mcg/kg/min ($t=360$), and complete discontinuation ($t=480$). The reconstructed active medication list at $t=480$ must be empty, while retaining the historical peak infusion rate of 0.12 mcg/kg/min.
  - *Metabolic Clearance:* Arterial blood gas monitoring tracking severe lactic acidosis (Lactate 4.2 mmol/L, pH 7.28 at $t=30$), partial clearance (Lactate 2.8 mmol/L at $t=240$), and complete clearance (Lactate 1.3 mmol/L at $t=720$).

### 2.2 Synthea FHIR (Chronic Disease Staging & GDMT Titration)

- **Source Dataset & Version:** Synthea Synthetic Patient Population Generator v3.0.0 (HL7 FHIR R4).
- **Clinical Focus:** Longitudinal outpatient primary care and chronic disease management across multi-year intervals ($10^5 - 10^6$ minutes).
- **Temporal Coordinate Representation:**
  - Multi-encounter timeline offsets spanning discrete primary care visits.
  - FHIR Resources: `Condition`, `MedicationRequest`, `Observation`, `Encounter`.
- **Exemplar Clinical Dynamics (`synthea_task_001`, `synthea_task_002`):**
  - *CKD Staging Progression:* Essential hypertension onset ($t=0$), followed by Chronic Kidney Disease Stage 2 development at year 1 ($t=525,600$ min, eGFR 72 mL/min/1.73m²), progressing to CKD Stage 3a at year 2 ($t=1,051,200$ min, eGFR 52 mL/min/1.73m²). The reconstructed diagnostic problem state must accurately reflect active Stage 3a without erasing underlying hypertension etiology.
  - *Heart Failure GDMT Optimization:* Heart failure with reduced ejection fraction (HFrEF) managed initially with Lisinopril 10mg + Metoprolol Succinate 25mg ($t=0$), followed by guideline-directed transition from ACE inhibitor to Angiotensin Receptor-Neprilysin Inhibitor (Sacubitril/Valsartan 49/51mg BID at $t=43,200$ min) with Lisinopril discontinuation, and subsequent addition of SGLT2 inhibitor (Empagliflozin 10mg daily at $t=86,400$ min). Reconstructed active regimen must contain 3 GDMT agents and mark Lisinopril as discontinued.

### 2.3 MIMIC-IV Demo on FHIR (Inpatient Stays & Antibiotic Escalation)

- **Source Dataset & Version:** MIMIC-IV Demo on FHIR v2.1.0 (Beth Israel Deaconess Medical Center / PhysioNet).
- **Clinical Focus:** Inpatient acute care hospital stays, emergency department presentations, and intensive care transfers.
- **Temporal Coordinate Representation:**
  - Resource timestamps (`authoredOn`, `validityPeriod.start`, `effectiveDateTime`, `issued`).
  - FHIR resource mappings: `MimicMedicationRequest.ndjson.gz`, `MimicCondition.ndjson.gz`, `MimicObservationLabevents.ndjson.gz`.
- **Exemplar Clinical Dynamics (`mimic_task_001`, `mimic_task_002`, `mimic_task_003_edge_case`):**
  - *Antibiotic Stewardship Sequence:* Empiric community-acquired sepsis treatment with Ceftriaxone 1g IV daily initiated in Emergency Department ($t=0$); escalation upon ICU transfer and clinical deterioration to broad-spectrum Vancomycin 15mg/kg Q12H + Piperacillin-Tazobactam 3.375g Q6H with Ceftriaxone discontinuation ($t=360$ min); targeted de-escalation following negative 48h blood cultures discontinuing Vancomycin while maintaining Piperacillin-Tazobactam ($t=2,880$ min).
  - *Acute on Chronic Problem Tracking:* Chronic systolic heart failure baseline ($t=0$) updated to Acute Decompensated Heart Failure upon acute volume overload admission ($t=60$ min); resolution of acute exacerbation prior to discharge ($t=4,320$ min) restoring compensated chronic status.
  - *Lab Amendment Conflict Resolution:* Initial normal Troponin T (0.04 ng/mL at $t=0$), followed by elevated result indicating NSTEMI (1.85 ng/mL at $t=180$ min), followed by laboratory amendment confirming peak Troponin T at 2.10 ng/mL ($t=360$ min). Evaluates monotonic epistemic state updating without duplicating laboratory assertions.

### 2.4 Diabetes 130-US Hospitals (Multi-Regimen Insulin & Readmissions)

- **Source Dataset & Version:** Diabetes 130-US Hospitals 1999–2008 Dataset v1.0.0 (UCI Machine Learning Repository / CC0).
- **Clinical Focus:** Multi-hospital longitudinal diabetic encounter transitions, acute glycemic decompensation, inpatient oral-to-injectable insulin transitions, and 30-day all-cause readmissions.
- **Temporal Coordinate Representation:**
  - Multi-encounter boundaries with intra-admission hour/day offsets and inter-encounter readmission intervals (up to 30 days / 43,200 minutes).
- **Exemplar Clinical Dynamics (`diabetes130_task_001`, `diabetes130_task_002`):**
  - *Complex Inpatient Insulin Adjustment:* Patient admitted on oral antidiabetic therapy (Metformin 1000mg BID + Glipizide 10mg daily with HbA1c 9.8% at $t=0$); acute inpatient switch discontinuing Glipizide and initiating human NPH Insulin 20 units QAM + Regular Insulin sliding scale ($t=1,440$ min); hospital discharge reconciliation transitioning patient to long-acting analog Insulin Glargine 18 units QHS alongside resumed Metformin ($t=4,320$ min).
  - *Readmission Continuity & Trajectory:* Index admission for severe hyperosmolar hyperglycemia (Glucose 340 mg/dL at $t=0$, discharged at $t=5,760$ min); readmission at Day 20 ($t=28,800$ min) with severe iatrogenic hypoglycemia (Glucose 48 mg/dL) requiring cross-encounter trajectory linking.

---

## 3. Canonical External Task Packet Schema (`glhs-external-validation-tasks-v2`)

The authoritative task specification document lives at `protocols/external_validation/eicu_mimic_tasks_v2.json`. All task envelopes must validate against the formal schema below.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GlhsExternalValidationTaskPacketV2",
  "type": "object",
  "required": [
    "schema_version",
    "freeze_id",
    "freeze_utc",
    "description",
    "corpora_represented",
    "tasks"
  ],
  "properties": {
    "schema_version": { "const": "glhs-external-validation-tasks-v2" },
    "freeze_id": { "type": "string", "pattern": "^GLHS-EXTERNAL-VALIDATION-TASKS-V2-[0-9]{8}$" },
    "freeze_utc": { "type": "string", "format": "date-time" },
    "description": { "type": "string" },
    "corpora_represented": {
      "type": "array",
      "items": { "enum": ["eicu", "synthea", "mimic_on_fhir", "diabetes_130"] },
      "uniqueItems": true
    },
    "tasks": {
      "type": "array",
      "items": { "$ref": "#/$defs/ExternalTask" }
    }
  },
  "$defs": {
    "ExternalTask": {
      "type": "object",
      "required": [
        "task_id",
        "corpus",
        "subject_id",
        "encounter_id",
        "domain",
        "prompt_summary",
        "longitudinal_sequence",
        "expected_ground_truth",
        "dual_annotator_packets"
      ],
      "properties": {
        "task_id": { "type": "string", "pattern": "^[a-z0-9_]+_task_[0-9]{3}(_[a-z0-9_]+)?$" },
        "corpus": { "enum": ["eicu", "synthea", "mimic_on_fhir", "diabetes_130"] },
        "subject_id": { "type": "string" },
        "encounter_id": { "type": "string" },
        "domain": {
          "enum": [
            "medications",
            "observations",
            "diagnoses_problems",
            "allergies_adverse_reactions",
            "longitudinal_continuity"
          ]
        },
        "prompt_summary": { "type": "string" },
        "longitudinal_sequence": {
          "type": "array",
          "items": { "$ref": "#/$defs/LongitudinalEvent" },
          "minItems": 2
        },
        "expected_ground_truth": {
          "type": "object",
          "required": ["state_reconstruction_correct"],
          "properties": {
            "state_reconstruction_correct": { "type": "boolean" }
          },
          "additionalProperties": true
        },
        "dual_annotator_packets": { "$ref": "#/$defs/DualAnnotatorPackets" }
      }
    },
    "LongitudinalEvent": {
      "type": "object",
      "required": ["offset_minutes", "event_type", "details", "valid_from_offset"],
      "properties": {
        "offset_minutes": { "type": "integer", "minimum": 0 },
        "event_type": { "type": "string" },
        "details": { "type": "string" },
        "valid_from_offset": { "type": "integer", "minimum": 0 }
      }
    },
    "DualAnnotatorPackets": {
      "type": "object",
      "required": ["annotator_1", "annotator_2", "adjudicator"],
      "properties": {
        "annotator_1": { "$ref": "#/$defs/AnnotatorReview" },
        "annotator_2": { "$ref": "#/$defs/AnnotatorReview" },
        "adjudicator": { "$ref": "#/$defs/AdjudicatorReview" }
      }
    },
    "AnnotatorReview": {
      "type": "object",
      "required": [
        "annotator_id",
        "rating",
        "fact_retained",
        "false_positive",
        "false_negative",
        "temporal_continuity_correct"
      ],
      "properties": {
        "annotator_id": { "type": "string" },
        "rating": { "enum": ["ACCURATE", "MINOR_DISCREPANCY", "INACCURATE"] },
        "fact_retained": { "type": "boolean" },
        "false_positive": { "type": "boolean" },
        "false_negative": { "type": "boolean" },
        "temporal_continuity_correct": { "type": "boolean" },
        "notes": { "type": "string" }
      }
    },
    "AdjudicatorReview": {
      "type": "object",
      "required": [
        "adjudicator_id",
        "consensus_rating",
        "final_fact_retained",
        "final_false_positive",
        "final_false_negative",
        "adjudication_status"
      ],
      "properties": {
        "adjudicator_id": { "type": "string" },
        "consensus_rating": { "enum": ["ACCURATE", "MINOR_DISCREPANCY", "INACCURATE"] },
        "final_fact_retained": { "type": "boolean" },
        "final_false_positive": { "type": "boolean" },
        "final_false_negative": { "type": "boolean" },
        "adjudication_status": { "enum": ["CONCORDANT", "RESOLVED_BY_ADJUDICATOR", "FAILED_CONSENSUS"] }
      }
    }
  }
}
```

---

## 4. Blinded Dual-Annotator & Adjudication Protocol Architecture

External validation employs a blinded dual-annotator plus adjudicator consensus architecture.

```text
+--------------------------------------------------------------------------------------------------+
|                            Blinded Review Packet Protocol Flow                                   |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|       +------------------------------------+      +------------------------------------+         |
|       |     Blinded Annotator 1 (ann_01)   |      |     Blinded Annotator 2 (ann_02)   |         |
|       |     - Rating: ACCURATE             |      |     - Rating: MINOR_DISCREPANCY    |         |
|       |     - Fact Retained: True          |      |     - Fact Retained: True          |         |
|       |     - False Positive: False        |      |     - False Positive: True         |         |
|       |     - False Negative: False        |      |     - False Negative: False        |         |
|       +------------------------------------+      +------------------------------------+         |
|                          \                                      /                                |
|                           \                                    /                                 |
|                            v                                  v                                  |
|                 +-------------------------------------------------------+                        |
|                 |          Automated Agreement Evaluation Engine        |                        |
|                 |          - Cohen's Kappa (kappa)                      |                        |
|                 |          - Krippendorff's Alpha (alpha)               |                        |
|                 +-------------------------------------------------------+                        |
|                                             |                                                    |
|                                    Concordant? (Rating 1 == Rating 2)                            |
|                                    /                         \                                   |
|                              YES  /                           \  NO                              |
|                                  v                             v                                 |
|               +-----------------------------+     +-------------------------------+              |
|               | Adjudication Status:        |     | Blinded Clinical Adjudicator  |              |
|               |   CONCORDANT                |     |   (adj_01)                    |              |
|               |                             |     | - Resolves Discrepancy        |              |
|               | Final Verdict = Ann 1       |     | - Consensus Rating: ACCURATE  |              |
|               +-----------------------------+     | - Status:                     |              |
|                                                   |     RESOLVED_BY_ADJUDICATOR   |              |
|                                                   +-------------------------------+              |
+--------------------------------------------------------------------------------------------------+
```

### 4.1 Rating Space & Binary Metric Mapping

Each reviewer evaluates the reconstructed snapshot against the primary source record across 4 orthogonal dimensions:
1. **Categorical Rating ($R \in \{\text{ACCURATE}, \text{MINOR\_DISCREPANCY}, \text{INACCURATE}\}$):**
   - `ACCURATE`: Reconstructed state matches ground truth in all clinically relevant entities, values, and intervals.
   - `MINOR_DISCREPANCY`: Non-critical formatting, transient duplicate assertion, or harmless time-boundary roundoff that does not alter clinical decision-making.
   - `INACCURATE`: State omits active therapy, retains discontinued therapy, misidentifies acute condition status, or corrupts numeric dosing/lab values.
2. **Fact Retention ($F_{\text{ret}} \in \{0, 1\}$):**
   - $F_{\text{ret}} = 1$: All essential clinical entities present in the ground truth timeline are correctly retained in the state.
3. **False Positive ($F_{\text{pos}} \in \{0, 1\}$):**
   - $F_{\text{pos}} = 1$: Reconstructed state hallucinated or persisted an entity that was never ordered or had been discontinued.
4. **False Negative ($F_{\text{neg}} \in \{0, 1\}$):**
   - $F_{\text{neg}} = 1$: Reconstructed state omitted an active condition, medication, or critical observation.

### 4.2 Concordance & Adjudication Rules

Let $R_1, R_2$ be the ratings assigned by Annotator 1 and Annotator 2.
- **Concordance:** If $R_1 = R_2$, the adjudication status is set to `CONCORDANT`, and the consensus values inherit directly:
  $$\text{consensus\_rating} = R_1, \quad \text{final\_fact\_retained} = F_{\text{ret}, 1}$$
- **Discrepancy:** If $R_1 \ne R_2$, the task packet is flagged for review by the third-party clinical adjudicator ($A$).
  - The adjudicator evaluates the disputed packet blindly and emits $R_A, F_{\text{ret}, A}, F_{\text{pos}, A}, F_{\text{neg}, A}$.
  - The status is marked `RESOLVED_BY_ADJUDICATOR`.
  - Exemplar: In `mimic_task_003_edge_case`, Annotator 1 rated `ACCURATE` while Annotator 2 rated `MINOR_DISCREPANCY` due to an intermediate lab report before amendment. Adjudicator `adj_01` resolved the consensus rating to `ACCURATE` with status `RESOLVED_BY_ADJUDICATOR`.

---

## 5. Deterministic Ingestion & Temporal Coordinate Mapping

A primary risk in external EHR validation is the arbitrary creation or "hallucination" of calendar timestamps for datasets that only provide relative ICU or encounter offsets. GLHS enforces strict temporal non-invention invariants.

```text
+--------------------------------------------------------------------------------------------------+
|                            GLHS Deterministic Ingestion Pipeline                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   External Event: [ offset_minutes: 120, drug: Norepinephrine, rate: 0.12 mcg/kg/min ]           |
|                                              |                                                   |
|                                              v                                                   |
|   1. Abstract Epoch Translation:                                                                 |
|      valid_from = RELATIVE_EPOCH + timedelta(minutes=120)                                        |
|      valid_to   = RELATIVE_EPOCH + timedelta(minutes=360) - 1 microsecond                        |
|                                              |                                                   |
|                                              v                                                   |
|   2. Register Source Reference (HealthSourceReference):                                          |
|      source_kind = "external_structured_demo"                                                    |
|      source_identity = sha256(event_pointer)                                                     |
|      checksum = sha256(canonical_value)                                                         |
|                                              |                                                   |
|                                              v                                                   |
|   3. Record Evidence (GlhsEvidence):                                                             |
|      record_evidence(profile_id, valid_from, valid_to, time_precision="unknown")                 |
|                                              |                                                   |
|                                              v                                                   |
|   4. Propose Assertion (GlhsAssertion):                                                          |
|      semantic_key = "eicu_offset:medications:eicu_task_001"                                      |
|      epistemic_state = "extracted"                                                               |
|      value = { ... relative coordinate details, absolute_time: UNAVAILABLE }                     |
|                                              |                                                   |
|                                              v                                                   |
|   5. Apply Transition (GlhsTransition):                                                          |
|      apply_transition(scope, assertion, action="activate", expected_version=v_curr)              |
|      -> Monotonic CAS increment: state_version advances v -> v + 1                               |
|                                              |                                                   |
|                                              v                                                   |
|   6. Snapshot Reconstruction (GlhsStateVersion):                                                 |
|      reconstruct_state(profile_id, valid_at=cutoff, known_at=POST_INGEST_CUTOFF)                 |
+--------------------------------------------------------------------------------------------------+
```

### 5.1 Temporal Mapping Coordinate Contract

As specified in `run_common_offset_glhs.py`, the temporal mapping configuration is strictly bounded:
```python
TEMPORAL_MAPPING = {
    "source_coordinate": "minutes_relative_to_icu_unit_admission",
    "encoding_epoch": "2000-01-01T00:00:00_abstract_naive_coordinate",
    "interval_rule": "event_valid_until_one_microsecond_before_next_distinct_offset",
    "absolute_clinical_time": "UNAVAILABLE_NOT_ESTIMATED",
    "source_knowledge_time": "UNAVAILABLE_NOT_ESTIMATED",
    "known_at_for_reconstruction": "post_ingest_processing_cutoff_not_source_time",
}
```

### 5.2 Microsecond-Preceding Interval Slicing Rule

To prevent instantaneous overlaps or ill-defined state versions when discrete transitions occur at distinct offsets, GLHS constructs interval bounds using the strict predecessor rule:
Given distinct chronological offsets $O = \{o_0, o_1, \dots, o_{K-1}\}$ with $o_k < o_{k+1}$:
$$\text{valid\_from}(e_k) = t_{\text{epoch}} + o_k$$
$$\text{valid\_to}(e_k) = \begin{cases} (t_{\text{epoch}} + o_{k+1}) - 1\,\mu\text{s} & \text{if } k < K-1 \\ \text{NULL (unbounded)} & \text{if } k = K-1 \end{cases}$$

This guarantees pairwise disjointness across non-overlapping intervals:
$$[ \text{valid\_from}(e_k), \text{valid\_to}(e_k) ] \cap [ \text{valid\_from}(e_{k+1}), \text{valid\_to}(e_{k+1}) ] = \emptyset$$

### 5.3 Ingestion Service Sequence

Every external task is processed through the 4 production API service methods:
1. `record_evidence(db, profile_id, data)`: Ingests raw source pointers into `GlhsEvidence` with SHA-256 fingerprinting.
2. `propose_assertion(db, profile_id, actor_user_id, data, evidence)`: Constructs typed assertion entity with domain classification (`DOMAIN_MAP`: `allergies`, `conditions`, `medications`, `observations`).
3. `apply_transition(db, scope, assertion, action="activate", expected_state_version)`: Atomically validates Compare-And-Swap (CAS) state version and persists `GlhsTransition`. Enforces $v_{\text{result}} > v_{\text{base}}$.
4. `reconstruct_state(db, profile_id, valid_at, known_at)`: Executes temporal point-in-time snapshot reconstruction over active assertions.

---

## 6. Snapshot Reconstruction & Strong Parity Verification

In `run_common_offset_glhs.py`, GLHS evaluates state reconstruction against two reference systems:
1. `valid_offset_resolver_strong_parity_reference` ($S_{\text{ref}}$): Selects the unique event corresponding to $\max(\text{valid\_offset\_minutes})$. If multiple events share the maximum offset, it returns `None`.
2. `input_order_baseline` ($S_{\text{base}}$): Naively selects the event with the highest raw row index (`source_index`), vulnerable to out-of-order data arrival.
3. `production_glhs_reconstruction` ($S_{\text{glhs}}$): The full production GLHS execution path querying `reconstruct_state()` at $t_{\text{cutoff}} = \max(\text{offset})$ with $t_{\text{known}} = \text{POST\_INGEST\_CUTOFF}$.

### 6.1 State Reconstruction Parity Equation

For all tasks $T \in \mathcal{T}$:
$$\text{Selected}(S_{\text{glhs}}, T) = \text{Target}(T) \iff \text{Selected}(S_{\text{ref}}, T) = \text{Target}(T)$$
Any discrepancy between production reconstruction and the unique latest valid offset resolver immediately fails the validation suite.

---

## 7. Formal Invariant Checking Pipeline

The validation suite enforces 6 formal system and statistical invariants:

$$\begin{array}{c}
\mathcal{I}_1: \text{Monotonic State Version Increment} \\
\forall i \in \{0, \dots, N-1\}: v_{i+1} > v_i \quad \text{and} \quad v_{i+1} = v_i + 1
\end{array}$$

$$\begin{array}{c}
\mathcal{I}_2: \text{Temporal Sequence Monotonicity} \\
\forall k \in \{0, \dots, K-2\}: \text{valid\_from\_offset}(e_k) \le \text{valid\_from\_offset}(e_{k+1})
\end{array}$$

$$\begin{array}{c}
\mathcal{I}_3: \text{Zero-Discrepancy State Reconstruction Parity} \\
\sum_{T \in \mathcal{T}} \mathbb{I}(\text{Selected}(S_{\text{glhs}}, T) \ne \text{Target}(T)) = 0
\end{array}$$

$$\begin{array}{c}
\mathcal{I}_4: \text{Inter-Rater Reliability Thresholds (Human Claim Invariant)} \\
\text{If mode} = \text{human} \implies \kappa \ge 0.80 \quad \text{and} \quad \alpha \ge 0.80
\end{array}$$

$$\begin{array}{c}
\mathcal{I}_5: \text{Fact Retention & Error Rate Bounds} \\
P(F_{\text{ret}} = 1) \ge 0.90, \quad \text{FPR} \le 0.05, \quad \text{FNR} \le 0.05 \quad (\text{at } 95\% \text{ Wilson CI})
\end{array}$$

$$\begin{array}{c}
\mathcal{I}_6: \text{Red Team Non-Laundering Invariant} \\
\text{mode} \in \{\text{synthetic}, \text{not\_run}\} \implies \text{independent\_human\_claim\_eligible} = \text{False}
\end{array}$$

### 7.1 Mathematical Formulations of Statistical Invariants

#### Cohen's Kappa ($\kappa$)
Given $N$ paired ratings $(r_{1, i}, r_{2, i})$ across categories $C$:
$$p_o = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(r_{1, i} = r_{2, i})$$
$$p_e = \sum_{c \in C} \left(\frac{1}{N} \sum_{i=1}^N \mathbb{I}(r_{1, i} = c)\right) \left(\frac{1}{N} \sum_{i=1}^N \mathbb{I}(r_{2, i} = c)\right)$$
$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

#### Krippendorff's Alpha ($\alpha$) for Nominal Ratings
Let $N$ be paired units, total ratings $2N$. Observed disagreement $D_o = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(r_{1, i} \ne r_{2, i})$.
Let $n_c$ be the total occurrences of category $c$ across both raters:
$$D_e = 1 - \sum_{c \in C} \frac{n_c (n_c - 1)}{2N(2N - 1)}$$
$$\alpha = 1 - \frac{D_o}{D_e}$$

#### Wilson Score 95% Confidence Interval
For $k$ successes out of $n$ trials with $z = 1.95996$:
$$\hat{p} = \frac{k}{n}, \quad \text{center} = \frac{\hat{p} + \frac{z^2}{2n}}{1 + \frac{z^2}{n}}, \quad \text{spread} = \frac{z \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$
$$\text{CI}_{95\%} = [\max(0, \text{center} - \text{spread}), \min(1, \text{center} + \text{spread})]$$

---

## 8. Red Team (E) Guardrails & Claim Eligibility Matrix

A core mandate of the GLHS R3 architecture is preventing synthetic or automated model evaluations from being laundered into claims of "independent human clinician validation".

### 8.1 The Model-As-Human Laundering Failure Mode

In automated benchmarking, systems frequently use an LLM (e.g. GPT-4, Claude, or DeepSeek) to evaluate another LLM's outputs, and subsequently report high agreement scores without human clinician involvement.
Red Team (E) explicitly forbids this pattern:
$$\text{Model QA} \ne \text{Independent Human Adjudication}$$

### 8.2 Claim Eligibility Truth Table

| Execution Mode | Annotator Origin | Adjudicator Origin | Status Output | Human Adjudication Status | Claim Eligible? | Allowed Manuscript Wording |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `human` | Verified Clinical Rater | Verified Clinical Adjudicator | `INDEPENDENT_HUMAN_ADJUDICATION` | `COMPLETED` | **YES** | "Validated by independent blinded dual-clinician review." |
| `synthetic` | Automated Model QA | Automated Model Adjudication | `SYNTHETIC_MODEL_ADJUDICATION` | `NOT_RUN_HUMAN_UNAVAILABLE` | **NO** | "Source-derived structural verification via automated task packets." |
| `not_run` | Unassigned | Unassigned | `NOT_RUN` | `NOT_RUN_HUMAN_UNAVAILABLE` | **NO** | "Independent human clinical validation remains not run." |

If `mode == "synthetic"`, `independent_human_claim_eligible` is hard-coded to `False`, and any attempt to assert a human clinical claim raises a verification error during artifact sealing.

---

## 9. Verification, Sealing, and Offline Reproduction Architecture

To ensure end-to-end cryptographic reproducibility, Phase 8 defines a complete sealing and offline verification protocol implemented in `evaluation/external_validation/seal.py` and `reproduce_e13.py`.

```text
+--------------------------------------------------------------------------------------------------+
|                            E13 Sealing & Offline Reproduction                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   1. Execution (run_e13_external.py)                                                             |
|      Emits: raw/results.jsonl, raw/execution_metadata.json                                       |
|                                                                                                  |
|   2. Analysis (analyze.py)                                                                       |
|      Emits: derived/summary.json, derived/summary.md                                             |
|                                                                                                  |
|   3. Validation (validation.json)                                                                |
|      Records verification status, point estimates, and CI bounds                                 |
|                                                                                                  |
|   4. Cryptographic Checksum Generation (checksums.sha256)                                       |
|      Computes SHA-256 for all raw, derived, and protocol files                                   |
|                                                                                                  |
|   5. Cryptographic Sealing (seal.json)                                                           |
|      Binds protocol_payload_sha256, raw_results_sha256, summary_sha256,                         |
|      and validation_sha256 into a single immutable seal document                                |
|                                                                                                  |
|   6. Offline Reproduction (reproduce_e13.py)                                                     |
|      - Disables all network sockets fail-closed (socket.socket = forbidden)                      |
|      - Verifies every hash in checksums.sha256                                                   |
|      - Recomputes summary.json from raw/results.jsonl and verifies byte-for-byte identity        |
+--------------------------------------------------------------------------------------------------+
```

### 9.1 Fail-Closed Network Disconnection

The offline reproduction runner `reproduce_e13.py` enforces network isolation at process startup:
```python
def disable_network() -> None:
    def forbidden_socket(*args: Any, **kwargs: Any) -> Any:
        raise NetworkAccessProhibitedError("network_access_prohibited_during_reproduction")
    socket.socket = forbidden_socket
    socket.create_connection = forbidden_socket
    socket.getaddrinfo = forbidden_socket
    socket.gethostbyname = forbidden_socket
```
This guarantees that offline reproduction cannot fetch remote packages, call remote APIs, or leak evaluation tokens.

### 9.2 Cryptographic Seal Schema (`glhs-e13-external-validation-seal-v1`)

The final seal document `protocols/E13_external_validation/seal.json` binds the artifact tree:
- `schema_version`: `glhs-e13-external-validation-seal-v1`
- `status`: `SEALED`
- `freeze_id`: `GLHS-EXTERNAL-VALIDATION-E13-20260928-01`
- `git_sha`: SHA-1 commit hash of the implementation
- `raw_results_sha256`: SHA-256 digest of `raw/results.jsonl`
- `derived_summary_sha256`: SHA-256 digest of `derived/summary.json`
- `validation_sha256`: SHA-256 digest of `validation.json`
- `sealed_files_count`: Total count of cryptographically validated files

---

## 10. Traceability Matrix & Conformance Checklist

The table below maps each external validation task to its source corpus, clinical dynamics, evaluated invariants, and test verification targets.

| Task ID | Source Corpus | Clinical Scenario | Evaluated Invariants | Reference Runner / Test Target |
| :--- | :--- | :--- | :--- | :--- |
| `eicu_task_001` | `eicu` | Norepinephrine titration (0.05 $\to$ 0.12 $\to$ 0.04 $\to$ 0 mcg/kg/min) | $\mathcal{I}_1, \mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_common_offset_glhs.py`, `test_e13_tasks_v2_schema` |
| `eicu_task_002` | `eicu` | Arterial lactate clearance (4.2 $\to$ 2.8 $\to$ 1.3 mmol/L) | $\mathcal{I}_1, \mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_common_offset_glhs.py`, `test_e13_tasks_v2_schema` |
| `synthea_task_001` | `synthea` | Multi-year CKD stage progression (Stage 2 $\to$ Stage 3a) | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_e13_external.py`, `test_run_e13_execution` |
| `synthea_task_002` | `synthea` | Heart failure GDMT titration (Lisinopril $\to$ ARNI + SGLT2i) | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_e13_external.py`, `test_run_e13_execution` |
| `mimic_task_001` | `mimic_on_fhir` | Inpatient antibiotic escalation & de-escalation for sepsis | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `prepare_mimic_demo_fhir.py`, `test_e13_tasks_v2_schema` |
| `mimic_task_002` | `mimic_on_fhir` | Acute decompensated heart failure problem list update | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `prepare_mimic_demo_fhir.py`, `test_e13_tasks_v2_schema` |
| `diabetes130_task_001` | `diabetes_130` | Inpatient oral-to-insulin multi-regimen transition | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_e13_external.py`, `test_run_e13_execution` |
| `diabetes130_task_002` | `diabetes_130` | 30-day readmission linkage & severe hypoglycemia trajectory | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_5$ | `run_e13_external.py`, `test_run_e13_execution` |
| `mimic_task_003_edge_case` | `mimic_on_fhir` | Conflicting lab amendment & dual-annotator adjudication | $\mathcal{I}_2, \mathcal{I}_3, \mathcal{I}_4, \mathcal{I}_5$ | `run_e13_external.py`, `test_red_team_guardrails` |

---

## 11. Systems Architecture Conformance Sign-Off

The multi-corpus external validation architecture specified herein is frozen and locked against regression:
- **Task Packet Schema:** Validated against `glhs-external-validation-tasks-v2` across all 4 target corpora.
- **Production GLHS Integration:** Verified on in-process API service primitives (`record_evidence`, `propose_assertion`, `apply_transition`, `reconstruct_state`) with 100% parity against the strong relative-offset resolver.
- **Red Team (E) Safety:** Verified by automated test suites (`test_red_team_guardrails`, `test_reproduce_e13_offline`) preventing model QA from masquerading as human clinician validation.
- **Cryptographic Provenance:** Enforced via SHA-256 manifest hashing, checksums file verification, and fail-closed offline reproduction.
