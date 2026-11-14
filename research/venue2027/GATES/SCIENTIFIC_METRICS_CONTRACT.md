# Statistical, efficiency and result-integrity protocol

## Safety and operational utility must be tested together

1. Before experiments identify *specific safety events* forbidden under the threat model. The independent oracle, not the candidate, decides if any event is forbidden.
2. For every independent unit test both the strongest baseline and candidate on **the same** schedule, source case and computational budget where scientifically meaningful. Include clean valid controls and indeterminate cases.
3. A zero-event outcome has a finite confidence bound. For iid independent Bernoulli units, one-sided Clopper–Pearson upper bound after 0/N errors at alpha=0.05 is `1 - 0.05**(1/N)`; N=598 gives ≈0.0050. Dependency and cluster correction must be justified where units share a patient/schedule source.
4. Safety noninferiority is not demonstrated by `p > 0.05`, by zero observed errors or by high abstention. Freeze margin, power and inferential method before holdout.
5. Operational improvements are separate hypotheses: lower false-stale, higher authorized completion, less redisclosure, better forensic query coverage, lower p95/p99, or fewer false alarms. Prefer Pareto frontiers at matched safety constraints rather than accuracy alone.
6. Report `eligible`, `attempted`, `completed`, `rejected`, `indeterminate`, `timeout`, `not_run_external`, and `missing`; never silently shrink denominator.
7. Include baseline source parity, paired CIs clustered at independent unit, calibration, ablations, group holdouts and independent repeated seeds.
8. If strong baseline matches/dominates candidate, narrow the mechanism claim rather than cherry-pick workloads. Keep the negative result in release artifacts.
9. Precompute pilot sample size with variance or conservative upper bound; prospective sample size is not chosen from target p-values.
10. Report computation budget and hardware. In systems studies compare fixed workload and fixed throughput, record warmup/DB queue effects, bounded retries and external I/O.

## Reviewer's strongest objections to anticipate

- Was oracle built independently, and does it verify *actual* persisted DB state / actual outbound dispatch rather than proposed code path?
- Did baseline implement strong consistency, online revocation check and same safety properties, or merely an illustrative toy?
- Were all runs included, including failures, rate limits and incompatible external systems?
- Is there an independent case-family holdout; is evaluation conditioned on success?
- Were RQ effects separated from shared GLHS journal and previous workshop/conference studies?
- Does the proof assume independence or full evidence completeness that real deployment lacks?
