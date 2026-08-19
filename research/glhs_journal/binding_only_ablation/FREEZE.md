# GLHS exact-binding matched ablation — FREEZE

**Freeze id:** `GLHS-BINDING-ABLATION-20260819-01`
**Protocol:** `evaluation/glhs_binding_only_ablation/protocol.json`
**Schedules:** `evaluation/glhs_binding_only_ablation/schedules.json`

## 1. What is frozen

- **320 logical schedules** (GLHS-A05): 8 binding-specific families x 32
  adversarial schedules = 256 adversarial plus 64 valid controls (8 per
  family). The scientific unit is the logical schedule.
- **Two matched arms** (GLHS-A01):
  - `FULL_GOVERNANCE_NO_EXACT_BINDING`: state, current authorization, policy,
    consent, actor, role, purpose, task, DB locking, idempotency, ordinary
    provenance and audit preserved; only the persisted exact THSS
    identity/digest/evidence dependency omitted. Implemented by calling the
    production current-coordinate primitive and skipping the exact primitive
    (C-001/C-002/C-005).
  - `GLHS_EXACT_BINDING`: identical plus exact THSS ID/digest/manifest/
    evidence-membership/expiry via the production exact-disclosure primitive
    (C-002/C-005).
- **Primary schedule families** (spec 3.3):
  1. wrong snapshot ID but same profile/current versions
  2. wrong snapshot digest
  3. mutated snapshot payload with unchanged current state/governance
  4. evidence used by proposal but absent from disclosed set
  5. substitute another valid snapshot from same profile/state version
  6. expired original snapshot while state/policy/consent unchanged
  7. minimized evidence-set swap
  8. lineage-root/snapshot substitution after human review
- **Every adversarial schedule holds current state/governance valid while
  changing only the disclosure dependency** (C-007, GLHS-A03).
- **Controls** preserve all fields and are expected to commit under both arms
  (GLHS-A04).
- **Analysis plan** (GLHS-A06): paired invalid-commit acceptance on the 256
  adversarial schedules; numerator/denominator per arm; paired absolute risk
  difference + 95% paired bootstrap CI with deterministic seed
  (`20260819`, 10 000 resamples); discordant counts; exact two-sided McNemar
  test; per-family results; controls valid-commit acceptance + rejection
  reason distribution. **No adaptive sample-size increase after result
  inspection.**

## 2. Frozen before execution (C-008)

The protocol (including the full analysis plan and the bootstrap seed) and the
320-schedule inventory were written and validated before any execution:
`evaluation/glhs_binding_only_ablation/protocol.json` and
`schedules.json` are committed with the freeze. `validate.py` re-verifies the
inventory and the protocol invariants (`make`/`pytest` runs
`evaluation/glhs_binding_only_ablation/tests/`).

Frozen hashes:

- `protocol.json` `protocol_hash`: `60c9babee3b70697584610c6a9ff42526666414b7755f3329c9cee58e22ad95a`
- `protocol.json` `analysis_plan_hash`: `1873f9aa346e6b6beb45fa8fbf098fe5fd4829691676aa5abaa3c7df69760e0d`
- `schedules.json` SHA-256: `81947281132e03c7728a48f790dc69be9f85f5159b309fe844fdd0125aaaaf54`

## 3. Gate C (arm-diff)

`validate.py::validate_arm_diff` proves, for every logical schedule, that the
two arm executions are byte-identical on all non-binding governance
coordinates (state version, policy, consent, purpose, task, actor role,
allowed actions, evidence fingerprints). The only permitted differences are
the admission outcome and the rejection reason, driven by
`binding_check_applied` (True only under `GLHS_EXACT_BINDING`). The raw
`execution_utc`, `sequence`, `txid`, and `backend_pid` fields are observation
metadata and are excluded from the diff by construction (they are not
governance inputs).

`validate.py::validate_no_production_flag` scans `services/**` for
`disable_binding` / `no_exact_binding`; it must return nothing (GLHS-A02).
`validate.py::validate_import_boundary` scans `services/**` for references to
`glhs_binding_only_ablation`; it must return nothing (GR-03, C-004).

## 4. Execution status — HONEST

- **PostgreSQL final run:** `GLHS-BA-POSTGRES-20260819-05` completed all 640
  executions through the real production commitment admission path in an
  isolated random schema on PostgreSQL 16.14. The schema was dropped after the
  run; `track_commit_timestamp` was `off`, so no commit-timestamp claim is
  made.
- **SQLite smoke:** no SQLite stream is retained as evidence. PostgreSQL is the
  final backend for this freeze.
- The seal in `seal/` reflects exactly the retained PostgreSQL execution; no
  PostgreSQL result is fabricated.

## 5. Claims

Claims and their artifact mapping are in `claim_to_evidence.csv`. Final
PostgreSQL claims are marked `CLAIM_ELIGIBLE` only after the raw stream,
analysis, and seal pass validation.
