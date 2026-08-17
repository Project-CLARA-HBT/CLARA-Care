# GovMut/SOICT final-run analysis plan (frozen aggregation rule)

This document records the aggregation rule that `final_analyze.py` implements
over a validated `final_run.json` (schema `govmut-final-run.v1`) produced by
the frozen SOICT M0--M3 matrix.  The rule is frozen because it determines the
reported headline numbers; changing it after execution would be p-hacking.

## Unit of analysis

The unit of analysis is the **controlled mutant**, not the generated Hypothesis
example and not the state transition (see `statistics_plan.json`,
`unit_of_analysis`).  Every mutation score, robustness score, and stratified
score is computed at mutant granularity.

## Execution grid

- 45 reviewed non-equivalent mutants (dual-model `included`, see
  `model_review_run/dual_model_review.json`), each with 16 execution slots:
  - `M0_regression`: 1 slot (no Hypothesis seed, `hypothesis_seed = null`);
  - `M1_stateless_property`, `M2_state_machine`, `M3_combined`: 5 slots each,
    one per frozen ordered seed `[17, 23, 41, 97, 271]`.
- Total: `45 x 16 = 720` executions.  `final_validate.py` enforces the complete
  Cartesian grid: no duplicate `(mutant, method, seed)` slot and no missing
  slot.  It refuses to accept a run that is not exactly this grid.

## Outcome normalization

Each slot's raw classification is normalized to exactly one canonical outcome:

| Raw classification | Canonical outcome |
| --- | --- |
| `KILLED_TEST_ASSERTION` (or `KILLED`) | `KILLED` |
| `SURVIVED` | `SURVIVED` |
| `INFRASTRUCTURE_ERROR_NOT_KILLED` (or `INFRASTRUCTURE_ERROR`) | `INFRASTRUCTURE_ERROR` |

`INFRASTRUCTURE_ERROR` is **never** counted as killed or survived.  It is a
distinct third outcome handled as an exclusion (see below).

## Frozen aggregation rule

Per mutant x method, over that method's frozen ordered seed slots:

- **primary — `detected_any_seed`**: 1 if at least one *executable* seed slot
  has outcome `KILLED`, else 0.  `None` if the mutant is fully unexecutable for
  the method (every seed slot is `INFRASTRUCTURE_ERROR`).
- **robustness — `detected_all_seeds`**: 1 if every *executable* seed slot has
  outcome `KILLED`, else 0.  `None` when fully unexecutable.
- **`kill_fraction`**: `killed_executable_seeds / executable_seeds` (0..1).
- **`seed_instability`**: `1 - kill_fraction` when `0 < kill_fraction < 1`,
  else 0.  A nonzero value means the mutant is detected on some seeds but not
  all — seed-dependent counterexample generation.
- **`first_killing_seed`**: the first frozen-ordered seed whose slot is
  `KILLED` (or `null` for `M0_regression`, which has no seed).
- **`time_to_first_kill`**: `runtime_ms` of that first killing slot.

### Seeds are NOT independent N

Hypothesis seeds are deterministic PRNG streams: each seed deterministically
derives its example/state-transition sequence.  A mutant that dies on seed A
and survives on seed B is **one mutant with seed-dependent detection**, not two
observations.  Consequently:

- **Mutation score is computed at mutant level only**: `killed / included`
  where `killed` uses `detected_any_seed == 1`, and the denominator is the
  number of executable included mutants.  It is **not** summed or averaged over
  seeds, and seed counts never inflate N for inference.
- Seed-level summaries (`kill_fraction`, `seed_instability`,
  `first_killing_seed`, `time_to_first_kill`) are descriptive, not an
  independent-N sample.

### Mutation score per method

```
mutation_score(method) = #{included mutants : detected_any_seed == 1}
                         / #{included mutants with >= 1 executable seed}
```

### Paired method comparisons

For every unordered pair of methods (M0, M1, M2, M3), on the **same** included
mutants executable in both methods, report the 2x2 table over `detected_any_seed`:

- `both_detected`, `a_only`, `b_only`, `neither`;
- `agreement = (both + neither) / shared_mutants`;
- exact two-sided McNemar p-value over the discordant pair counts (binomial,
  no external statistics dependency).

### Stratification

Mutation score (same mutant-level definition) is additionally reported per
`family_seed`, per `source_path`, and per `anchor`, using the frozen
`mutation_site_candidates.json` fields.

## Infrastructure-error exclusions

`INFRASTRUCTURE_ERROR` slots are excluded from every killed/survived numerator
and denominator and reported separately (`infra_exclusions`).  A mutant whose
slots are entirely `INFRASTRUCTURE_ERROR` for a method is excluded from that
method's mutation-score denominator (`excluded_infra_mutants`) and is never
counted as killed or survived.  This implements `statistics_plan.json`
`unexecutable_rule` at execution level.

## Runtime statistics

Per method: execution count, total/mean/median `runtime_ms`.  Overall: total
executions, total runtime, and the distribution of `time_to_first_kill`.

## Sealing

`final_seal.py` freezes a validated run + its analysis into
`artifact-sha256.json` (inventory), `environment.json` (git source SHA,
Hypothesis version, limits, Python), `README.md`, and `claim_to_evidence.csv`
(claim -> evidence artifact with SHA-256), so every reported number can be
traced to the exact byte-for-byte artifact that produced it.
