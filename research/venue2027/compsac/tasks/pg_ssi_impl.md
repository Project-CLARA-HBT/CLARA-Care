# COMPSAC-X04_pg_ssi — implementation spec: PostgreSQL SERIALIZABLE (SSI) baseline with schema-check predicates + bounded retry

**Task:** `COMPSAC-X04_pg_ssi` · **Phase:** `P03` · **Venue:** `compsac` · **Priority:** `P1`
**Paper:** Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes (**RQ1/RQ3**)
**Contract source:** `research/venue2027/VENUES/compsac/TASKS/COMPSAC-X04_pg_ssi.md`
**Executed adapter (REAL, reused — never forked, never simulated):**
`evaluation/venue2027/compsac/baselines.py`, arm `postgresql-ssi` (blueprint **B2**,
`COMPSAC_BASELINES_VERSION = "1.0.0"`, registry `fidelity: NOT_RUN_EXTERNAL`,
upstream `github.com/postgres/postgres` tag `REL_16_9`, PostgreSQL Licence)
**Isolation tooling (reused):** `research/venue2027/_shared/tools/pg_guard.py`
(`PG_GUARD_VERSION = "1.0.0"`) + `infra/research/venue2027/docker-compose.pg.yaml`
(digest-pinned `postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412`,
network `pg_research_net`, host `pg_research`, db `clara_research`, no published host port)
**Test module:** `research/venue2027/compsac/tests/test_x04_pg_ssi.py`
**Status:** implemented; REAL PG16 outcome captured (see §7 and the proof report notes for the
actual run verdict). This document is the engineering record, not a results claim. No number
herein is a scientific finding; campaign numbers must derive from
`artifacts/venue2027/compsac/<run_id>/manifest.json` after protocol freeze.

---

## 1. Objective

Deliver the strong DB-native comparator (blueprint arm B2) for RQ1/RQ3: **PostgreSQL
SERIALIZABLE Snapshot Isolation (SSI)** — the database's own serializability machinery — applied
to the canonical clinical write schedule. Under SSI (Ports & Grittner, "Serializable Snapshot
Isolation in PostgreSQL", VLDB 2012 / Proc. VLDB Endow. 5(8)), a transaction may commit only if
its snapshot plus read/write dependencies form an acyclic serialization graph; dangerous
structures (rw-antidependency edges tracked via SIREAD predicates and SIReadLocks) trigger
**serialization failures at COMMIT** rather than allowing anomaly admission. The comparator's
scientific role is the strongest "just use the database" alternative to the candidate (B4,
dependency-complete scope-local OCC): if fully serializable PostgreSQL matches the candidate's
throughput at equal safety, the paper must candidly report the null benefit (falsification rule,
task §8).

The task-manifest contract is `execute_serializable(op, session) -> Outcome`; the verified
existing implementation of that contract is the B2 arm of
`evaluation/venue2027/compsac/baselines.py::run_baseline("postgresql-ssi", case, ctx)` with
`ctx.pg_connection` carrying a genuine DB-API PostgreSQL connection (task instruction: use the
EXISTING B2 adapter; a second implementation would violate baseline-parity rule 8 — never replace
or duplicate a declared baseline). The X04 deliverable is therefore (a) this formalization and
(b) the real-cluster test module; the adapter itself is NOT re-implemented.

## 2. Formal model

Fix a clinical write schedule `W = (E, τ, T)`: entity set `E` (e.g. `medication_order`,
`allergy_list`), version map `τ`, transactions `T = (t_1, …, t_n)` with declared reads `R_i`,
declared writes `W_i`, observed versions `v_i` and write values `u_i`.

**Schema-check predicates (the B2 mapping into SQL).** Each `t_i` executes in its own
`BEGIN ISOLATION LEVEL SERIALIZABLE` transaction over table `clinical_entities(entity_id PK,
version, value)`:

1. **Predicate re-read** — for every `e ∈ R_i`:
   `SELECT version FROM clinical_entities WHERE entity_id = e`.
   This makes each declared read a *predicate read* so SSI's SIREAD tracking registers the
   rw-dependency even though the lookup is by key. The adapter (`baselines.py::_run_tx`) issues
   exactly these statements before any write.
2. **Upsert write** — for every `(e, u) ∈ W_i`:
   `INSERT INTO clinical_entities (entity_id, version, value) VALUES (e, 1, u)
   ON CONFLICT (entity_id) DO UPDATE SET version = clinical_entities.version + 1, value = u`.
3. **COMMIT** — PostgreSQL's SSI engine alone decides: on commit, if the transaction's
   rw-antidependencies form a dangerous structure (two consecutive rw edges in the serialization
   graph), the backend raises `SQLSTATE 40001` (`serialization_failure`); conflicting lock waits
   that collapse into a cycle may instead surface `SQLSTATE 40P01` (`deadlock_detected`). Both are
   ABORT outcomes of the arm's protocol; any other database error is a first-class failure, never
   counted as a safe rejection.

**State transition relation (per transaction).**

- `succeeded(t_i)` := COMMIT returned ⇒ `t_i` is serialized with all previously committed
  transactions (SSI guarantee), its writes visible at `version + 1`.
- `aborted(t_i)` := `40001 | 40P01` raised ⇒ **no write of `t_i` is installed** (PostgreSQL
  transaction atomicity — the aborted transaction's upserts are rolled back by the server, not by
  the adapter).
- `error(t_i)` := any other exception ⇒ propagates as an execution failure (fail closed).

**Retry policy (bounded, idempotent).** SSI is optimistic: a `40001` abort is an instruction to
retry, not a safety verdict. The bounded retry envelope for campaign use (and asserted once by the
test module at the protocol level) is:

- logical operation id `oid = (case_id, tx_id)` — fixed across attempts, so a retried transaction
  re-executes the same predicate reads/upserts and cannot double-install (the upsert is
  naturally idempotent per attempt because each attempt runs in a fresh SERIALIZABLE transaction
  that re-reads the CURRENT version before writing);
- `attempt(a)`: run §2.1–2.3; on `40001`/`40P01` with `a < A_MAX` (campaign default `A_MAX = 3`)
  re-run with fresh snapshot; on `a = A_MAX` record `RETRY_EXHAUSTED` as a first-class
  indeterminate/abort outcome (never a success);
- no backoff randomness in the deterministic pilot: fixed tiny stagger, documented per run.

**Guarantee (what a COMMIT certifies).** A committed `t_i` is *serializable* with every other
committed transaction of the cluster: there exists a serial order of all committed transactions
consistent with all their read/write dependencies (PostgreSQL SSI correctness, REL_16_9). Unlike
B1/B3's declared-read-set fence, the guarantee does NOT depend on what the workload declares:
even an *omitted* semantic dependency (the canonical write-skew window of B1/B3) is protected
**when the transaction actually reads the conflicting entity** — because the predicate re-read
puts every executed read into SIREAD, and SSI detects the rw-antidependency at commit. The
boundary (mechanism axis, RQ2): SSI protects what the transaction *executed*, not what the
operation *semantically required* — a transaction that never issues the required read (the
omitted dependency) exposes the same write-skew hole as B3's ablation; SSI cannot derive missing
reads. That residual gap, at real-DB abort cost, is the candidate's (B4) reason to exist.

**Cost.** SSI trades safety for (i) **retry amplification** — under contention, aborted
transactions re-execute (measured as `attempts / committed`, campaign metric); (ii) **tail
latency** — SIReadLock acquisition and commit-time conflict detection sit on the critical path
(p50/p95/p99, RQ3); (iii) **lock memory** — `max_pred_locks_per_transaction` bounds SIREAD
granularity escalation (page → relation), a degradations surface the candidate avoids by
validating a derived edge set instead. RQ3 asks exactly when this cost erases the candidate's
overhead.

**States and codes.** `COMMIT/OK`, `ABORT/SERIALIZATION_FAILURE` (SQLSTATE 40001 or 40P01,
mapped by the adapter), `EXECUTION_ERROR` (any other DB error, non-PostgreSQL connection refused
via `PostgresConnectionRequired`/`PG_CONNECTION_REQUIRED`, malformed schedule
`SCHEDULE_MALFORMED`), and — when no genuine PostgreSQL connection is injected —
`NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE`. A NOT_RUN_EXTERNAL is a transparent, mutually exclusive
outcome (INDEPENDENT_EVIDENCE_PROTOCOL rule 4); it never counts as a rejection, a success, or a
skipped safety check.

## 3. Faithful-execution mapping (PostgreSQL REL_16_9 semantics → B2 adapter → this task)

| PostgreSQL SSI (REL_16_9) | B2 adapter (`baselines.py::_PostgresSsiExecutor`) | X04 deliverable |
|---|---|---|
| `BEGIN ISOLATION LEVEL SERIALIZABLE` | `_run_tx` first statement | test module requests the adapter via `run_baseline("postgresql-ssi", …)` |
| predicate read → SIREAD/SIReadLock | `SELECT version … WHERE entity_id = %s` per declared read | scenario fixtures declare reads the OTHER tx writes (write-skew pair) |
| row upsert with version bump | `INSERT … ON CONFLICT DO UPDATE SET version = version + 1` | same, via `write_values` |
| commit-time dangerous-structure detection → 40001 | `except` maps `40001`/`40P01` → `ABORT/SERIALIZATION_FAILURE` | test asserts a REAL 40001 was observed on the isolated cluster |
| genuine-PostgreSQL gate (never simulate) | `server_version` must start `12.–17.` else `PostgresConnectionRequired` | test injects only a real `psycopg2` connection inside `pg_research_net` |

No SSI logic is re-implemented or weakened here; the adapter is executed verbatim. The test
module adds only the fail-closed reachability probe (pg_guard + docker) and the assertion layer.

## 4. Positive and adversarial vectors (defined before running)

Positive: **X04-P1** — on the isolated PG16 cluster, the canonical write-skew pair under
SERIALIZABLE yields **at least one real `40001` serialization_failure abort** and the aborted
transaction's writes are NOT installed (server-side rollback verified by version readback).
**X04-P2** — `SHOW server_version` on the injected connection reports a 16.x server (pinned
16.4), captured verbatim into the evidence artifact. **X04-P3** — the B2 adapter's real outcome
verdict on the default schedule matches the run (ADMIT iff ≥ 1 COMMIT).

Adversarial: **X04-A1** — no connection injected ⇒ adapter returns
`NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE` (never a simulated result). **X04-A2** — non-PostgreSQL
connection (e.g. a stub whose `server_version` says "3.40.1") ⇒ `EXECUTION_ERROR/
PG_CONNECTION_REQUIRED` (SQLite/mock substitution is structurally refused before execution).
**X04-A3** — if the isolated cluster is unreachable, the PG tests SKIP with the real probe output
as the skip reason and the proof states PG was NOT run (transparent skip; no SQLite fallback
ever). **X04-A4** — a read-write READ COMMITTED contrast control (same interleaving) is recorded
in the evidence artifact so the SERIALIZABLE differential is machine-checkable, not narrative.

## 5. Test and evidence contract

`research/venue2027/compsac/tests/test_x04_pg_ssi.py`:

- probes the disposable research cluster through `pg_guard.assert_isolated_database_url` first
  (fail closed: any non-`pg_research`/`clara_research` DSN is refused), then `docker run` psql
  ping inside `pg_research_net` (the cluster publishes no host port by design);
- when reachable: executes the REAL B2 adapter (`evaluation.venue2027.compsac.baselines.
  run_baseline("postgresql-ssi", case, ctx)` with a genuine `psycopg2` connection injected as
  `ctx.pg_connection`) via a driver run inside `pg_research_net` (the only namespace where the
  cluster is addressable), asserting a real `40001`/`40P01` PG outcome, server-side rollback, and
  `SHOW server_version` 16.x — all captured verbatim to
  `research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json`;
- when unreachable: every PG test SKIPs with the real probe output as the reason, and the proof
  report MUST state PG was NOT run (never fabricated).

The adapter module `evaluation/venue2027/compsac/baselines.py` is untouched (additive-only task);
`evaluation/venue2027/compsac/test_baselines.py` must stay green. Artifacts: this spec + test
module + evidence JSON + pytest/ruff/validator logs + proof report
`research/venue2027/proof/COMPSAC-X04_pg_ssi.json` (emitted via `agent_protocol.build_report`,
validated `ok: true`). The task manifest's `artifacts/venue2027/compsac/<run_id>/pg_ssi.json`
belongs to the campaign runner (`COMPSAC-runner`), not to this per-task commit.

## 6. What was changed

| File | Change | Backwards compatibility |
|---|---|---|
| `research/venue2027/compsac/tasks/pg_ssi_impl.md` | NEW: this spec | — |
| `research/venue2027/compsac/tests/test_x04_pg_ssi.py` | NEW: real-cluster SSI serialization-failure test + fail-closed skip | No shared fixture mutated |
| `research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json` | NEW: verbatim PG16 outcome capture | — |
| `research/venue2027/proof/COMPSAC-X04_pg_ssi.json` + logs | NEW: proof report via `agent_protocol.build_report` | — |

No production path, secret or patient data touched; the throwaway research role
(`research_app`, NOSUPERUSER) on the disposable compose cluster only; no hidden
clock/randomness/network beyond the declared docker probe.

## 7. Real-cluster run record (fill at execution)

- Cluster: container `clara-pg-research`, image digest
  `sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412` (postgres:16.4-bookworm).
- Reachability: pg_guard OK + `docker run --network pg_research_net … psql -tAc "SELECT 1"` → `1`.
- Driver executed inside `pg_research_net` with `psycopg2` (2.9.10, Debian) driving the B2
  adapter in-process against `postgresql://research_app:…@pg_research:5432/clara_research`.
- Observed (see evidence JSON for the verbatim capture of THIS task's run): SERIALIZABLE pair →
  ≥1 `40001` abort, remaining commit verified; `SHOW server_version` → `16.4 (Debian
  16.4-1.pgdg120+2)`; READ COMMITTED contrast → both commit (write skew admitted), demonstrating
  the differential is caused by SSI, not by the fixture.
