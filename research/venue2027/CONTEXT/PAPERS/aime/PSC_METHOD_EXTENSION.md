# PSC-Clinical: method-specific strongest-case hypothesis and evaluation

**Novelty status: CONDITIONAL; empirical results NOT_RUN.**

**Candidate title:** Twin-State Consent Certification for Selective Clinical AI Workflows

## Claimed mechanism boundary

Twin A aligns model-supplied medication/allergy/lab facts with reported recommendation evidence; Twin B tests updated consent and clinical context under independently authored care constraints; uncertain cases defer to physician review.

**Twin witnesses:** No clinical validation when labels are only synthetic rules. Differentiated case-level policy correctness is not the same as diagnosis/treatment accuracy.

## Three decisive research questions

**RQ1.** Can current-vs-disclosed patient context identify a subset of clinical AI recommendations requiring updated history or professional review?
**RQ2.** At fixed inappropriate-action risk, does selective certification preserve more useful recommendations than blanket denial and periodic re-query?
**RQ3.** How do physician-adjudicated safety and case difficulty behave under missing information and shifted care settings?

## Prespecified comparison

- **Primary endpoint:** clinician-adjudicated unsafe-action acceptance per unique vignette.
- **Secondary, useful endpoint:** safe task completion and review workload at fixed upper-risk bound.
- **Strongest comparator:** Clinical safety-rule oracle, always-ask clinician gate, source-verified RAG with fixed budget, GLEAN (ICML 2026) for guideline verification as a different-task comparator, matched LLM baseline.
- **Independent population/unit:** synthetic patient trajectories and, only with rights and approvals, public licensed clinical data; two independent qualified physicians for action-appropriateness ground truth.
- **Required falsifying outcome:** If clinical reviewers find the same unsafe-action acceptance as a strong always-revalidate baseline, or if valid task completion falls below prespecified noninferiority margin, stop efficacy claim.
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

- `evaluation/venue2027/06_aime_2027/shadow_a.py`: historical witness proof and exact request replay; output `witness_a.json` with `source_sha`, trust assumption, and outcome.
- `evaluation/venue2027/06_aime_2027/shadow_b.py`: current-state counterfactual / policy oracle; output `witness_b.json` with unknown state explicitly encoded.
- `evaluation/venue2027/06_aime_2027/certificate_gate.py`: consume witness A/B, refuse missing evidence, and pass *advisory* candidate to production atomic transaction (or appropriate venue-specific decision authority).
- `evaluation/venue2027/06_aime_2027/paired_certify.py`: independent paired test with calibrated margins and seed/split lock; outputs `certification_decision.json` in `CERTIFIED | INCONCLUSIVE | REJECTED`.
- `evaluation/venue2027/06_aime_2027/ablate.py`: reproduce at least five ablations; never delete failures.
- `tests/venue2027/06_aime_2027/test_shadow_edges.py`: test valid, stale, revoked, wrong principal, cross-purpose, missing evidence, malformed history, unknown dependency and certificate tampering.
- `research/venue2027/06_aime_2027/falsification_log.csv`: dated evidence of whether the strongest baseline ties or dominates; preserve negative findings.

**There is no requirement to present PSC as novel across all papers.** PSC is shared infrastructure. Each publication must report *its own distinct independently measured contribution*, or the project must collapse to fewer papers to prevent salami slicing.
