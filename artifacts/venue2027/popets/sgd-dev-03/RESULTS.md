# Cache optimization at matched external dialogue inputs

This complete repeat used each of the 24 orders of the four implementations once. A prior attempt in the optimization worktree stopped with 39 of 96 archived runs. Only the complete repeat supplies the following medians. Run the verifier from the repository root.

```sh
python -m evaluation.venue2027.popets.sgd_cache_comparison verify artifacts/venue2027/popets/sgd-dev-03
```

| Implementation | Median process time, 24 replays |
|---|---:|
| B1 coarse purge | 113.02 ms |
| B2 always recompute | 111.24 ms |
| B4 before optimization | 162.70 ms |
| B4 after optimization | 149.67 ms |

The optimized candidate finished ahead of its predecessor in 19/24 rounds. Coarse purge finished ahead of the optimized candidate in 24/24 and always-recompute in 23/24. These repetitions reuse the same workload. Every observed payload and cancellation matched the original reference for that arm. All four implementations delivered 144,992 authorized bytes per run, with zero forbidden bytes observed under the synthetic revocations. Median latency for the complete sender process includes startup. The parent source, adaptation and [CC BY-SA 4.0 attribution and license](../sgd-dev-01/RESULTS.md) apply to these derived traces. The all-baseline latency claim fails on this development workload.
