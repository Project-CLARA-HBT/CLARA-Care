"""Emit and validate the DSN-X04_outbox_reference task proof report.

Builds ``research/venue2027/proof/DSN-X04_outbox_reference.json`` via
``agent_protocol.build_report(task_id='DSN-X04_outbox_reference')`` with real
command log paths, then runs the agent_protocol validator against it
(fail-closed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

BASE_SHA = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"
REPORT_PATH = REPO / "research/venue2027/proof/DSN-X04_outbox_reference.json"


def main() -> int:
    commands = [
        {
            "argv": "python3 -m pytest -q tests/venue2027/dsn/test_outbox_reference.py",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-X04_outbox_reference.pytest.log",
        },
        {
            "argv": (
                "uvx ruff@0.7.1 check evaluation/venue2027/dsn/outbox_reference.py"
                " tests/venue2027/dsn/"
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-X04_outbox_reference.ruff.log",
        },
        {
            "argv": (
                "docker run --rm --network pg_research_net -v <repo>:/work:ro -w /work"
                " python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
                " bash -lc \"pip install -q 'psycopg[binary]==3.2.3' pytest &&"
                " python3 -m pytest -q tests/venue2027/dsn/test_outbox_reference.py -rs\""
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-X04_outbox_reference.pg-pytest.log",
        },
        {
            "argv": "python3 -m evaluation.venue2027.dsn.outbox_reference --json",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-X04_outbox_reference.selfcheck.log",
        },
        {
            "argv": "python3 -m pytest -q evaluation/venue2027/dsn/",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-X04_outbox_reference.suite.log",
        },
    ]

    report = build_report(
        task_id="DSN-X04_outbox_reference",
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=[
            "evaluation/venue2027/dsn/outbox_reference.py",
            "tests/venue2027/dsn/__init__.py",
            "tests/venue2027/dsn/test_outbox_reference.py",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.pytest.log",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.ruff.log",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.pg-pytest.log",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.pg_probe_evidence.json",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.selfcheck.log",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.suite.log",
            "research/venue2027/proof/DSN-X04_outbox_reference.json",
        ],
        commands=commands,
        artifact_paths=[
            "evaluation/venue2027/dsn/outbox_reference.py",
            "tests/venue2027/dsn/test_outbox_reference.py",
            "research/venue2027/proof/logs/DSN-X04_outbox_reference.pg_probe_evidence.json",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 task DSN-X04_outbox_reference (RQ1): faithful transactional-outbox"
            " reference (strong practical baseline B1) for the DSN 2027 study"
            " 'Recoverable Safety Journals for Crash-Consistent AI-Mediated"
            " Health-State Mutations'. evaluation/venue2027/dsn/outbox_reference.py"
            " implements run_outbox(case, tx=None, *, store=None, logical_time=0) ->"
            " Outcome per the manifest signature run_outbox(case: Case, tx:"
            " PGSession)->Outcome. Core algorithm (both backends, identical"
            " semantics): (1) ONE atomic transaction persists the clinical row +"
            " the outbox event + the consumer idempotency key (all three or none);"
            " (2) the consumer is idempotent keyed by the immutable operation ID --"
            " a redelivered event re-acks without re-applying the side effect; (3)"
            " delivery replays under at-least-once semantics until acknowledged,"
            " with every scheduled delivery recorded (CASE_MATRIX DSN-CASE-04)"
            " and the effect applied at most once; (4) the outcome reports"
            " full_retries (deliveries after the first, crash recoveries,"
            " redeliveries) and durable_writes (the atomic triple tx plus each"
            " effect write). Backends declared honestly, never conflated:"
            " backend='in-memory-reference' (default, tx=None) runs a pure"
            " deterministic in-process store (buffered all-or-nothing commit);"
            " backend='postgresql-16.x' runs when tx is a GENUINE PostgreSQL"
            " connection (server_version string per DB-API, or psycopg3"
            " conn.info.server_version numeric, or get_server_version()),"
            " executing real INSERT/UPDATE/SELECT in real transactions on the"
            " research_test schema. Fail-closed: pre_commit crash yields REJECT /"
            " OP_NOT_DURABLE_CRASH_BEFORE_WRITE (retriable, never counted as"
            " success); post_commit_pre_response yields ADMIT /"
            " OP_COMMITTED_ACK_LOST_RECOVERED with one recovery retry (CASE-03"
            " unknown-response reconciliation); delivery budget exhausted yields"
            " INDETERMINATE / DELIVERY_BUDGET_EXHAUSTED_INDETERMINATE (never a"
            " phantom success); a lost outbox row detected during replay yields"
            " INDETERMINATE / OUTBOX_ROW_LOST_DETECTED (tamper/partial state never"
            " coerced to success); a non-PostgreSQL tx (SQLite, mocks) is REFUSED"
            " with PG_CONNECTION_REQUIRED -- never simulated (COMPSAC-B2"
            " discipline). Malformed cases raise OutboxReferenceError with stable"
            " reason codes (CASE_NOT_AN_OBJECT, CASE_MISSING_FIELD,"
            " CASE_UNKNOWN_FIELD, CASE_EMPTY_OPERATION_ID, CRASH_POINT_UNKNOWN,"
            " DELIVERY_SCHEDULE_MALFORMED, CASE_BAD_TYPE); harness Outcome"
            " projection via to_harness() keeps the shared false-zero ban"
            " (NEVER_SUCCESS_OUTCOMES cannot be counted_as_success). REAL"
            " POSTGRESQL RAN: the isolated research cluster"
            " (infra/research/venue2027/docker-compose.pg.yaml, image"
            " postgres@sha256:e62fbf9d3e2b..., healthy container clara-pg-research)"
            " served SHOW server_version = '16.4 (Debian 16.4-1.pgdg120+2)'"
            " (server_version_num 160004); the 4 real-PG test vectors executed"
            " from INSIDE pg_research_net (docker run --network pg_research_net,"
            " python@sha256:5e2bdb1b... + psycopg[binary]==3.2.3) because the"
            " cluster publishes no host port by design (pg_guard isolation"
            " contract); full suite: 32 passed (28 in-memory + 4 real-PG, none"
            " skipped), log research/venue2027/proof/logs/DSN-X04_outbox_reference.pg-pytest.log."
            " Durable evidence verified in the database itself: exactly one"
            " outboxref_effect row per operation (op:pg-clean, op:pg-dup,"
            " op:pg-ack), idempotency flag durable, ack flag durable, pre_commit"
            " crash leaves ZERO rows in all three tables; evidence artifact"
            " research/venue2027/proof/logs/DSN-X04_outbox_reference.pg_probe_evidence.json."
            " Host-level (in-memory) suite: 28 passed, 4 PG vectors skip honestly"
            " with the real reason (cluster unreachable from the host network"
            " namespace) -- a skip never claims a PostgreSQL condition. Outcome"
            " backend label decodes libpq server_version_num 160004 as"
            " 'postgresql-16.0.4' while SHOW server_version reports the Debian"
            " point release 16.4 -- both recorded in the evidence artifact; the"
            " PostgreSQL condition is claimed ONLY from the real container run."
            " Tests test_outbox_reference.py: 32 vectors (positive: atomic row+"
            " outbox commit with shared operation id DSN-CASE-01, idempotent"
            " duplicate delivery, triple broker replay DSN-CASE-04 with all"
            " deliveries recorded and 2 full retries, replay-until-ack after"
            " consumer crash, lost-response recovery dedup DSN-CASE-03, retry/"
            " durable-write reporting, harness projection; adversarial: pre_commit"
            " never a success DSN-CASE-02 with retry-succeeds-exactly-once, budget"
            " exhaustion INDETERMINATE, no duplicate effect across the crash"
            " window, lost outbox row detected, pre_outbox_delivery window"
            " DSN-CASE-07, SQLite/mock tx refused PG_CONNECTION_REQUIRED, 9"
            " malformed-case wiring refusals, determinism, exact case schema;"
            " real-PG: clean commit, pre-commit writes nothing, idempotent"
            " redelivery, post-commit recovery). Regression: full"
            " evaluation/venue2027/dsn/ suite 174 passed; tests/venue2027/ 156"
            " passed; uvx ruff@0.7.1 check clean on both touched files. Backend"
            " used for the in-memory vectors: in-memory-reference (declared in"
            " every outcome); backend used for the PG vectors: genuine PostgreSQL"
            " 16.4 in the isolated compose cluster. source_sha_after records the"
            " base commit 5f97bc36 per sibling convention (DSN-X01..X03, X06);"
            " the single task commit SHA is created immediately after this report"
            " and reported in the handoff. Baseline parity NOT_APPLICABLE for this"
            " file itself (it IS the B1 baseline reference; B0-B3 comparisons"
            " execute in the benchmarking tasks DSN-X05/X07). Dependency"
            " DSN-baselines PASS verified in research/venue2027/STATE/completion.json"
            " before start. Next ready tasks: DSN-X05_workflow_reference,"
            " DSN-X07_kill_driver."
        ),
    )

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = validate_report(
        json.loads(REPORT_PATH.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-X04_outbox_reference",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
