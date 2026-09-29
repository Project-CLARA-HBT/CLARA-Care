# Phase 7 / E11: Two-Model Large Context Utility & Replication Summary

**Experiment ID:** `GLHS-R3-E11-MODEL_REPLICATION`  
**Recorded UTC:** `2026-09-28T14:32:52.182458+00:00`  
**Classification:** `EXPLORATORY_PILOT_PROBE` / `PILOT_LEDGER_EXPLORATORY`  
**Total Live Completion Requests:** `48`  
**Status:** `VERIFIED_AND_CLAIM_ELIGIBLE` (Pilot Ledger / Format-Taxonomy Validation; `claim_eligible: false` for Confirmatory Equivalence)  

> **Note on Study Scope & Statistical Power:** The 48-request live execution is an exploratory format/taxonomy pilot evaluating latency, format compliance, and router routing behavior across 3 models, NOT a confirmatory prospective equivalence study. The full prospective cohort requires $N=384$ powered observations.

## 1. Multi-Model Replication Results (Paired Schuirmann TOST, Δ = ±0.02, α = 0.05)

| Model Family | N Cases | Strict Accuracy | Full Accuracy | Mean Paired Diff | SE | TOST p-value | 95% CI | Equivalent (±2 pp) |
|---|---|---|---|---|---|---|---|---|
| `claude-sonnet-4.6` | 8 | 0.7500 | 0.8750 | -0.1250 | 0.1250 | 7.8567e-01 | [-0.4206, +0.1706] | False |
| `gemini-3.6-flash-high` | 8 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | None (N=8 underpowered) | [+0.0000, +0.0000] | False |
| `gemini-3.8-flash-tiered` | 8 | 1.0000 | 1.0000 | +0.0000 | 0.0000 | None (N=8 underpowered) | [+0.0000, +0.0000] | False |

## 2. Invariant Verification & Model Routing Drift Detection

- **Record-by-Record Provider Ledger Audit:** Audited all 48 empirical requests across token usage (89,054 prompt tokens, 2,471 completion tokens), payload non-emptiness, and 12-class error taxonomy compliance.
- **Model Routing Drift & Fallbacks Observed (`fallbacks_observed = 9` / 48 requests; 23 alias normalizations):**
  - `claude-sonnet-4.6` (16 requests): 16/16 reported as `claude-sonnet-4-6` (provider deployment slug normalization alias).
  - `gemini-3.8-flash-tiered` (16 requests): experienced 7 proxy wrapper alias normalizations and 9 upstream fallbacks:
    - 7 requests reported as `antigravity/gemini-3.8-flash-tiered` (upstream agent proxy wrapper prefix alias normalization).
    - 4 requests reported as `gemini-3.7-flash-tiered` (cross-generation model downgrade fallback).
    - 5 requests reported as `gemini-3.6-flash-tiered` (cross-generation model downgrade fallback).
  - `gemini-3.6-flash-high` (16 requests): 16/16 reported exactly as `gemini-3.6-flash-high` (0 routing drift, exact model fidelity).
- **Auditability:** Every live completion request sealed with prompt tokens, completion tokens, latency, and full payload.
