# Prior-cycle failure burden for prioritizing CI tests

**Decision. Retire the suite-burden superiority claim.** On held-out ABB cycles, conditioning a test's failure estimate on the previous cycle's failure fraction yielded 60.94% project-macro recall under the registered deadline. Exponential failure history per predicted cost achieved 62.35%. Removing suite burden and tuning the simpler estimator on the same validation cycles yielded 61.92%. This experiment contributes zero papers toward the portfolio's all-baseline target.

| Selected method | IOF/ROL recall | Paint Control recall | Project-macro recall |
|---|---:|---:|---:|
| Exponential failure history per cost (weight 0.2) | 45.02% | 79.67% | 62.35% |
| Previous verdict only (ablation, strength 2) | 42.05% | 81.79% | 61.92% |
| Previous verdict and suite burden (strength 8) | 41.86% | 80.02% | 60.94% |
| Greedy recent failure-cycle coverage per cost | 45.52% | 75.61% | 60.56% |
| Most recent failure, cost aware | 38.50% | 74.82% | 56.66% |
| Boosted tree per cost | 43.17% | 55.84% | 49.51% |

### Estimand and denominator

ABB IOF/ROL supplied 320 cycles and 27,664 distinct first test attempts from 32,260 rows. Paint Control supplied 352 cycles and 22,260 distinct first attempts from 25,594 rows. A failing test gives one positive label regardless of how many underlying defects caused it. Only ordinary historical verdicts and estimated durations were read. No test was executed. Within each project the chronological splits were 192/64/64 and 211/70/71 cycles, respectively. On the final 64 IOF/ROL cycles, 52 had failures. On the final 71 Paint Control cycles, 54 had failures. All 29 zero-failure cycles remain visible in the per-cycle logs. Recall averages within failure-bearing cycles and then across projects. The budget was 25% of the sum of predicted test durations in that cycle. Scoring charged the source-recorded duration for the contiguous prefix that actually fit. These are offline outcomes assuming that all first-attempt results eventually become visible. An online service executing only selected tests would have different feedback.

The primary comparator and candidate settings were selected in commit `48e5c0ce` using validation alone. Compared with that comparator, the candidate lost 3.16 percentage points on IOF/ROL and gained 0.35 on Paint Control. The previous-verdict ablation beat the candidate on both. These findings trigger both registered retirement conditions. The small pooled advantage over greedy coverage cannot undo either loss. The two related ABB projects do not establish generalization to other organizations. No confidence or clinical inference is claimed. [Registered protocol](PROTOCOL.md) · [Selected settings](results/selection.json) · [All 13 held-out arms](results/test_summary.json) · [Every held-out arm and cycle](results/test_cycles.csv)

### Closest work and scope

Spieker et al. proposed RETECS for failure-directed prioritization from historical CI executions and released ABB test histories. Cheng et al. evaluated recent-failure, time-based and learned rankers in long-running suites, including cost-aware variants. The narrower hypothesis here was that the previous suite's failure burden changes the value of the previous verdict enough to beat strong historical scores under a strict deadline. In this test the added conditioning lost to its simpler ablation. The boosted tree is a local fixed learner. Neither the original RETECS reinforcement-learning agent nor the feature-complete Cheng et al. learning-to-rank system was reproduced. The earliest failing comparison suffices to retire this claim. Published APFDc values and our deadline recall measure different endpoints. [RETECS artifact](https://github.com/mregorova/RETECS/tree/9980ab6035f7a961c56e3b33e202bf2c18d15e6f) · [Cheng et al., ISSTA 2024](https://doi.org/10.1145/3650212.3680307)

### Reproduction

The input mirror SHA and two file fingerprints are pinned in the protocol and runner. ABB published the histories with the RETECS project. The repository includes an MIT notice. Raw rows remain external. Python 3.12, scikit-learn 1.8.0, NumPy 2.4.4 and one numerical thread were used. From this directory run the commands below with the upstream checkout at the pinned revision. The independent Node verifier recomputes per-cycle deadlines and labels from the original files and recalculates project and macro scores. A full replay reproduces the ranking-dependent prefixes.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python replay.py /path/to/RETECS/DATA validation /tmp/ci-replay
python replay.py /path/to/RETECS/DATA test /tmp/ci-replay
diff -ru results /tmp/ci-replay
node verify.mjs /path/to/RETECS/DATA results
```
