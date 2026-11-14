# Research novelty dossier — Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes

**Target:** 05 COMPSAC 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

A machine-checkable *dependency-closure oracle* for schema-defined clinical write operations, coupled with scope-local optimistic versioning that minimizes false-stale rejection without allowing write skew under changing consent and policy.

## 2. Gap against strongest published systems

Silo/OCC and PostgreSQL Serializable Snapshot Isolation already address concurrency; original value must come from automatically deriving semantically required cross-resource dependencies for *AI-generated* clinical writes and quantifying the safety/throughput frontier.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Compared with globally versioned OCC, does a dependency-complete read set reduce unnecessary aborts without increasing forbidden commits?
**Unit / primary endpoint:** independent study unit / forbidden commit rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
How does omitted dependency failure propagate under explicit write-skew and policy-epoch races, and can a separate oracle detect each flaw?
**Unit / primary endpoint:** independent study unit / forbidden commit rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
At what graph fanout and contention does dependency-scope overhead erase throughput gains relative to PostgreSQL SERIALIZABLE?
**Unit / primary endpoint:** independent study unit / forbidden commit rate. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

Freeze per-operation dependency schema and required read/write edges. Validate all required edge versions and consent/policy epochs in one DB transaction with canonical lock ordering. Export histories to Elle/independent serializability checker.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | global-profile version OCC | common coarse implementation | NOT_RUN on new study |
| B1 | Silo-style entity readset OCC with commit-time validation | strong algorithmic comparator; disclose that port is not Silo source code | NOT_RUN on new study |
| B2 | PostgreSQL SERIALIZABLE (SSI) with schema-check predicates | strong DB-native comparator | NOT_RUN on new study |
| B3 | entity-OCC without semantic dependency closure | ablation exposing write skew | NOT_RUN on new study |
| B4 | proposed dependency-complete scope-local OCC | candidate | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Speedy Transactions in Multicore In-Memory Databases | SOSP 2013 | Serializable optimistic concurrency, scalable in-memory baseline; not a health-specific disclosure mechanism | https://doi.org/10.1145/2517349.2522713 |
| Elle: Inferring Isolation Anomalies from Experimental Observations | OSDI 2020 | Independent black-box transaction-history checker; requires truthful export of histories | https://github.com/jepsen-io/elle |
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |
| Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud | NDSS 2014 | Strong caveat-bound HMAC capability; prevents overstating novelty of scoped tokens | https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/ |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Deterministic family of medication/allergy/history/purpose grants; 1, 2, 4, 8, 16 workers; workload partitions with Zipf skew and dependency density; ≥ 5 independent seeds per setting before deciding power.

**Independent oracle:** Independent dependency oracle plus transaction-history consistency checker; record kernel SHA, PG release/version and isolation setting.

**Experimental measurements:** forbidden commit rate; oracle-defined false-stale rate; throughput committed ops/sec; p50/p95/p99 latency; retry amplification; dependency graph completeness.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

Any forbidden commit under a complete, independently labeled dependency schedule falsifies the safety claim; if fully serializable PostgreSQL is as fast, candidly report the null performance benefit.

**Feasibility risk:** A large/sound baseline (PG SSI) is essential; avoid weak baselines only and never reuse R4 SQLite as PG performance.

## 9. Reviewer objections to anticipate

- Strong prior work may already implement the mechanism; require a distinguishing observation from the strongest baseline.
- Benchmark and baseline adaptations may alter threat model or semantics; validate equivalence using official examples and an independent oracle.
- Synthetic-data efficacy may not transfer to clinical settings or adversarial deployments; report domain shift and a negative generalization test.
- Checksums and passing unit tests do not prove the comparative claim or its statistical power.
- Existing GLHS/HEALTHINF/RIVF/SOICT evidence may overlap; independently define contribution, results and publication relationship.

# Cross-study integrity rules

- **Status:** prospective research; source code and publication package are not experimental evidence.
- **Clinical separation:** Synthetic data is not clinical validation; no real patients, live medical actions, or unverifiable provider output.
- **Source of truth:** Git SHA, immutable protocol freeze and raw JSONL must be consistent; checksums do not prove backend truthfulness or design novelty.
- **Real baselines:** Literature references are not executable baselines by themselves. Original external code/adapter must run, or status is NOT_RUN_EXTERNAL (not a weak substitute).
- **Priority:** a strong negative result or equivalence with prior art is more publishable than false superiority.
- **Paper integrity:** Verify corresponding author status, policies on generative AI, author anonymity, copyright and fees before submission. Do not send overlapping contributions to multiple venues at the same time.

