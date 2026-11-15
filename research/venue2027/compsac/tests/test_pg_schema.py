"""COMPSAC-X03_pg_schema: isolated benchmark partition/version schema tests.

What is verified
----------------
(a) The DDL file ``infra/research/venue2027/schema/compsac_benchmark.sql``
    parses/normalizes: statements split cleanly, balanced quoting, and a
    structural check that every statement is scoped to the ``research_schema``
    namespace (never ``public`` or any production table).
(b) The schema targets a research namespace and contains the required tables
    (entities, entity_version_partitions, governance_epochs, consent_epochs,
    op_log) and the version-lookup indexes.
(c) REAL PostgreSQL 16 (optional, never simulated): when the disposable
    research cluster from ``infra/research/venue2027/docker-compose.pg.yaml``
    is reachable via the compose-network DSN checked by
    ``research/venue2027/_shared/tools/pg_guard.py``, the schema is applied
    with psql inside ``pg_research_net`` and the tables/indexes are asserted
    to exist (and the rollback helper works). Output is captured verbatim.

If the cluster is unreachable, the PG integration tests are marked
``PG NOT_RUN`` explicitly (pytest.skip with the real failure output) — a
SQLite or localhost database is NEVER substituted, per the task contract.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
SQL_PATH = REPO / "infra" / "research" / "venue2027" / "schema" / "compsac_benchmark.sql"
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"

sys.path.insert(0, str(TOOLS))
import pg_guard  # noqa: E402

SCHEMA_VERSION = "1.0.0"

REQUIRED_TABLES = (
    "research_schema.entities",
    "research_schema.entity_version_partitions",
    "research_schema.governance_epochs",
    "research_schema.consent_epochs",
    "research_schema.op_log",
)

REQUIRED_INDEXES = (
    "entities_tenant_version_idx",
    "entity_version_partitions_history_idx",
    "governance_epochs_tenant_idx",
    "consent_epochs_subject_idx",
    "op_log_tenant_status_idx",
    "op_log_entity_idx",
    "op_dependency_edges_entity_idx",
)

REQUIRED_SCHEMA = "research_schema"

ISOLATED_DSN = "postgresql://research_app:research-only-throwaway@pg_research:5432/clara_research"
PG_IMAGE = "postgres@sha256:e62fbf9d3e2b49816a32c400ed2dba83e3b361e6833e624024309c35d334b412"


def _load_sql() -> str:
    assert SQL_PATH.is_file(), f"missing schema file: {SQL_PATH}"
    return SQL_PATH.read_text(encoding="utf-8")


def _split_statements(sql: str) -> list[str]:
    """Structural normalize/split: strip comments, split on ';' at depth 0.

    Fails closed on unbalanced single/double quotes or dollar-quoting, so a
    truncated or corrupted DDL file cannot pass as "parsed".
    """
    statements: list[str] = []
    buf: list[str] = []
    in_line_comment = False
    in_block_comment = 0
    in_single = in_double = False
    dollar_tag: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buf.append(ch)
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = 0
                i += 2
                continue
            i += 1
            continue
        if dollar_tag is not None:
            end = sql.find(dollar_tag, i)
            if end == -1:
                raise ValueError("unterminated dollar-quoted string")
            buf.append(sql[i : end + len(dollar_tag)])
            i = end + len(dollar_tag)
            dollar_tag = None
            continue
        if not in_single and not in_double and ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue
        if not in_single and not in_double and ch == "/" and nxt == "*":
            in_block_comment = 1
            i += 2
            continue
        if not in_double and ch == "'" and not in_single:
            in_single = True
        elif in_single and ch == "'":
            if nxt == "'":  # escaped quote
                buf.append(sql[i : i + 2])
                i += 2
                continue
            in_single = False
        elif not in_single and ch == '"' and not in_double:
            in_double = True
        elif in_double and ch == '"':
            in_double = False
        elif not in_single and not in_double and ch == "$":
            tag = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if tag:
                dollar_tag = tag.group(0)
        if ch == ";" and not in_single and not in_double and dollar_tag is None:
            statements.append("".join(buf).strip().rstrip(";").strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if in_single or in_double or in_block_comment or dollar_tag is not None:
        raise ValueError("unbalanced quotes/comments in DDL")
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if s]


# ------------------------------------------------------------------ (a) parse
def test_sql_file_exists_and_parses_into_statements() -> None:
    sql = _load_sql()
    stmts = _split_statements(sql)
    assert len(stmts) >= 15, f"expected a real DDL body, got {len(stmts)} statements"
    assert any(s.upper().startswith("CREATE SCHEMA") for s in stmts)


def _statement_target(s: str) -> str | None:
    """Return the qualified object name a DDL statement targets, or None."""
    m = re.match(
        r"(?:CREATE TABLE|ALTER TABLE|DROP TABLE)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?" r"([\w.]+)",
        s,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.match(
        r"(?:CREATE|DROP)\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
        r"([\w.]+)?\s*(?:ON\s+)?([\w.]*)",
        s,
        re.I,
    )
    if m:
        return m.group(2) or m.group(1)
    m = re.match(r"COMMENT ON\s+(\w+)\s+([\w.]+)", s, re.I)
    if m:
        return m.group(2)
    return None


def test_every_statement_targets_research_schema() -> None:
    sql = _load_sql()
    stmts = _split_statements(sql)
    unqualified = []
    for s in stmts:
        target = _statement_target(s)
        if target is None:
            continue
        if not target.startswith(REQUIRED_SCHEMA + ".") and target != REQUIRED_SCHEMA:
            unqualified.append(target)
    assert not unqualified, f"statements outside research_schema: {unqualified}"
    # Hard fail-closed: the DDL must never reference the public namespace.
    assert not re.search(r"\bpublic\.", sql), "DDL must not touch the public schema"
    # And must never appear in any Alembic production migration path.
    assert "alembic" not in sql.lower()


def test_schema_declares_version_and_purpose_docstring() -> None:
    sql = _load_sql()
    assert "COMPSAC_X03_SCHEMA_VERSION" in sql
    assert "1.0.0" in sql
    assert SCHEMA_VERSION == "1.0.0"


# ------------------------------------------------- (b) namespace and contents
def test_required_tables_and_indexes_present() -> None:
    sql = _load_sql()
    for table in REQUIRED_TABLES:
        assert re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(table)}\b", sql), table
    for idx in REQUIRED_INDEXES:
        assert re.search(rf"CREATE INDEX IF NOT EXISTS {re.escape(idx)}\b", sql), idx
    # Version-lookup index on the entities hot path must cover version.
    assert re.search(
        r"entities_tenant_version_idx\s*\n\s*ON research_schema\.entities\s*"
        r"\(tenant_id, entity_id, version\)",
        sql,
    )


def test_required_constraints_per_contract() -> None:
    """Per-synthetic-tenant unique keys, epochs, versions, dependency links, ledger."""
    sql = _load_sql()
    # Explicit per-synthetic-tenant unique keys.
    assert "PRIMARY KEY (tenant_id, entity_id)" in sql
    assert "REFERENCES research_schema.benchmark_tenants" in sql
    # Policy + consent epochs exist with epoch columns.
    assert "governance_epochs" in sql and "policy_version" in sql
    assert "consent_epochs" in sql and "consent_state" in sql
    # Version columns on entities and history.
    assert re.search(r"version\s+bigint NOT NULL DEFAULT 0", sql)
    # Dependency links table and operation ledger.
    assert "op_dependency_edges" in sql
    assert "op_log" in sql
    # Rollback helper is provided (migration+rollback DoD).
    assert "compsac_x03_rollback" in sql


# --------------------------------------------------- (c) real isolated PG16
def _pg_reachable() -> tuple[bool, str]:
    """Fail-closed reachability probe for the isolated research cluster only.

    The DSN must pass pg_guard first; then a trivial psql ping runs inside
    pg_research_net. Any failure returns (False, real_output).
    """
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
    if ping.returncode != 0:
        return False, (ping.stderr or ping.stdout).strip()[-300:]
    return True, ping.stdout.strip()


PG_OK, PG_REASON = _pg_reachable()

PG_SKIPIF = pytest.mark.skipif(
    not PG_OK, reason=f"PG NOT_RUN: isolated research PG16 unreachable: {PG_REASON}"
)


def _psql_in_network(sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "pg_research_net",
            "-v",
            f"{REPO}:/work:ro",
            PG_IMAGE,
            "psql",
            ISOLATED_DSN,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )


@PG_SKIPIF
def test_pg16_apply_schema_and_tables_exist() -> None:
    """REAL PostgreSQL 16: apply DDL, assert tables/indexes exist, then rollback."""
    apply = _psql_in_network(f"\\i /work/{SQL_PATH.relative_to(REPO)}")
    output = (apply.stdout + "\n" + apply.stderr).strip()
    assert apply.returncode == 0, f"psql apply failed:\n{output[-1500:]}"
    assert "ERROR" not in output, output[-1500:]

    catalog = _psql_in_network(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='research_schema' ORDER BY table_name;"
    )
    tables_out = catalog.stdout
    assert catalog.returncode == 0, (catalog.stdout + catalog.stderr)[-800:]
    for table in REQUIRED_TABLES:
        bare = table.split(".", 1)[1]
        assert bare in tables_out, f"missing table {table} in:\n{tables_out}"

    indexes = _psql_in_network(
        "SELECT indexname FROM pg_indexes WHERE schemaname='research_schema' " "ORDER BY indexname;"
    )
    assert indexes.returncode == 0, (indexes.stdout + indexes.stderr)[-800:]
    for idx in REQUIRED_INDEXES:
        assert idx in indexes.stdout, f"missing index {idx} in:\n{indexes.stdout}"

    version = subprocess.run(
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
            "SHOW server_version;",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert version.returncode == 0 and version.stdout.strip().startswith(
        "16"
    ), f"expected PG16, saw {version.stdout!r} {version.stderr[-200:]}"

    rollback = _psql_in_network("SELECT research_schema.compsac_x03_rollback();")
    assert rollback.returncode == 0, (rollback.stdout + rollback.stderr)[-800:]
    after = _psql_in_network(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='research_schema' AND table_name<>'compsac_x03_rollback';"
    )
    # psql -c prints the function name row plus the count row.
    count_line = [ln for ln in after.stdout.splitlines() if ln.strip().isdigit()]
    assert count_line and int(count_line[-1]) == 0, after.stdout
