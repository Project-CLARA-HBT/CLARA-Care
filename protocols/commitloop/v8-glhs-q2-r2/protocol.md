# CommitLoop Phase E11/E12 prospective protocol: v8-glhs-q2-r2

Status: `FROZEN_PROSPECTIVE`. Synthetic software evaluation for Phase 11 (E11: Two-Model Large Context Replication) and Phase 12 (E12: Malformed-Output Sensitivity).

## Research Questions

1. **E11 (Two-Model Large Context Replication):** Across two genuinely distinct model families (`claude-sonnet-4.6` and `gemini-3.6-flash-high`), does `glhs_hybrid_thss_strict` achieve statistical equivalence to `full_authorized_history` within a +/- 2 percentage point margin ($\Delta = 0.02$) on subject-level exact decision accuracy under task-bounded context minimization?
2. **E12 (Malformed-Output Sensitivity):** What is the prospective distribution across the 12-class error taxonomy, and how do sensitivity recovery arms (R0 ITT primary, R1 deterministic local repair, R2 1 identical prompt retry, R3 1 constrained repair prompt) affect accuracy and recovery rates across models, conditions, and task families?

## Cohorts & Design

- **Cohort Differentiation:**
  - **Pilot Live Provider Probe Ledger:** $N = 48$ live requests ($N = 8$ benchmark cases $\times 2$ conditions $\times 3$ model configurations) for latency, error taxonomy, and format validation on real provider endpoints. Because $N = 8 < 384$, this pilot probe ledger is underpowered for statistical equivalence testing and cannot be used to confirm TOST equivalence (zero-variance on $N < 384$ yields $p_{\text{TOST}} = \text{NaN}/\text{None}$, not $p = 0.0$).
  - **Full Prospective Powered Cohort:** $N = 384$ independent synthetic subjects (balanced 48 per held-out stratum across 8 strata) powered for Paired Schuirmann TOST equivalence testing within $\pm 2$ percentage points ($\Delta = 0.02$).
- **Unit of Analysis:** Independent synthetic subjects ($N = 384$), balanced 48 per held-out stratum across 8 strata.
- **Model Families (No Fallback Permitted):**
  - Primary Model: `claude-sonnet-4.6` (Anthropic family via router).
  - Secondary Model: `gemini-3.6-flash-high` (Google DeepMind family via router).
  - Fallback is strictly prohibited (`fallback: false`). Any model substitution invalidates the run.
- **Primary Contrast:** `glhs_hybrid_thss_strict` vs `full_authorized_history`.
- **Interleaved Request Grid:** Requests are issued in an interleaved, randomized grid across models and conditions to eliminate temporal provider bias and backend state drift.
- **Primary Endpoint:** All three state axes (`lifecycle_state`, `evidence_state`, `timeliness_state`) exactly match deterministic gold standards.
- **Intention-To-Treat (ITT) Invariant:** Missing, malformed, truncated, or failed provider outputs are scored as 0 (incorrect) and retained in the denominator. No subject or cell is excluded post-hoc in the primary R0 analysis.

## Equivalence Bounds & Power (E11)

- **Equivalence Margin:** $\Delta = 0.02$ (+/- 2.0 percentage points).
- **Statistical Test:** Paired subject-level Schuirmann Two One-Sided Tests (TOST) at $\alpha = 0.05$.
- **Zero-Variance & Power Rules:**
  - When paired differences have zero variance ($s_d = 0$) and $\bar{d} = 0$:
    - If $N < 384$ (e.g., $N=8$ pilot ledger cases), TOST equivalence cannot be claimed; $p_{\text{TOST}}$ is set to `NaN`/`None` and annotated as underpowered.
    - If $N \ge 384$ (powered cohort) and $s_d = 0$ with $\bar{d} = 0$, the 90% confidence interval is strictly $[0, 0] \subset [-0.02, +0.02]$, yielding $p_{\text{TOST}} = 0.0001$.
- **Confidence Intervals:** Paired subject-level 95% bootstrap CIs (10,000 resamples, master seed = 2026082008).
- **Directional Test:** Exact two-sided paired sign test excluding zero-differences from sign denominator.
- **Power Target:** Planned for 90% power to detect non-inferiority/equivalence within $\Delta = 0.02$ on $N \ge 384$.

## Prospective 12-Class Error Taxonomy (E12)

1. `invalid_json`: Raw response body fails JSON parsing syntax.
2. `schema_mismatch`: Parsed JSON fails target prediction schema validation.
3. `truncation`: Response cut off due to max token limit or missing closing delimiter.
4. `refusal`: Provider/model policy refusal or safety block.
5. `empty_response`: Response payload is zero-length or whitespace only.
6. `provider_error`: Provider 5xx HTTP server or gateway protocol error.
7. `wrong_model`: Returned model ID does not match requested model ID.
8. `timeout`: Request timed out before receiving complete response.
9. `content_format_violation`: Non-JSON text wrapper / markdown fence rule violation.
10. `semantic_failure`: Valid JSON schema output containing logically impossible state combinations.
11. `rate_limit_exhaustion`: Provider HTTP 429 rate limit or quota exhaustion.
12. `unclassified_error`: Any unclassified failure.

## Sensitivity Recovery Arms (E12)

- **R0 (ITT / Primary):** Raw initial output. Missing/malformed scored as 0. All 384 subjects retained.
- **R1 (Deterministic Local Repair):** Local text sanitization (markdown fence removal, trailing comma fix, JSON object extraction) with zero network calls.
- **R2 (1 Identical Prompt Retry):** Re-issue 1 identical API request upon initial malformed response.
- **R3 (1 Constrained Repair Prompt):** Re-issue 1 targeted follow-up prompt including error diagnostic and JSON schema instructions.

## Freeze and Execution Gate

Before any provider call:
1. Validate prior-cohort exclusion registry against v5/v6/v7 cohorts.
2. Verify clean git status for tracked files.
3. Verify provider probe returns exact expected model IDs without fallbacks.
4. Seal implementation git SHA, cohort sha256, schema sha256, prompt sha256, and generate `checksums.sha256`.
5. Run offline verification suite with networking disabled (`reproduce_e11.py`, `reproduce_e12.py`).
