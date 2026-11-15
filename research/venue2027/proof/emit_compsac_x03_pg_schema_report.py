"""Emit the COMPSAC-X03_pg_schema task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED_PATHS = [
    "infra/research/venue2027/schema/compsac_benchmark.sql",
    "research/venue2027/compsac/tests/test_pg_schema.py",
    "research/venue2027/proof/COMPSAC-X03_pg_schema.json",
    "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.ruff.log",
    "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.validator.log",
]

COMMANDS = [
    {
        "argv": ("python3 -m pytest -q research/venue2027/compsac/tests/" "test_pg_schema.py -rs"),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check research/venue2027/compsac/tests/"
            "test_pg_schema.py && uvx ruff@0.7.1 format --check "
            "research/venue2027/compsac/tests/test_pg_schema.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.ruff.log",
    },
]

ARTIFACTS = [
    "infra/research/venue2027/schema/compsac_benchmark.sql",
    "research/venue2027/compsac/tests/test_pg_schema.py",
    "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.ruff.log",
]


def main() -> int:
    # Sibling convention (COMPSAC-X05_silo_occ, COMPSAC-X06_coarse_occ): the
    # task is delivered as EXACTLY ONE commit that contains this report, so
    # source_sha_after records the base commit; the single task commit SHA is
    # created immediately after this report and reported in the handoff.
    sha_after = BASE

    report = ap.build_report(
        task_id="COMPSAC-X03_pg_schema",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED_PATHS,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "COMPSAC-X03_pg_schema (P04, venue compsac, RQ1 infrastructure): "
            "delivered the isolated benchmark partition/version DDL at "
            "infra/research/venue2027/schema/compsac_benchmark.sql "
            "(COMPSAC_X03_SCHEMA_VERSION 1.0.0) plus its structural + real-"
            "integration test research/venue2027/compsac/tests/test_pg_schema.py. "
            "SCHEMA: everything lives in the dedicated research_schema namespace "
            "(CREATE SCHEMA IF NOT EXISTS research_schema; no public.* reference, "
            "no production table touched, never wired into the API service's "
            "versioned migration directory). Tables: benchmark_tenants (explicit "
            "per-synthetic-tenant registry; entities PK (tenant_id, entity_id) so "
            "benchmark arms cannot cross-contaminate), entities (entity_kind "
            "CHECK medication_order/allergy/history/purpose_grant, version bigint "
            ">= 0 version column), entity_version_partitions (append-only "
            "per-entity version history, PK (tenant_id, entity_id, version), "
            "payload_sha256 hex-64 CHECK, FK ON DELETE CASCADE), governance_epochs "
            "(policy_version, active boolean with UNIQUE (tenant_id, active) "
            "single-active-epoch guard), consent_epochs (consent_state "
            "granted/revoked/withdrawn, UNIQUE (tenant_id, subject_id, active)), "
            "op_log (append-only operation ledger: op_kind "
            "read/write/commit/abort/epoch_bump, status "
            "pending/committed/aborted, attempt >= 0 with outcome CHECK "
            "committed/aborted requires attempt > 0, base_version/observed_version "
            "CAS admission columns, governance_epoch/consent_epoch bindings), and "
            "op_dependency_edges (required_read/write dependency links resolving "
            "to real entity versions via composite FK). Indexes for version "
            "lookups: entities_tenant_version_idx (tenant_id, entity_id, version), "
            "entity_version_partitions_history_idx, governance_epochs_tenant_idx, "
            "consent_epochs_subject_idx, op_log_tenant_status_idx, op_log_entity_idx, "
            "op_dependency_edges_entity_idx. Rollback: idempotent "
            "research_schema.compsac_x03_rollback() dropping exactly the seven "
            "benchmark tables in FK-safe order (migration+rollback DoD). "
            "TESTS (6 passed, exit 0): (a) DDL parses/normalizes via a fail-closed "
            "statement splitter (balanced single/double quotes, dollar-quoting, "
            "line/block comments; unbalanced input raises, never passes); "
            "(b) every CREATE TABLE/INDEX/COMMENT statement targets "
            "research_schema (target-name extraction, public.* forbidden, no "
            "production migration path reference); required tables + indexes + "
            "contract constraints asserted textually; (c) REAL PostgreSQL 16 "
            "integration: the test probes the disposable compose cluster "
            "(docker-compose.pg.yaml, network pg_research_net, DSN "
            "postgresql://research_app:...@pg_research:5432/clara_research) which "
            "MUST pass pg_guard.assert_isolated_database_url first (fail-closed: "
            "localhost/SQLite never substituted), applies the file with psql "
            "-v ON_ERROR_STOP=1 inside pg_research_net, asserts SHOW "
            "server_version starts with 16 (observed 16.4), asserts all 7 tables "
            "exist via information_schema and all 7 indexes via pg_indexes, then "
            "runs compsac_x03_rollback() and asserts 0 benchmark tables remain. "
            "PG WAS ACTUALLY USED: the live isolated cluster "
            "(container clara-pg-research, image postgres@sha256:e62fbf9d...) was "
            "up and healthy; psql apply/verify/rollback ran against it for real "
            "(server logs recorded CREATE TABLE research_schema.* statements); "
            "NOT_RUN was NOT used. uvx ruff@0.7.1 check + format --check clean, "
            "exit 0. baseline_parity=NOT_APPLICABLE (schema-only task; no "
            "comparator arm). oracle_disagreement_count=0 (no oracle vector in "
            "scope; adjudication belongs to COMPSAC-oracle). source_sha_after "
            "records the base commit 11a9219c per sibling convention (X05/X06): "
            "the single task commit is created immediately after this report and "
            "reported in the handoff. Caveat disclosed: STATE/completion.json "
            "carries a concurrent user-owned IFIP_SEC-X01 entry from another "
            "agent; this task neither touches nor commits it. Next ready tasks "
            "in this scope: COMPSAC-X04_pg_ssi, COMPSAC-X07_scope_occ."
        ),
    )

    out = REPO / "research/venue2027/proof/COMPSAC-X03_pg_schema.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="COMPSAC-X03_pg_schema",
    )
    log_path = REPO / "research/venue2027/proof/logs/COMPSAC-X03_pg_schema.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
