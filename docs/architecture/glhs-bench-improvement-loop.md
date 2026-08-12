# GLHS-Bench improvement loop

The post-benchmark loop is development-first. The final subject partition is
never used for task-level analysis or engineering decisions.

1. Freeze subject-disjoint task bank, context builders, scoring, model mapping,
   runner and implementation SHA.
2. Run development data, then generate aggregate-only failure taxonomy and
   gap matrices with `evaluation.commitloop.failure_analysis`.
3. Add one registry row linking the observed failure to a general production
   GLHS/THSS change, targeted tests, and development/validation results.
4. Select only on development/validation. Once convergence is documented,
   create a new immutable candidate freeze and execute the untouched final
   partition once.

`failure_analysis` refuses `sealed_test`, writes no provider response or task
content, and is not a scorer. It supports investigation; it cannot alter a
frozen outcome.

The current registry is at
[`protocols/commitloop/improvement_registry.csv`](../../protocols/commitloop/improvement_registry.csv).
The first development-only analysis of the superseded batch-5 router run found
knowledge-time, temporal-selection, model-format, and conflict-collapse
clusters. It exposed a production error in commitment reconstruction: the
bitemporal cutoff used audit ingestion time rather than semantic `known_at`.
`IMP-001` changes that behavior and locks it with a late-arrival regression.
The old run remains exploratory evidence and must not be relabeled as a final
post-improvement result.
