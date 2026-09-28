# Phase 7 / E11: Two-Model Large Context Utility & Replication Summary

**Experiment ID:** `GLHS-R3-E11-MODEL_REPLICATION`  
**Recorded UTC:** `2026-09-28T14:32:52.182458+00:00`  
**Total Live Completion Requests:** `48`  
**Status:** `VERIFIED_AND_CLAIM_ELIGIBLE`  

## 1. Multi-Model Replication Results (Paired Schuirmann TOST, Δ = ±0.02, α = 0.05)

| Model Family | N Cases | Strict Accuracy | Full Accuracy | Mean Paired Diff | SE | TOST p-value | 95% CI | Equivalent (±2 pp) |
|---|---|---|---|---|---|---|---|---|
| `claude-sonnet-4.6` | 8 | 0.7500 | 0.8750 | -0.1250 | 0.1250 | 7.8567e-01 | [-0.4206, +0.1706] | False |
| `gemini-3.6-flash-high` | 8 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | 0.0000e+00 | [+0.0000, +0.0000] | True |
| `gemini-3.8-flash-tiered` | 8 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | 0.0000e+00 | [+0.0000, +0.0000] | True |

## 2. Invariant Verification

- **Zero Provider Fallback Usage:** 100% genuine provider completions verified.
- **Auditability:** Every live completion request sealed with prompt tokens, completion tokens, latency, and full payload.
