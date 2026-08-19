# GLHS PostgreSQL TOCTOU R3 Freeze

- `freeze_id`: `GLHS-POSTGRES-TOCTOU-R3-20260819-01`
- `run_id`: `GLHS-POSTGRES-TOCTOU-R3-20260819-01`
- `code_sha`: `f1533e74`
- `protocol`: `postgres_toctou_protocol_r3.json`
- `protocol_sha256`: `b44606736ce65c262c9026cdcb57eeab1edbf12c8b72cedc54890936d529e58e`
- `statistics_plan`: `statistics_plan_v2.json`
- `statistics_plan_sha256`: `46a7e270f067769a3c43dc643dd448a2a25bdfffe74597c2d3b399b073af4fa7`
- `logical_schedule_count`: `12`
- `unit_of_analysis`: one frozen logical schedule
- `repetitions_are_new_N`: `false`
- `production_resources`: `false`
- `status`: `FROZEN_PRE_EXECUTION`

This is a new run identity created after the PostgreSQL identifier-length
migration fix. The twelve schedules, expected classifications, statistics plan,
observer contract, and isolation requirements are copied without adaptive
changes from the reviewed v2 protocol. The prior v1/v2 artifacts and the first
R3 execution attempt remain immutable historical records.

Execution is valid only in the isolated PostgreSQL stack with persisted
transaction/audit observations. A mismatch remains a mismatch and is not
reclassified into safety.
