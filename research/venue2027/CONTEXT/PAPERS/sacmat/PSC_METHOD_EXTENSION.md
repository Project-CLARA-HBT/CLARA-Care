# PSC-PolicyTrace: method-specific strongest-case hypothesis and evaluation

**Novelty status: CONDITIONAL; empirical results NOT_RUN.**

**Candidate title:** Twin-Trace Certification for Temporal Purpose-Based Authorization

## Claimed mechanism boundary

Twin A reconstructs authorized event-time policy, Twin B checks action-time precedence; generator searches minimal histories that make identical current states but different legal decisions.

**Twin witnesses:** No false claim that Cedar/OpenFGA natively supports every temporal construct; map unsupported semantics explicitly, or score them as NOT_APPLICABLE.

## Three decisive research questions

**RQ1.** Can a trace-relative oracle distinguish same-state policy histories that produce different authorized actions?
**RQ2.** Does a policy-trace test generator expose bugs missed by state-only XACML/ABAC mutation or MC/DC test suites?
**RQ3.** Does PSC-PolicyTrace reach better temporal boundary coverage at equal query and oracle budget?

## Prespecified comparison

- **Primary endpoint:** detected true temporal authorization faults per independently verified mutant family.
- **Secondary, useful endpoint:** false-positive rate, unique coverage per query, oracle runtime.
- **Strongest comparator:** Cedar policy engine; OpenFGA ReBAC; OPA/Rego; XACML MC/DC mutation tests; pairwise configuration testing.
- **Independent population/unit:** frozen temporal access-control policies across revoke, delegate, purpose, tenant, and legal hold histories.
- **Required falsifying outcome:** If equal-budget MC/DC or property-based mutation testing finds the same mutants, no improved test-effectiveness claim.
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

- `evaluation/venue2027/07_sacmat_2027/shadow_a.py`: historical witness proof and exact request replay; output `witness_a.json` with `source_sha`, trust assumption, and outcome.
- `evaluation/venue2027/07_sacmat_2027/shadow_b.py`: current-state counterfactual / policy oracle; output `witness_b.json` with unknown state explicitly encoded.
- `evaluation/venue2027/07_sacmat_2027/certificate_gate.py`: consume witness A/B, refuse missing evidence, and pass *advisory* candidate to production atomic transaction (or appropriate venue-specific decision authority).
- `evaluation/venue2027/07_sacmat_2027/paired_certify.py`: independent paired test with calibrated margins and seed/split lock; outputs `certification_decision.json` in `CERTIFIED | INCONCLUSIVE | REJECTED`.
- `evaluation/venue2027/07_sacmat_2027/ablate.py`: reproduce at least five ablations; never delete failures.
- `tests/venue2027/07_sacmat_2027/test_shadow_edges.py`: test valid, stale, revoked, wrong principal, cross-purpose, missing evidence, malformed history, unknown dependency and certificate tampering.
- `research/venue2027/07_sacmat_2027/falsification_log.csv`: dated evidence of whether the strongest baseline ties or dominates; preserve negative findings.

**There is no requirement to present PSC as novel across all papers.** PSC is shared infrastructure. Each publication must report *its own distinct independently measured contribution*, or the project must collapse to fewer papers to prevent salami slicing.
