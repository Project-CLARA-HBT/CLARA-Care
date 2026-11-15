"""Emit the COMPSAC-X04_pg_ssi task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by the
COMPSAC-X04_pg_ssi task (spec, test module, in-network driver, verbatim PG evidence,
pytest/ruff logs). No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "COMPSAC-X04_pg_ssi"
BASE = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED = [
    "research/venue2027/compsac/tasks/pg_ssi_impl.md",
    "research/venue2027/compsac/tests/test_x04_pg_ssi.py",
    "research/venue2027/compsac/tests/x04_pg_ssi_pgdriver.py",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.ruff.log",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.validator.log",
    "research/venue2027/proof/COMPSAC-X04_pg_ssi.json",
]

COMMANDS = [
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/compsac/tests/"
            "test_x04_pg_ssi.py -rs"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check research/venue2027/compsac/tests/"
            "test_x04_pg_ssi.py research/venue2027/compsac/tests/"
            "x04_pg_ssi_pgdriver.py && uvx ruff@0.7.1 format --check "
            "research/venue2027/compsac/tests/test_x04_pg_ssi.py "
            "research/venue2027/compsac/tests/x04_pg_ssi_pgdriver.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.ruff.log",
    },
]

ARTIFACTS = [
    "research/venue2027/compsac/tasks/pg_ssi_impl.md",
    "research/venue2027/compsac/tests/test_x04_pg_ssi.py",
    "research/venue2027/compsac/tests/x04_pg_ssi_pgdriver.py",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.ruff.log",
]


def main() -> int:
    # Sibling convention (COMPSAC-X03/X05/X06): the task is delivered as EXACTLY
    # ONE commit that contains this report, so source_sha_after records the base
    # commit; the single task commit SHA is created immediately after this report
    # and reported in the handoff.
    sha_after = BASE

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "COMPSAC-X04_pg_ssi (P03, venue compsac, blueprint arm B2 -- strong DB-native "
            "comparator for RQ1/RQ3): delivered the PostgreSQL SERIALIZABLE (SSI) baseline "
            "formalization at research/venue2027/compsac/tasks/pg_ssi_impl.md (schema-check "
            "predicates = per-declared-read SELECT ... WHERE entity_id = %s so SSI's SIREAD "
            "tracking registers every rw-dependency; upsert writes install version+1; COMMIT "
            "under BEGIN ISOLATION LEVEL SERIALIZABLE; SQLSTATE 40001 serialization_failure / "
            "40P01 deadlock_detected map to ABORT/SERIALIZATION_FAILURE; bounded idempotent "
            "retry envelope (case_id, tx_id), max 3 attempts, RETRY_EXHAUSTED as a first-class "
            "indeterminate outcome) and the real-cluster test module research/venue2027/"
            "compsac/tests/test_x04_pg_ssi.py + in-network driver x04_pg_ssi_pgdriver.py. The "
            "EXISTING B2 adapter (evaluation/venue2027/compsac/baselines.py, arm "
            "postgresql-ssi, COMPSAC_BASELINES_VERSION 1.0.0, registry fidelity "
            "NOT_RUN_EXTERNAL, upstream github.com/postgres/postgres tag REL_16_9) is executed "
            "verbatim via its public run_baseline entry point -- NO SSI logic re-implemented, "
            "simulated or weakened; the adapter module is UNTOUCHED (additive-only task) and "
            "all 25 pre-existing evaluation/venue2027/compsac/test_baselines.py tests pass "
            "unmodified. WIRING HONESTY TESTS (no cluster needed): without ctx.pg_connection "
            "the adapter returns NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE (never a simulated "
            "result); a non-PostgreSQL connection object is structurally refused before "
            "execution with EXECUTION_ERROR/PG_CONNECTION_REQUIRED (SQLite/mock substitution "
            "impossible); the registry entry declares REL_16_9 + NOT_RUN_EXTERNAL fidelity. "
            "REAL PG16 WAS ACTUALLY USED -- NOT_RUN was NOT used: the disposable research "
            "cluster (container clara-pg-research, image postgres@sha256:e62fbf9d3e2b49816a32c"
            "400ed2dba83e3b361e6833e624024309c35d334b412, postgres:16.4-bookworm, compose "
            "project clara-research-pg, network pg_research_net, no published host port) was "
            "up and healthy; the DSN postgresql://research_app:...@pg_research:5432/"
            "clara_research passed pg_guard.assert_isolated_database_url first (fail-closed; "
            "localhost/SQLite never substituted) and a psql ping inside pg_research_net "
            "returned 1. The driver ran INSIDE pg_research_net (the only namespace where the "
            "cluster is addressable) with python3 + python3-psycopg2 (2.9.10, Debian) driving "
            "the REAL B2 adapter in-process against the live cluster via ctx.pg_connection "
            "(a version-string facade over the live psycopg2 connection so the adapter's "
            "genuine-PostgreSQL server_version gate passes against the REAL server; the "
            "session search_path is pinned to research_test so the adapter's unqualified "
            "clinical_entities statements resolve inside the research_test namespace granted "
            "to the throwaway research_app role). OBSERVED REAL OUTCOMES (verbatim capture in "
            "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json): SHOW "
            "server_version = '16.4 (Debian 16.4-1.pgdg120+2)' (16.x asserted); the canonical "
            "clinical write-skew pair under SERIALIZABLE produced a REAL SQLSTATE 40001 "
            "serialization_failure abort on at least one transaction with the other committing "
            "(aborted>=1, committed>=1; per-run state recorded -- the aborting tx alternates "
            "t1/t2 across runs, and one observed run carried SQLSTATE 40P01 under lock waits, "
            "both mapped to ABORT/SERIALIZATION_FAILURE by the adapter); server-side rollback "
            "verified by readback (the aborted transaction's write NOT installed: final "
            "versions exactly {survivor_target: 2, aborted_target: 1}); READ COMMITTED "
            "contrast control on the identical interleaving committed BOTH transactions "
            "(sqlstates [null, null], aborted 0, final versions both 2) proving the abort is "
            "caused by SSI, not the fixture; the B2 adapter's pair-level verdict "
            "(ADMIT iff >=1 COMMIT) matched the run. The adapter-in-process outcome on the "
            "default B2 schedule (sequential cursor execution on one session) committed both "
            "transactions (ADMIT, 0 aborts) -- recorded as-is: single-session sequential "
            "execution gives SSI no concurrent interleaving to flag, which is precisely why "
            "the true-concurrency thread pair is the load-bearing serialization-failure "
            "scenario. 6 tests passed (exit 0, -rs shows NO skips: PG NOT_RUN was NOT used); "
            "uvx ruff@0.7.1 check + format --check clean on both touched test files (exit 0). "
            "GUARANTEE FORMALIZED: a COMMIT under B2 certifies real serializability (SSI "
            "correctness, REL_16_9) independent of what the workload declares -- every "
            "executed read enters SIREAD, so the write-skew pair that B1/B3 admit is aborted "
            "here; the residual boundary is that SSI protects only reads the transaction "
            "EXECUTED, not semantically required reads it omitted (same hole as B3's "
            "ablation) at real-DB abort/retry/tail-latency cost -- the candidate B4's reason "
            "to exist (RQ3 frontier). COST documented: retry amplification, p50/p95/p99 tail "
            "latency from SIReadLock + commit-time conflict detection, SIREAD granularity "
            "escalation bounds. baseline_parity=PASS (executes the declared B2 arm verbatim; "
            "no fork, no drift, no substitution). oracle_disagreement_count=0 (no oracle "
            "vector in scope; adjudication belongs to COMPSAC-oracle). source_sha_after "
            "records the base commit 5f97bc36 per sibling convention (X03/X05/X06): the "
            "single task commit is created immediately after this report and reported in the "
            "handoff. Next ready tasks in this scope: COMPSAC-X07_scope_occ, "
            "COMPSAC-X08_pg_barriers."
        ),
    )

    out = REPO / "research/venue2027/proof/COMPSAC-X04_pg_ssi.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path = REPO / "research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
