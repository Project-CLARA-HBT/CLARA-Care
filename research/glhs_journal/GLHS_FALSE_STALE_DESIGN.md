# GLHS False-Stale Burden & Concurrency Scaling — v2.1 Design

Status: additive design note for the W4 GLHS v2.1 follow-up (policy-epoch schema
migration + false-stale burden + concurrency scaling). It does **not** modify
the frozen v1 protocol (`research/glhs_journal/postgres_toctou_protocol.json`),
the sealed v2 run (`research/glhs_journal/protocol_v2/run_v2_raw.json`), the
frozen v2 protocol (`postgres_toctou_protocol_v2.json`), CareGuard, the remote
VPS process, RIVF/SOICT files, or any production default. All schedules are
executed only by an attested, operator-owned, isolated PostgreSQL run through
the v2.1 protocol (`protocol_v2/postgres_toctou_protocol_v2_1.json`).

## 1. Scope

The v2.1 follow-up covers three deliverables:

1. **W4-T05 persisted policy epoch** — a real `governance_policy_epochs` table
   (GC-006 migration `20260818_0056`) consulted by the real gateway when an
   isolated research attestation is active.
2. **W4-T16 false-stale burden** — measure valid independent writes rejected by
   profile-global versioning (TOCTOU-V2-13).
3. **W4-T15 concurrency scaling** — 1/2/4/8 writers on independent resources
   (TOCTOU-V2-14..17), reporting completion, false-stale rate, latency
   p50/p95, and DB errors. Concurrency 16 remains a documented extension point
   (a future schedule could add it); the frozen v2.1 protocol covers the four
   levels below it.

## 2. False-stale measurement definition

**False stale rejection** = a rejected proposal caused only by an intervening
state transition outside the proposal's declared dependency set (its
`semantic_key`). **True stale rejection** = a rejection caused by an
intervening transition inside the proposal's declared dependency.

The profile-global version counter (`GlhsStateVersion` per profile, checked by
`apply_transition` under the profile row lock) serializes every writer of a
profile. When two writers hold proposals on *different* semantic keys of the
*same* profile, the first commit advances the shared counter and the second is
rejected with `stale_state_version` even though its resource is untouched:
that rejection is false stale. Writes on *different* profiles have independent
counters, so a version advance on one profile rejects nothing on another.

### 2.1 Operationalized contract (TOCTOU-V2-13)

- Seed one profile with two independent proposals (distinct `semantic_key`,
  each bound to its own snapshot at the same base state version).
- Release both writers simultaneously (barrier phase `release`).
- Exactly one commit wins; the loser is rejected as `stale_state_version`.
- The loser's rejection is **false stale**: the winner's transition touched a
  dependency outside the loser's declared set. The winner's commit is the
  "version advance on an unrelated resource".
- Control phase: commit a transition on an unrelated profile, then complete a
  fresh independent write on another profile. A completed write proves
  per-profile isolation (cross-profile false stale = 0); a rejection there
  would be a real defect and aborts the schedule.

Metrics: `attempts`, `accepted_valid_commits`, `true_stale_rejections`,
`false_stale_rejections`, `false_stale_rate_per_attempt`
(= false_stale / attempts), `database_errors`, `latency_p50_ms`,
`latency_p95_ms` (nearest-rank over per-attempt latencies).

## 3. Scaling design (TOCTOU-V2-14..17)

`N` writers (N ∈ {1, 2, 4, 8}) race on N independent resources of one profile
(the N = 1 schedule is the no-race baseline). Expected design-consequence
outcomes:

| Writers | Accepted | False-stale rejections | Expected rate |
| --- | --- | --- | --- |
| 1 | 1 | 0 | 0.000 |
| 2 | 1 | 1 | 0.500 |
| 4 | 1 | 3 | 0.750 |
| 8 | 1 | 7 | 0.875 |

These values are a deterministic consequence of one-winner-per-profile-race,
not estimated population rates (same framing as the earlier
`evaluation/contention_analysis` evidence). The v2.1 protocol freezes each
expected rate; `run_schedules` compares observed vs expected in the
classification audit (`false_stale_matches`) and any mismatch makes the run
**not claim-eligible**.

### 3.1 Operational classification (W4-T14)

Deadlock / could-not-serialize / lock-wait-timeout outcomes are recorded as
`operational_outcome=True, safety_success=False` and are never safety
successes. An unclassified worker error aborts the schedule fail-closed. A
race with no committed winner or more than one winner is an invalid
measurement and aborts.

### 3.2 Audited actor

Following the v2 precedent (TOCTOU-V2-08 audits the losing attempt), the
observation's `rejection_auditability` describes the first false-stale loser
(its proposal/snapshot coordinates and zero transition rows), while the
winner's commit is verified by the one-winner invariant and the committed-item
checks. Governance schedules in the same run (TOCTOU-V2-01..12) keep their v2
observation shape and get a derived single-attempt `metrics` block with
`workload_type="governance_toctou_single_attempt"`; only schedules that staged
an independent-resource race report nonzero false-stale counts.

## 4. Persisted policy epoch (W4-T05 / GC-006)

- Migration `20260818_0056_governance_policy_epochs` adds
  `governance_policy_epochs(id, policy_domain, version, active_from,
  canonical_digest, created_at)` with indexes on `policy_domain`/`version` and
  `UNIQUE (policy_domain, version)`. No PHI.
- `GovernancePolicyEpoch` ORM model mirrors the migration.
- `read_current_policy_epoch(db, policy_domain=None)` returns the active epoch
  (`active_from <= now`, highest `version`, ties → newest row id) or `None`.
- `_effective_policy_version(db)` precedence under the isolated research
  attestation: persisted epoch (when present) → `GOVRED_RESEARCH_POLICY_VERSION`
  env override (sanctioned isolated override) → `POLICY_VERSION` constant.
  **Without attestation no epoch read happens and the default strict path is
  byte-identical to pre-v2.1 behavior.**
- The v2.1 executor writes real `GovernancePolicyEpoch` rows (v2.1 epoch
  factory) so schedules TOCTOU-V2-03/12 exercise the persisted read end to end;
  their `persisted_epoch_version` schedule keys (`policy-v2` / `policy-v3`)
  keep the `(policy_domain, version)` unique constraint satisfiable while the
  frozen v2 protocol (no such keys) falls back to `policy-v2` unchanged.
- The frozen v2 path still uses the `glhs_governance_policy_epochs` row model
  and env override exactly as sealed; the executor selects the epoch model by
  protocol schema version.

## 5. Files

| Path | Role |
| --- | --- |
| `services/api/alembic/versions/20260818_0056_governance_policy_epochs.py` | GC-006 additive migration |
| `services/api/src/clara_api/db/models.py` | `GovernancePolicyEpoch` ORM model |
| `services/api/src/clara_api/glhs/gateway.py` | `read_current_policy_epoch` + `_effective_policy_version(db)` epoch precedence (default path unchanged) |
| `evaluation/glhs_postgres_toctou/executor_v2.py` | v2.1 drivers TOCTOU-V2-13..17, metrics, `validate_v21`, v2.1 `run_schedules` wiring |
| `research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2_1.json` | Frozen v2.1 protocol (v2 schedules + 13..17) |
| `research/glhs_journal/GLHS_FALSE_STALE_DESIGN.md` | This design note |

## 6. Non-goals

No production behavior change (default strict path performs no epoch read), no
remote execution, no edits to the frozen v1/v2 protocols or sealed runs, no
CareGuard/RIVF/SOICT changes, no git commits. Fakes are injected in tests;
the real gateway path is exercised only by attested isolated runs.
