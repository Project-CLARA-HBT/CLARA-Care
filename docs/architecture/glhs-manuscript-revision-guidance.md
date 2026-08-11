# GLHS manuscript revision guidance from verified evidence

This file is author guidance, not manuscript prose and not a result claim. It
must be updated only from the evidence map and sealed artifacts.

## Abstract and conclusion

- Label deterministic suites as developer-authored structural conformance.
- Do not claim universal superiority or clinical safety/efficacy.
- Mention standards-composed, independent-utility, deployment-boundary,
  contention or external-validity results only after their status becomes
  `COMPLETE` with a sealed run.
- Describe the implemented write rule as: a persistent proposal is checked
  against its declared observed base-state version and, when snapshot-bound,
  against its exact governed disclosure context.

## Introduction and related work

- Frame the incremental question as disclosure-to-write context continuity,
  not invention of stale-write prevention.
- Explicitly distinguish established FHIR version-aware update, Provenance,
  Consent and AuditEvent concepts; openEHR versioning/contributions; and
  temporal/state-centric AI systems.
- Call the repository comparator a standards-composed mechanism baseline unless
  a named server/product is actually executed and its deviations are frozen.

## Formal contract

- Give snapshot and proposal distinct profile/subject, actor, role, purpose,
  task, valid-time, knowledge-time, state, policy and consent coordinates.
- Define snapshot-bound and base-version-only admissibility separately.
- State the PostgreSQL atomic compare-and-transition boundary; until the opt-in
  concurrency test runs, qualify this as implementation design plus local
  conformance evidence rather than measured concurrent behavior.
- Call SHA-256 values consistency fingerprints inside the trusted-store threat
  model, not signatures or sender authentication.

## Evaluation and statistics

- Organize evidence as structural conformance, novelty isolation, independent
  utility, PostgreSQL systems/contention, deployed-boundary adversarial,
  prospective model-mediated and external validation.
- Report authored deterministic suites using exact counts and mechanism
  localization; do not emphasize their p-values as external validation.
- Name case-weighted estimates with subject-clustered uncertainty exactly and
  never treat cases/model cells as independent subjects.
- Missing or invalid external/model outputs remain failures under the frozen
  plan. `NOT_RUN` and `BLOCKED_EXTERNAL` must stay visible.
