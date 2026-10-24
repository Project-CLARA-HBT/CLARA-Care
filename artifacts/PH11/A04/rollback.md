# Rollback Plan — PH11 A04 (Consent and Provenance Mapping)

## Pre-Rollback State
- Base commit SHA: `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
- Branch: `phase/ph11-a04`

## Rollback Procedure
1. Revert modifications to `services/ml/src/clara_ml/config.py`:
   ```bash
   git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- services/ml/src/clara_ml/config.py
   ```
2. Remove newly added FHIR consent and provenance module:
   ```bash
   rm -f services/ml/src/clara_ml/fhir_consent_provenance.py
   ```
3. Remove evaluation unit tests:
   ```bash
   rm -f evaluation/tests/test_fhir_consent_provenance.py
   ```
4. Remove phase deliverables:
   ```bash
   rm -rf artifacts/PH11/A04
   ```
5. Verification:
   ```bash
   git status
   git diff
   ```
