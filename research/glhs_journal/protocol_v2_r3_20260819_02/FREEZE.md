# GLHS PostgreSQL TOCTOU R3 Freeze 02

- `freeze_id`: `GLHS-POSTGRES-TOCTOU-R3-20260819-02`
- `run_id`: `GLHS-POSTGRES-TOCTOU-R3-20260819-02`
- `code_sha`: `ada17aab`
- `protocol`: `postgres_toctou_protocol_r3.json`
- `protocol_sha256`: `21586abf5dcff02ec574cb234649b9e702aa12a62efcff6d7d43bf23f96e4c5e`
- `statistics_plan`: `statistics_plan_v2.json`
- `statistics_plan_sha256`: `46a7e270f067769a3c43dc643dd448a2a25bdfffe74597c2d3b399b073af4fa7`
- `logical_schedule_count`: `12`
- `unit_of_analysis`: one frozen logical schedule
- `repetitions_are_new_N`: `false`
- `production_resources`: `false`
- `status`: `FROZEN_PRE_EXECUTION`

This freeze preserves the reviewed v2 schedule inventory, expected outcomes,
statistics plan, and isolation contract. It differs from R3 freeze 01 only by
the run identity and the executor provenance fix that prevents output from
claiming the historical run ID.

An observed mismatch remains a mismatch and is not reclassified into safety.
