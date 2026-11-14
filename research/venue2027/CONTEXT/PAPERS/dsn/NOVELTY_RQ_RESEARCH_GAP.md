# Research novelty dossier — Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations

**Target:** 01 DSN 2027
**Research maturity:** research design, not peer-reviewed originality or validated experiment.

## 1. Precisely claimed novel contribution (conditional)

Recoverability is a safety property of the *joint* clinical row, immutable decision lineage, and asynchronous side-effect record, not just of one database commit. Define a recoverable outcome function that returns COMMITTED, REJECTED, or INDETERMINATE until reconcilable ground truth exists.

## 2. Gap against strongest published systems

Transactional outbox and database WAL already give crash-safe writes; the unresolved issue worth testing is whether an AI proposal lineage and user-visible decision stay consistent across crash windows and arbitrary duplicate deliveries. Without a new counterexample to a careful outbox baseline, this is an application paper, not a DSN A contribution.

This is a **testable candidate research gap**, not an established first-in-literature claim. A full systematic related-work audit and prior-art search at final submission are mandatory.

## 3. RQs / estimands / possible falsification

### RQ1
Across crash cut points, are there executions where the clinical state, decision receipt, and outbox state disagree after bounded recovery?
**Unit / primary endpoint:** independent study unit / orphan clinical writes per independent history. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ2
Under at-least-once replay and concurrent consent revocation, does recovery preserve idempotence, causal order, and correct INDETERMINATE labels?
**Unit / primary endpoint:** independent study unit / orphan clinical writes per independent history. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

### RQ3
What is the added durable-write, p99 latency and recovery-time cost compared with transactional outbox and durable workflow baselines?
**Unit / primary endpoint:** independent study unit / orphan clinical writes per independent history. Contrast and minimum effect will be selected prospectively from a pilot, then frozen before confirmatory tests.
**Strong null:** the strongest baseline reaches the same safety/correctness with no statistically meaningful cost difference.

## 4. New system or method under test

A reconciler checks a versioned decision receipt against the committed row, independent outbox receipt and consent epoch. Invalid/ambiguous evidence never becomes a positive outcome; retry decisions are keyed to immutable operation IDs.

## 5. Strong baseline matrix and review of their scope

| Arm | Actually compare | Why this baseline is nontrivial | Reproduction status |
|---|---|---|---|
| B0 | DB transaction only + fire-and-forget side effect | weak control; measures lost side effects | NOT_RUN on new study |
| B1 | PostgreSQL atomic write + transactional outbox + idempotent consumer | strong practical baseline; must implement fully | NOT_RUN on new study |
| B2 | Durable workflow/saga with compensation and stable operation IDs | strong operational baseline; record precise engine/version | NOT_RUN on new study |
| B3 | Proposed reconciliation safety journal | candidate; no pre-existing performance assumed | NOT_RUN on new study |

**Non-equivalence warning:** A named SOTA algorithm, policy engine or clinical benchmark cannot be declared "implemented" merely because a similarly named Python stub exists. Pinned upstream releases, adapters, tests, and fair parameter selection must be documented.

## 6. Verified relevant research and exact comparison burden

| Citable work | Source type | What must be tested rather than assumed | Link |
|---|---|---|---|
| Speedy Transactions in Multicore In-Memory Databases | SOSP 2013 | Serializable optimistic concurrency, scalable in-memory baseline; not a health-specific disclosure mechanism | https://doi.org/10.1145/2517349.2522713 |
| Elle: Inferring Isolation Anomalies from Experimental Observations | OSDI 2020 | Independent black-box transaction-history checker; requires truthful export of histories | https://github.com/jepsen-io/elle |
| Certificate Transparency Version 2.0 | IETF RFC 9162 | Merkle append-only transparency model, integrity != confidentiality | https://www.rfc-editor.org/rfc/rfc9162.html |
| Zanzibar: Google’s Consistent, Global Authorization System | USENIX ATC 2019 | Consistency-aware authorization; tests novelty beyond permission re-evaluation | https://www.usenix.org/conference/atc19/presentation/pang |

This source selection contains A/A* publications, selected journal papers, standards and actual open-source engines, clearly distinguished; a Q1 quartile claim must be verified by subject and year.

## 7. Data, independent oracle, experiments

**Data build:** Generate 48 crash windows x 4 commit/revocation orderings x 3 delivery schedules x 5 independent seeds. Confirm final N only after schedule deduplication; benchmark 1/2/4/8 worker settings.

**Independent oracle:** Jepsen/Elle-compatible history export plus deterministic SQL-state audit; manually review anomaly witnesses.

**Experimental measurements:** orphan clinical writes per independent history; phantom user-visible success; eventual safe reconciliation fraction; duplicate side effects; RTO p50/p95/p99; extra fsyncs per operation.

**Recommended statistics:** fixed split with paired comparisons, case/subject-clustered bootstrap confidence intervals, multiplicity control for secondary claims, and risk-difference bounds for rare invalid events. Power is not inferred from requested sample N; calculate from pilot variance and expected event rates. No posthoc choice of the best baseline.

## 8. Explicit falsification and decision rule

If a correctly engineered PostgreSQL transaction + outbox + idempotent consumer achieves the same invariants and equal/better recovery cost, discard the new mechanism superiority claim.

**Feasibility risk:** Very high novelty bar, deadline nearly immediate. Do not submit a routine outbox implementation as a breakthrough.

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

