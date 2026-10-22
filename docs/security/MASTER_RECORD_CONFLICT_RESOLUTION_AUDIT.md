# Master Patient Record Conflict-Resolution Golden Evaluation Report (PH10)

## Executive Summary
This evaluation formalizes the deterministic conflict-resolution rules and source precedence hierarchy applied when synthesizing disparate clinical records into the master longitudinal patient record.

## Precedence Hierarchy Matrix

| Precedence Tier | Source Category | Description | Conflict Disposition |
|---|---|---|---|
| **Tier 1 (Authoritative)** | `EMR_INTEGRATION`, `HOSPITAL_LAB` | Clinically verified hospital records signed by practitioners | Overrides lower-tier claims in primary summary; surfaces competing claims |
| **Tier 2 (Clinical Direct)** | `SCRIBE_CONSULTATION` | Clinical encounters documented and signed by attending clinician | Primary truth for visit encounter; linked to audio provenance |
| **Tier 3 (Prescription OCR)** | `DOCUMENT_OCR` | Scanned pharmacy or hospital paper receipts | Retained as secondary evidence until reconciled by clinician |
| **Tier 4 (Self-Reported)** | `PATIENT_PORTAL`, `WEARABLE` | Patient self-entries and home sensor readings | Labeled as self-reported; never overwrites Tier 1/2 clinical diagnoses |

## Non-Destructive Invariant
- **Rule:** Lower-tier records are **never deleted or silently dropped**.
- **Audit:** When a conflict occurs (e.g. Patient claims "Normal BP" while Hospital EMR documents "Stage 2 Hypertension"), both claims are preserved in the assertion ledger, and the clinician view displays an explicit conflict alert.
