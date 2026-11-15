"""COMPSAC-X04_pg_ssi: real PostgreSQL SERIALIZABLE (SSI) baseline tests.

What is verified
----------------
(a) The EXISTING B2 adapter (`evaluation/venue2027/compsac/baselines.py`, registry arm
    ``postgresql-ssi``, fidelity NOT_RUN_EXTERNAL) is wired honestly: without a
    ``ctx.pg_connection`` it returns ``NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE`` (never a
    simulated result), and a non-PostgreSQL connection object is structurally refused with
    ``EXECUTION_ERROR/PG_CONNECTION_REQUIRED`` (SQLite/mock substitution impossible).
(b) REAL PostgreSQL 16 (never simulated over SQLite, never claimed from localhost): when the
    disposable research cluster from ``infra/research/venue2027/docker-compose.pg.yaml`` is
    reachable — probed fail-closed through ``research/venue2027/_shared/tools/pg_guard.py``
    (the DSN must be the isolated compose shape ``pg_research``/``clara_research``, refused
    otherwise) and then with a psql ping inside ``pg_research_net`` — a genuine SSI
    serialization-failure scenario is executed: the canonical clinical write-skew pair runs
    through the REAL B2 adapter (``run_baseline("postgresql-ssi", case, ctx)`` with a genuine
    psycopg2 connection injected as ``ctx.pg_connection``) by an in-network driver script, and
    the test asserts a REAL PostgreSQL outcome: SQLSTATE 40001 (or 40P01) serialization abort
    on at least one transaction, server-side rollback of the aborted transaction's writes,
    ``SHOW server_version`` reporting 16.x captured verbatim, and a READ COMMITTED contrast
    control proving the abort is caused by SSI. All output is captured verbatim to
    ``research/venue2027/proof/logs/COMPSAC-X04_pg_ssi.pg_evidence.json``.
(c) If the cluster is NOT reachable, every PG test SKIPs with the real probe output as the
    reason (``PG NOT_RUN``) and the proof report states PG was NOT run — never fabricated.

Version: X04 test contract 1.0.0 over COMPSAC_BASELINES_VERSION 1.0.0 / PG_GUARD_VERSION 1.0.0.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.compsac import baselines as bl

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
EVIDENCE_PATH = (
    REPO / "research" / "venue2027" / "proof" / "logs" / "COMPSAC-X04_pg_ssi.pg_evidence.json"
)
DRIVER_PATH = pathlib.Path(__file__).resolve().parent / "x04_pg_ssi_pgdriver.py"

sys.path.insert(0, str(TOOLS))
import pg_guard  # noqa: E402

B2 = bl.B2_POSTGRES_SSI

ISOLATED_DSN = "postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research"
PG_IMAGE = "postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412"


# ---------------------------------------------------------------------------
# (a) Honest wiring of the EXISTING B2 adapter (no cluster needed)
# ---------------------------------------------------------------------------


def test_b2_without_connection_is_not_run_external_never_simulated() -> None:
    outcome = bl.run_baseline(B2, {"case_id": "case-x04"}, None)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    detail_text = outcome.detail
    assert "BASELINE_UNAVAILABLE" in detail_text
    assert "simulated" in detail_text


def test_b2_refuses_non_postgres_connection_before_execution() -> None:
    class FakeSqliteConnection:
        server_version = "3.40.1"

    outcome = bl.run_baseline(
        B2, {"case_id": "case-x04"}, {"pg_connection": FakeSqliteConnection()}
    )
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.detail.startswith("PG_CONNECTION_REQUIRED")
    assert "never simulated" in outcome.detail


def test_b2_registry_entry_declares_real_upstream_and_not_run_external_fidelity() -> None:
    entry = bl.BASELINE_REGISTRY[B2]
    assert entry["fidelity"] == "NOT_RUN_EXTERNAL"
    assert "REL_16_9" in entry["source"]
    assert "ctx.pg_connection" in entry["source"]


# ---------------------------------------------------------------------------
# (b) Fail-closed reachability probe for the isolated research cluster only
# ---------------------------------------------------------------------------


def _pg_reachable() -> tuple[bool, str]:
    """pg_guard first (fail closed), then a psql ping inside pg_research_net."""
    try:
        pg_guard.assert_isolated_database_url(ISOLATED_DSN)
    except pg_guard.PgGuardError as exc:
        return False, f"pg_guard refused DSN: {exc.reason_code}: {exc.message}"
    ver = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
    )
    if ver.returncode != 0:
        return False, (ver.stderr or ver.stdout).strip()[:300]
    try:
        ping = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "pg_research_net",
                PG_IMAGE,
                "psql",
                ISOLATED_DSN,
                "-tAc",
                "SELECT 1",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "psql ping timed out after 120s (docker/network unavailable)"
    if ping.returncode != 0:
        return False, (ping.stderr or ping.stdout).strip()[-300:]
    return True, ping.stdout.strip()


PG_OK, PG_REASON = _pg_reachable()

PG_SKIPIF = pytest.mark.skipif(
    not PG_OK, reason=f"PG NOT_RUN: isolated research PG16 unreachable: {PG_REASON}"
)


def _run_pg_driver() -> dict[str, object]:
    """Execute the in-network driver with the REAL B2 adapter; return its JSON evidence."""
    work = "/work"
    setup = (
        "apt-get update -qq >/dev/null 2>&1"
        " && apt-get install -y -qq python3-minimal python3-psycopg2 >/dev/null 2>&1"
    )
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "pg_research_net",
        "-v",
        f"{REPO}:{work}:ro",
        PG_IMAGE,
        "bash",
        "-c",
        f"{setup} && cd {work} && python3 {DRIVER_PATH.relative_to(REPO)}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    combined = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode != 0:
        pytest.fail(f"in-network B2 driver failed (exit {proc.returncode}):\n{combined[-2000:]}")
    marker = "X04_EVIDENCE_JSON:"
    if marker not in proc.stdout:
        pytest.fail(f"driver produced no evidence marker:\n{combined[-2000:]}")
    payload = proc.stdout.split(marker, 1)[1].strip().splitlines()
    evidence = json.loads("\n".join(payload))
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence  # type: ignore[no-any-return]


@PG_SKIPIF
def test_real_pg16_ssi_serialization_failure_scenario() -> None:
    """REAL PG16: canonical write-skew pair through the REAL B2 adapter.

    Asserts, from the verbatim in-cluster capture: server_version starts with 16; the
    SERIALIZABLE pair run by the B2 adapter produced at least one SQLSTATE 40001/40P01
    serialization abort; the aborted transaction's writes were NOT installed (server-side
    rollback); and a READ COMMITTED contrast committed both transactions (the abort is
    caused by SSI, not by the fixture).
    """
    evidence = _run_pg_driver()
    assert evidence["adapter"] == B2
    assert evidence["adapter_version"] == bl.COMPSAC_BASELINES_VERSION
    assert evidence["driver_executed_in_network"] == "pg_research_net"
    assert evidence["dsn_ok"] is True

    server_version = str(evidence["server_version"])
    assert server_version.startswith("16"), f"expected PG16, saw {server_version!r}"

    ssi = evidence["ssi_pair"]
    ssi_states = [str(s) for s in ssi["sqlstates"]]
    assert any(
        s in ("40001", "40P01") for s in ssi_states
    ), f"expected a real SSI serialization abort, saw {ssi_states!r}"
    assert ssi["outcome"] in ("ADMIT", "REJECT")
    aborted = [tx for tx in ssi["transactions"] if tx["outcome"] == "ABORT"]
    assert aborted, "adapter must record the serialization abort"
    assert all(tx["reason_code"] == "SERIALIZATION_FAILURE" for tx in aborted)
    assert ssi["aborted"] >= 1 and ssi["committed"] >= 1

    # Server-side rollback: the aborted tx's write must NOT be installed.
    assert ssi["aborted_write_installed"] is False
    assert ssi["final_versions"] == ssi["expected_final_versions"]

    # READ COMMITTED contrast control: same interleaving admits both (write skew).
    rc = evidence["read_committed_contrast"]
    assert rc["sqlstates"] == [None, None]
    assert rc["aborted"] == 0 and rc["committed"] == 2


@PG_SKIPIF
def test_real_pg16_b2_outcome_verdict_matches_run() -> None:
    """The B2 adapter's pair-level verdict (ADMIT/REJECT) matches the observed run."""
    evidence = _run_pg_driver()
    ssi = evidence["ssi_pair"]
    expected = "ADMIT" if ssi["committed"] > 0 else "REJECT"
    assert ssi["outcome"] == expected
    assert evidence["server_version"].startswith("16")


@PG_SKIPIF
def test_real_pg16_retry_policy_bounded_envelope_declared() -> None:
    """The bounded retry envelope is declared and surfaced in the evidence (no hidden retry).

    The adapter itself reports aborts as outcomes (retry belongs to the campaign runner);
    the evidence must carry the declared envelope so retry amplification is measurable.
    """
    evidence = _run_pg_driver()
    assert evidence["retry_policy"]["max_attempts"] == 3
    assert evidence["retry_policy"]["idempotent_operation_id"] == "(case_id, tx_id)"
    assert evidence["retry_policy"]["retries_executed_by_adapter"] == 0
