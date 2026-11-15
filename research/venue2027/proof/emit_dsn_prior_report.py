"""Emit the DSN-prior task report via agent_protocol.build_report.

Purpose
-------
Assembles and validates the single task report for ``DSN-prior`` using the
shared protocol tool (imported, not reimplemented). Every declared command
log and artifact must exist on disk with a matching SHA256 before the report
may claim ``ok:true``.

Allowed input
-------------
Read-only hashing of the task artifacts inside this repository. No network,
no database, no randomness.

Failure semantics
-----------------
Exits 1 if the assembled report fails ``validate_report``; the validation
payload is printed either way.

Version
-------
``DSN_PRIOR_EMIT_VERSION = "1.0.0"``
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SHARED_TOOLS = REPO_ROOT / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS.resolve()))

import agent_protocol  # noqa: E402

DSN_PRIOR_EMIT_VERSION = "1.0.0"

MATRIX = "research/venue2027/dsn/literature_matrix.csv"
TESTS = "research/venue2027/dsn/tests/test_literature_matrix.py"


def main() -> int:
    report = agent_protocol.build_report(
        task_id="DSN-prior",
        status="PASS",
        source_sha_before="9b6be889db89c2228c6ea1ac599f0000d03c63a4",
        source_sha_after="9b6be889db89c2228c6ea1ac599f0000d03c63a4",
        changed_paths=[
            MATRIX,
            TESTS,
            "research/venue2027/proof/DSN-prior.json",
            "research/venue2027/proof/logs/DSN-prior.validator.log",
            "research/venue2027/proof/logs/DSN-prior.pytest.log",
            "research/venue2027/proof/logs/DSN-prior.suite.log",
            "research/venue2027/proof/logs/DSN-prior.shared_regression.log",
            "research/venue2027/proof/logs/DSN-prior.ruff.log",
        ],
        commands=[
            {
                "argv": "python3 research/venue2027/_shared/tools/comparator_matrix.py "
                "research/venue2027/dsn/literature_matrix.csv",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-prior.validator.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/dsn/tests/test_literature_matrix.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-prior.pytest.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/dsn/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-prior.suite.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-prior.shared_regression.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check research/venue2027/dsn/tests/test_literature_matrix.py "
                "&& uvx ruff@0.7.1 format --check research/venue2027/dsn/tests/test_literature_matrix.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-prior.ruff.log",
            },
        ],
        artifact_paths=[MATRIX, TESTS],
        repo=REPO_ROOT,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P01 prior-art implementation and verification ledger for DSN (Recoverable Safety "
            "Journals for Crash-Consistent AI-Mediated Health-State Mutations): "
            "literature_matrix.csv with 10 comparators carrying exactly "
            "comparator_matrix.REQUIRED_COLUMNS and >=40-char mechanism_analysis on every row. "
            "Blueprint arms recorded: B0 single-write transactional commit + fire-and-forget side "
            "effect (weak control), B1 PostgreSQL atomic write + transactional outbox + idempotent "
            "consumer (mandatory strong practical baseline; upstream postgres/postgres tag REL_16_9 "
            "commit 6e4ab1b69197e2756192a1019439aebacdea5497 re-verified via git ls-remote on "
            "2026-11-15, ORIGINAL_UPSTREAM), B2 durable workflow/saga with compensation and stable "
            "operation IDs (temporalio tag 1.19.0 commit 11e8650c7c8b89af45fab328e400d2fd5a9af16c "
            "re-verified, ORIGINAL_UPSTREAM), B3 fsync/durability reference (Pillai et al. OSDI 14, "
            "crash-consistency update protocols; no pinnable official ALICE upstream, honestly "
            "no/UNAVAILABLE_NOT_RUN), B4 candidate reconciliation safety journal (tri-state "
            "COMMITTED/REJECTED/INDETERMINATE, declared falsifiable, never presented as runnable), "
            "B5 monotonic single-journal internal control, plus B2b WAL/ARIES recovery reference "
            "(Mohan et al. ACM TODS 17(1) 1992, DOI 10.1145/128765.128770 verified via Crossref; "
            "no executable reference implementation exists, honestly UNAVAILABLE_NOT_RUN). "
            "Registry comparators cite exactly their MANIFESTS/literature_registry.json locators "
            "(verified by test): ct9162 (RFC 9162 append-only log integrity is not reconciliation), "
            "elle20 (jepsen-io/elle pinned oracle side, HEAD 4e359e597c52938b0afebb8bc42273914d68a424 "
            "live-checked, repo verified, ORIGINAL_UPSTREAM; oracle reviewer must not reuse candidate "
            "code), silo13 (SOSP 2013 serializable single-store CC boundary, no official code release, "
            "UNAVAILABLE_NOT_RUN). No implementation was fabricated: evaluation/venue2027/dsn does "
            "not exist in this worktree, so all in-project B-arms are honestly UNAVAILABLE_NOT_RUN, "
            "and available_code=yes appears only on rows with verified upstream code (B1 postgres, "
            "B2 temporalio, elle20). Shared validator: ok=true, row_count=10, exit 0. Tests: 28 "
            "passed (real-matrix pass, exact REQUIRED_COLUMNS, registry-locator consistency, "
            "tri-state framing, mandatory-B1/equal-budget falsification clause, oracle independence, "
            "pinned revisions, no empirical values, cross-study firewall E15-E22/COMPSAC/IFIP, "
            "contract GO declaration - plus adversarial failures: fabricated id "
            "UNKNOWN_COMPARATOR_ID, missing link MISSING_SOURCE_LINK, thin mechanism "
            "MECHANISM_ANALYSIS_MISSING, available_code=yes without code_url "
            "AVAILABLE_CODE_WITHOUT_URL, ORIGINAL_UPSTREAM without code UPSTREAM_WITHOUT_CODE, "
            "FAITHFUL_PORT without code_url PORT_WITHOUT_CODE). DSN venue suite: 80 passed; shared "
            "regression: 167 passed. uvx ruff@0.7.1 check + format --check clean on the test file "
            "(the pinned formatter version is authoritative per the sibling task convention). No "
            "empirical numbers, no clinical claims, no real PHI; source_sha_after records the base "
            "SHA of the single task commit per sibling convention (ACNS-prior/AIME-prior: the "
            "pre-commit HEAD is recorded and the commit itself is created immediately after the "
            "report hash freeze)."
        ),
    )
    result = agent_protocol.validate_report(report, repo=REPO_ROOT, expected_task_id="DSN-prior")
    print(json.dumps(result.to_dict(), indent=2))
    out = REPO_ROOT / "research" / "venue2027" / "proof" / "DSN-prior.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report written: {out}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
