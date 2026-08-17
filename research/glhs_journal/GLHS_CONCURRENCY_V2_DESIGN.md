# GLHS Concurrency V2 Design (W4 persisted-governance workstream)

Status: additive design note. It does **not** modify the frozen v1 protocol
(`research/glhs_journal/postgres_toctou_protocol.json`), the running SOICT
process, CareGuard, or any production service. There is **no remote PostgreSQL
execution** and no production behavior change; everything below is
pure-Python/duck-typed and exercised only by focused unit tests with injected
fakes.

## Scope

The v1 development probe (`evaluation/glhs_postgres_toctou/development_probe.py`)
proved GLHS rejection behavior but is development-only, tightly coupled to
SQLAlchemy/`clara_api`, and cannot be reused by a concurrency study. The v2
workstream extracts the durable, database-agnostic pieces into four new modules
under `evaluation/glhs_postgres_toctou/` plus a design note:

| Module | Role |
| --- | --- |
| `schedule_primitives.py` | Shared non-development primitives (monotonic timing, binding digest, ordering classifiers, session/trace protocols). Conceptually extracted from `development_probe`; never imports its private helpers. |
| `barrier.py` | Reusable `PhasedBarrier` (wait/phase), `NullBarrier`, and `CompetingLock` with monotonic timestamps; documents the lock-order specification. |
| `governance_writers.py` | Independent persisted writers as separate session/transaction contracts (consent, role, purpose/authorization, governance policy epoch). Explicit session handle; no global mutation. |
| `observer_v2.py` | Observer with **no dependency on `development_probe`**; per-schedule observation completeness; splits `rejection_auditability` from `committed_reconstructability`; records transaction trace. |
| `validate_v2.py` | Validates v2 observations; refuses draft/non-isolated protocols; requires persisted-writer markers, barrier-controlled interleaving coverage, compound governance drift; classifies deadlock/serialization as operational, not safety success. |

## Lock-order specification

Canonical source: docstring in `evaluation/glhs_postgres_toctou/barrier.py`.
This is the authoritative ordering that every v2 schedule driver must respect so
that barrier-controlled interleaving can never itself deadlock the study.

1. **Coordination order is fixed**: a `PhasedBarrier` rendezvous is always
   entered before any `CompetingLock` acquisition.
2. **A `CompetingLock` is held only for the mutation critical section** and is
   always released before `session.commit()`; it is never held across a
   transaction commit.
3. **A barrier is never waited on while holding a `CompetingLock` or inside a
   transaction that already holds row locks.**
4. **Writer-side ordering**: barrier release → optional competing lock → begin →
   single authoritative governance row mutation → release lock → commit. No
   writer ever holds two governance row locks simultaneously.
5. **Each schedule owns its own `TransactionTrace`**; trace appends are
   single-threaded per schedule and hold no cross-thread lock.

## Governance writer contracts

Each writer takes an explicit duck-typed session (plus optional barrier and
trace handles) and performs one persisted governance mutation followed by a
commit. No function mutates module/global state. Key result contract:

`WriterMetadata`: `writer`, `committed`, `begin_monotonic_ns`,
`commit_monotonic_ns`, `details`, `latency_ms`.

| Writer | Sequence | `details` highlights |
| --- | --- | --- |
| `consent_revoke` | load target → barrier → persist revocation → commit → record metadata | `user_id`, `consent_type`, `consent_version`, `revoked`, `revoked_at` |
| `role_change` | before role → barrier → mutate authoritative role/grant → commit → after role (fresh read) → fresh scope resolution | `before_role`, `after_role`, `fresh_scope_actor_role` |
| `purpose_or_authorization_change` | before purpose → barrier → mutate → commit → after purpose → fresh scope resolution | `before_purpose`, `after_purpose`, `before_status`, `after_status`, `fresh_scope_purpose` |
| `advance_governance_policy_epoch` | load previous epoch → barrier → persist epoch row → commit | `policy_domain`, `version`, `canonical_digest`, `epoch`, `previous_version` |

### Persisted governance policy epoch concept

The v1 probe mutated an in-memory global policy version. v2 replaces that with a
persisted `governance_policy_epochs` row written by
`advance_governance_policy_epoch`:

| Column | Meaning |
| --- | --- |
| `id` | unique epoch id |
| `policy_domain` | e.g. `medications` |
| `version` | policy version string |
| `active_from` | effective timestamp |
| `canonical_digest` | SHA-256 of canonical policy content |
| `created_at` | row creation timestamp |

## Observer v2 contracts

`RawScheduleOutcome` (produced by an injected schedule driver) → `observe`
normalizes and enforces completeness. Required observation fields:
`id`, `run_status`, `schedule_type`, `persisted_writers`, `interleaving`,
`compound_drift`, `outcome`, `rejection_auditability`,
`committed_reconstructability`, `transaction_trace`, `latency_ms`.

Two disjoint auditability contracts:

- **`rejection_auditability`** (a rejected commit): `rejection_decision_event`,
  `reason_code`, `proposal_coordinate`, `snapshot_coordinate`,
  `zero_state_transition_rows`.
- **`committed_reconstructability`** (a committed transition):
  `transition_exists`, `resulting_state_version`, `exact_snapshot_linkage`,
  `reconstruction_succeeds`.

Exactly one of the two is populated per observation; a committed outcome with no
reconstructability, an absent sub-contract, or both present are refusals.

`transaction_trace` records `events` (`begin`/`commit`/`rollback` with
`monotonic_ns`, `backend_pid`, `txid` where the duck-typed session exposes them)
and `lock_waits` (`lock`, `waited_ns`, `acquired`).

## Validation gates (`validate_v2`)

- Refuses draft and non-isolated protocols.
- Requires persisted-writer markers on each schedule.
- Requires barrier-controlled interleaving coverage across the run:
  `mutation_before_commit`, `commit_before_mutation_control`, `competing_lock`,
  `simultaneous_release`, `rollback_retry`.
- Requires compound governance drift (≥ 2 governance dimensions in one
  schedule).
- Classifies deadlock/serialization (`deadlock_detected`,
  `could_not_serialize_access`, `lock_wait_timeout`) as **operational**, never a
  safety success.

## Non-goals

No production code, no remote PostgreSQL, no v1 protocol edits, no git commits.
Fakes are injected in tests; SQLAlchemy/`clara_api` are never imported by the
new modules.
