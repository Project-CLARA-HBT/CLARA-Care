# Runbook: Clinical Data Dictionary & Vocabulary Cutover Plan (PH10)

## 1. Overview
Governs the operational cutover, curation, and validation of standardized clinical vocabulary codes in `medical_vocabulary_codes` across Vietnamese hospitals and clinics.

## 2. Seed Data Ingestion & Curation Procedure
When new Vietnamese Ministry of Health (MOH) circulars or LOINC/ICD-10 releases are published:
1. **Download Official Dataset:** Acquire official CSV/XML from authorized source.
2. **Compute Release SHA-256:**
   ```bash
   sha256sum moh_drug_circular_latest.csv
   ```
3. **Execute Curation CLI:**
   ```bash
   python3 -m clara_api.ops.ingest_vocabulary --source "moh_drug_circular_latest.csv" --system "VN_CIRCULAR"
   ```
4. **Clinical Pharmacist Review:**
   A qualified clinical pharmacist must review and sign off on any drug-interaction mapping adjustments before activation.

## 3. Rollback & Stale Mapping Handling
- Inactive mappings are marked `is_active = False` rather than deleted, preserving historical prescription audit trails.
- If a bad vocabulary release occurs:
  ```bash
  python3 -m clara_api.ops.rollback_vocabulary --system "VN_CIRCULAR" --before-timestamp "2026-10-22T00:00:00Z"
  ```
