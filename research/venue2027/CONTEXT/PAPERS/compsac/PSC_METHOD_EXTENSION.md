# PSC-Locality: method-specific strongest-case hypothesis and evaluation

**Novelty status: CONDITIONAL; empirical results NOT_RUN.**

**Candidate title:** Dependency-Complete Shadow Certification for High-Concurrency Health Writes

## Claimed mechanism boundary

Derive required schema dependency closure, compare only semantically relevant read sets, separately preserve mandatory governance epochs; issue speculative pass only if shadow histories agree and the PostgreSQL lock/SSI commit rechecks all constraints.

**Twin witnesses:** Never use SQLite to claim PostgreSQL concurrency. Both arms receive identical retries, connection pools, isolation levels and CPU/time budgets.

## Three decisive research questions

**RQ1.** Can schema-derived dependency closure eliminate false-stale aborts without permitting write skew or authorization drift?
**RQ2.** Against PostgreSQL SERIALIZABLE+retry and strong dependency-aware OCC, what is the measurable benefit of paired-shadow certificates?
**RQ3.** At which dependency fanout and hot-key skew do the certificate costs exceed the benefit?

## Prespecified comparison

- **Primary endpoint:** forbidden commits per unique adversarial transaction schedule.
- **Secondary, useful endpoint:** false-stale rate, completed legitimate throughput, p95 latency.
- **Strongest comparator:** PostgreSQL SERIALIZABLE+retry; strong entity-local OCC; classical full read-set OCC; signed exact-disclosure capability with live policy; a faithfully documented Silo-style port.
- **Independent population/unit:** real PG16 1/2/4/8/16 workers, prescribed hot-key Zipf distributions, medication-allergy-consent dependent writes.
- **Required falsifying outcome:** Any forbidden write skew stops release. If PostgreSQL SERIALIZABLE+retry matches legitimate throughput at equivalent correctness, no superiority claim.
- **Hard safety gate:** a single newly discovered forbidden commit, unauthorized egress, incorrect ground-truth oracle, uncontrolled leakage, or hidden failed baseline invalidates the central claim until fixed.

## Non-inferiority / superiority contract

This study has two co-primary goals, both needed for a method-superiority assertion: (a) specified safety loss vs strongest comparator stays inside a *preregistered, clinically/technically defensible* non-inferiority margin with correct confidence bounds, and (b) the named secondary benefit improves by a prespecified minimally important amount on held-out independent units. Neither `p > 0.05` nor zero observed failures alone gives proof. Abstention/coverage remains visible. The methodological target is a meaningful Pareto frontier, **not guaranteed positive numbers**.

## Ablation and negative control requirements

1. Remove historical-view verification but preserve current policy: tests whether exact dispatched evidence contributes.
2. Remove current-state verification while preserving historical binding: tests revocation and delayed commits.
3. Replace selective rescue with conservative full-state revalidation: tests effectiveness vs false-stale.
4. Substitute strong named comparator unchanged; record original source version and mapping fidelity.
5. Remove/tamper certificate and fail-closed; ensure certificate is not treated as hardware attestation.
6. Shift to unseen workload families/sites/principals and higher contention or noise; report all failures.

## Implementation ownership

Each task-specific artifact below extends (not replaces) the path-level plan in `FILE_BY_FILE_IMPLEMENTATION.md`:

- `evaluation/venue2027/05_compsac_2027/shadow_a.py`: historical witness proof and exact request replay; output `witness_a.json` with `source_sha`, trust assumption, and outcome.
- `evaluation/venue2027/05_compsac_2027/shadow_b.py`: current-state counterfactual / policy oracle; output `witness_b.json` with unknown state explicitly encoded.
- `evaluation/venue2027/05_compsac_2027/certificate_gate.py`: consume witness A/B, refuse missing evidence, and pass *advisory* candidate to production atomic transaction (or appropriate venue-specific decision authority).
- `evaluation/venue2027/05_compsac_2027/paired_certify.py`: independent paired test with calibrated margins and seed/split lock; outputs `certification_decision.json` in `CERTIFIED | INCONCLUSIVE | REJECTED`.
- `evaluation/venue2027/05_compsac_2027/ablate.py`: reproduce at least five ablations; never delete failures.
- `tests/venue2027/05_compsac_2027/test_shadow_edges.py`: test valid, stale, revoked, wrong principal, cross-purpose, missing evidence, malformed history, unknown dependency and certificate tampering.
- `research/venue2027/05_compsac_2027/falsification_log.csv`: dated evidence of whether the strongest baseline ties or dominates; preserve negative findings.

**There is no requirement to present PSC as novel across all papers.** PSC is shared infrastructure. Each publication must report *its own distinct independently measured contribution*, or the project must collapse to fewer papers to prevent salami slicing.
