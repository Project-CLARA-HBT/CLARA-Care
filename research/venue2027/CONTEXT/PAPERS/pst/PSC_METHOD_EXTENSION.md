# PSC-Forensic: method-specific strongest-case hypothesis and evaluation

**Novelty status: CONDITIONAL; empirical results NOT_RUN.**

**Candidate title:** Minimal Audit Certificates for Verifiable Privacy-Constrained Forensics

## Claimed mechanism boundary

Twin A generates proof commitments to an authorized history; Twin B verifies a selectively disclosed witness under a policy-specific retention epoch; separate integrity from confidentiality.

**Twin witnesses:** Destroying keys does not prove data deletion from backups. Merkle roots verify append-only integrity, not absence of metadata leaks.

## Three decisive research questions

**RQ1.** What is the least metadata an auditor needs to reconstruct an authorized execution decision?
**RQ2.** At a fixed reconstruction fidelity threshold, do proof-carrying minimal receipts reduce membership and linkage leakage vs detailed logs?
**RQ3.** How do retention, backup persistence and key deletion change privacy and verifiability?

## Prespecified comparison

- **Primary endpoint:** authorized audit reconstruction accuracy at fixed privacy-leakage budget.
- **Secondary, useful endpoint:** log bytes, membership/linkage attacker advantage, p95 proof verification.
- **Strongest comparator:** Full immutable audit log; redacted append-only log; RFC9162-style Merkle transparency with equal redaction; event-only audit baseline.
- **Independent population/unit:** synthetic security event and consent records with fixed attacker auxiliary information and retention schedules.
- **Required falsifying outcome:** If standard selective logging plus Merkle proofs matches privacy and audit utility, novelty is a trade-off measurement only.
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

- `evaluation/venue2027/09_pst_2027/shadow_a.py`: historical witness proof and exact request replay; output `witness_a.json` with `source_sha`, trust assumption, and outcome.
- `evaluation/venue2027/09_pst_2027/shadow_b.py`: current-state counterfactual / policy oracle; output `witness_b.json` with unknown state explicitly encoded.
- `evaluation/venue2027/09_pst_2027/certificate_gate.py`: consume witness A/B, refuse missing evidence, and pass *advisory* candidate to production atomic transaction (or appropriate venue-specific decision authority).
- `evaluation/venue2027/09_pst_2027/paired_certify.py`: independent paired test with calibrated margins and seed/split lock; outputs `certification_decision.json` in `CERTIFIED | INCONCLUSIVE | REJECTED`.
- `evaluation/venue2027/09_pst_2027/ablate.py`: reproduce at least five ablations; never delete failures.
- `tests/venue2027/09_pst_2027/test_shadow_edges.py`: test valid, stale, revoked, wrong principal, cross-purpose, missing evidence, malformed history, unknown dependency and certificate tampering.
- `research/venue2027/09_pst_2027/falsification_log.csv`: dated evidence of whether the strongest baseline ties or dominates; preserve negative findings.

**There is no requirement to present PSC as novel across all papers.** PSC is shared infrastructure. Each publication must report *its own distinct independently measured contribution*, or the project must collapse to fewer papers to prevent salami slicing.
