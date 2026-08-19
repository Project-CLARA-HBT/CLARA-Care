# Budget-fair GovMut follow-up — design and frozen budget (GMT-04 / F-011..F-014)

Status: **design frozen; budget calibration complete; budget-fair execution gated
on W9 promotion + human review.** No model calls are made by any artifact in
this design.

## 1. Why a separate budget-fair analysis is required (GMT-04)

W8's four strategies ran with **unconstrained wall-clock budgets**: M3 executed
the full union of M0+M1+M2 suites across five Hypothesis seeds, so it naturally
spent far more wall-clock time per mutant (W8 sealed `runtime_stats`: M3 total
~8.9 M ms across 225 executions, M0 ~1.1 M ms across 45, M1 ~0.98 M ms, M2
~2.7 M ms). The W8 mutation-score ranking (M0 .356, M1 .089, M2 .133, M3 .444)
is therefore a **raw, non-budget-normalized** ranking. It answers "does a more
comprehensive strategy detect more faults?" but NOT "is M3 the most
cost-effective detector per unit of wall-clock budget?".

The raw ranking must **explicitly remain non-budget-normalized** (GMT-04); the
budget-fair analysis is a *second, separate* analysis, not a re-normalization of
W8.

## 2. M3 is a union superset — raw-score monotonicity expectation

The frozen method matrix defines M3 as the union of the M0+M1+M2 suites
(`suite_matrix.py`: `M3_combined == M0 + M1 + M2`). Consequently M3's
detection is a superset of each component's, and its raw score is *weakly
monotonic* with respect to them (W8: M3 kills 20 of the 20 union-killed
mutants, with zero M3-only-detected gaps over the components). The interesting
comparison is therefore NOT "does M3 win" but **"how much extra detection does
each additional cost tier buy"** — i.e. incremental detection per additional
wall-clock budget, and which fault families each tier uniquely covers.

## 3. The novel question

- **Q1 (incremental detection per cost):** with an equal per-mutant budget B,
  do M1 and M2 add *any* unique kills over M0, and what does each additional
  unique kill cost in wall-clock terms? (W8, non-budget-normalized, already
  hints M1/M2 add almost nothing on commitment-gateway mutants.)
- **Q2 (fault-family coverage per cost tier):** do the replayed/reconstruction
  faults targeted by W9 (commitment-gateway reconstruction, governance-cache,
  persistence-reconstruction) become observable by any tier under the equal
  budget, and if so which tier detects them first (time-to-first-kill)?
- **Q3 (budget efficiency):** kills/minute and cost per incremental kill per
  strategy under the equal budget, vs the W8 non-budget-normalized figures.

## 4. Frozen protocol

- **Corpus:** the promoted W9 corpus (post human non-equivalence review +
  dual-model review; `w9_catalog.json` + `w9_final_freeze.json`), or a
  separately frozen follow-up corpus if W9 promotion is not available.
- **Machine:** the fixed frozen environment at the W9 `code_revision`
  (currently anchored at `0a6c5940`), staged exactly as
  `evaluation/property_assurance/mutation_runner.execute_mutant` stages it
  (fresh-process copy of `services/api/src`, `services/api/tests`,
  `evaluation`; import probe; per-seed pytest subprocess).
- **Equal per-mutant budget B per strategy:** frozen from an outcome-blind
  unmutated calibration (Section 5).
- **Kill-as-soon-as-detected:** seeds run in frozen order
  `[17, 23, 41, 97, 271]`; the strategy stops at the first `KILLED` outcome.
- **Unused budget:** recorded per (mutant, strategy) as
  `unused_budget_ms = max(0, B - used_ms)`; **never transferred** to another
  mutant or strategy.
- **Reported metrics (F-014):** kills per minute, time-to-first-kill (per
  mutant and distribution), incremental unique kills (M0 → M1 → M2 → M3
  ordering), and cost per incremental kill (strategy total wall-clock ÷ its
  incremental unique kills).

## 5. Frozen budget B (outcome-blind unmutated calibration)

Ran `evaluation/property_assurance/budget_calibration.py --run` against the
committed `3263d011` tree (clean worktree; no mutants executed → outcome-blind).
All 16 unmutated invocations passed (returncode 0, no timeouts):

| Method | Executions | Total wall-clock (ms) |
| --- | --- | --- |
| M0_regression | 1 | 36,797 |
| M1_stateless_property | 5 | 31,644 |
| M2_state_machine | 5 | 44,058 |
| M3_combined | 5 | 232,927 |

Frozen rule: `B = ceil(max over methods of unmutated total wall-clock)`, whole
seconds. **B = 233 s** per mutant per strategy
(`research/assurance_soict/budget_calibration.json`, status `completed`).

Note: B is dominated by M3's natural runtime. Under an equal budget, M0, M1,
M2 finish their suite well within B and would carry large *unused* budgets; the
budget-fair comparison therefore measures whether the *extra* wall-clock M3
consumes buys proportionally more detection. This is exactly the intended
question — it is not a critique of W8's raw ranking.

## 6. W8-derived efficiency context (non-budget-normalized, from sealed data)

From the sealed W8 `runtime_stats` + `mutation_scores` (see
`w8_secondary_report/w8_runtime_efficiency.md`; fields exist in the sealed
analysis, no W8 re-run):

| Method | Kills | Total runtime ms | kills/minute | Incremental unique kills (M0→M1→M2→M3) | Cost per incremental kill ms |
| --- | --- | --- | --- | --- | --- |
| M0 | 16/45 | 1,141,775 | 0.84 | 16 | 71,361 |
| M1 | 4/45 | 979,888 | 0.25 | 1 | 979,888 |
| M2 | 6/45 | 2,726,686 | 0.13 | 3 | 908,895 |
| M3 | 20/45 | 8,913,881 | 0.14 | 0 | N/A |

These are **explicitly non-budget-normalized** (GMT-04): W8 strategies ran
unconstrained budgets (M0 = 1 slot, generated methods = 5 slots). They are
included only as the baseline context the budget-fair run will be contrasted
against. The budget-fair run (Section 4) re-measures the same metrics under the
equal budget B.

## 7. Preconditions and artifacts

- `evaluation/property_assurance/budget_calibration.py` — outcome-blind
  calibration (dry-run and `--run`).
- `evaluation/property_assurance/budget_fair_runner.py` — budget-fair M0-M3
  runner; refuses to execute until the human-review gate is complete and B is
  frozen; supports `--validate-only`.
- `research/assurance_soict/budget_calibration.json` — calibration record with
  frozen B = 233 s.
- `research/assurance_soict/budget_fair_design.md` — this document.
- Execution is F-013/F-014 and is **gated**: it runs only after W9 promotion
  (human non-equivalence review complete, W9_PROTOCOL.md section 6) and the
  frozen B exist. No model calls, no router budget.
