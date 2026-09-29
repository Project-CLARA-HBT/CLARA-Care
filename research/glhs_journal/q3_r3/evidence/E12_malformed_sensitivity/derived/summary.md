# Phase 7 / E12: Malformed-Output Sensitivity & Error Taxonomy Analysis Summary

**Experiment ID:** `GLHS-R3-E12-MALFORMED_SENSITIVITY`  
**Recorded UTC:** `2026-09-28T14:32:52.182458+00:00`  
**Total Evaluated Cells:** `48`  
**Status:** `VERIFIED_AND_CLAIM_ELIGIBLE`  

## 1. Prospective 12-Class Error Taxonomy Breakdown

| Error Class | Count |
|---|---|
| `invalid_json` | 2 |
| `schema_mismatch` | 0 |
| `truncation` | 0 |
| `refusal` | 0 |
| `empty_response` | 0 |
| `provider_error` | 0 |
| `wrong_model` | 0 |
| `timeout` | 0 |
| `content_format_violation` | 0 |
| `semantic_failure` | 0 |
| `rate_limit` | 0 |
| `unclassified` | 0 |

## 2. Sensitivity Recovery Arms Performance (R0–R3)

| Recovery Arm | Correct Cells | Accuracy | Repairs | Accuracy Gain over R0 |
|---|---|---|---|---|
| `R0_ITT_Primary` | 45 | 0.9375 | 0 | N/A |
| `R1_Local_Repair` | 45 | 0.9375 | 1 | +0.0000 |
| `R2_Identical_Retry` | 45 | 0.9375 | 1 | +0.0000 |
| `R3_Constrained_Repair` | 45 | 0.9375 | 1 | +0.0000 |

## 3. Invariant Verification & Model Drift Context

- **Fail-Closed Gate:** Malformed outputs fail closed with structured 12-class error reasons.
- **Intention-To-Treat Primary:** Raw ITT performance (R0) is primary scorable metric; recovery arms (R1..R3) serve as diagnostic bounds.
- **Provider Ledger & Model Routing Drift Auditing:** The 48 evaluated cells originate from empirical provider requests exhibiting 32 model routing drift events (16 deployment slug normalizations, 7 upstream proxy wrapper drifts, and 9 cross-generation fallbacks). Sensitivity recovery arms evaluate error recovery independently under these real provider dynamics.
