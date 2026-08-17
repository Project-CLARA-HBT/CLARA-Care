# Final PostgreSQL TOCTOU Runner Gate

`evaluation/glhs_postgres_toctou/final_frozen_runner.py` is a validation-only
scaffold for a future final GLHS governance-TOCTOU execution. It does not import
database code, create a database engine, connect to PostgreSQL, or write a
result artifact.

The current `postgres_toctou_protocol.json` is `draft_not_run`; the final
runner must refuse it. Development observations from `development_probe.py` are
not input to, or evidence for, a final run.

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

Successful validation reports only
`VALIDATED_FINAL_PROTOCOL_NOT_EXECUTED`. It is neither a database execution nor
a result, safety conclusion, denominator, or claim-eligible evidence.
