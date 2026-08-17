# Final PostgreSQL TOCTOU Runner Gate

`evaluation/glhs_postgres_toctou/final_frozen_runner.py` validates the frozen
protocol by default. With `--execute` and the explicitly bound PostgreSQL
observer, it creates one random schema, executes the frozen schedule order, and
removes that schema before returning the structural observations.

The current `postgres_toctou_protocol.json` is frozen but not executed.
Development-probe output is not an input or substitute for this final run.

Before an isolated operator can execute a future protocol, the validator
requires all of the following:

- `schema_version` is `glhs-postgres-governance-toctou-final-v1` and `status`
  is exactly `FROZEN_FINAL_REVIEWED`.
- PostgreSQL is operator-owned, uses a random schema per run, and explicitly
  excludes shared/default databases and production resources.
- The frozen statistics plan and schedule manifest are present and SHA-256
  bound from the protocol.
- The five required schedules are present. TOCTOU-02, TOCTOU-03, and TOCTOU-05
  each declare a persisted governance writer.
- The observer contract requires a persisted audit row and exact reconstruction,
  rejects hash-only observations, and classifies missing audit as observer
  incomplete.

Validation reports `VALIDATED_FINAL_PROTOCOL_NOT_EXECUTED`. Execution is only
available with `GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH=1`, an operator-owned
PostgreSQL URL, and `evaluation.glhs_postgres_toctou.postgres_observer:observe`.
The emitted observations are not a safety conclusion; apply the frozen
statistics plan before deriving any result or claim.
