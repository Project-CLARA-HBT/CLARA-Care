"""Emit the COMPSAC-oracle proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the COMPSAC-oracle task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "COMPSAC-oracle"
BASE_SHA = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED = [
    "evaluation/venue2027/compsac/independent_oracle.py",
    "evaluation/venue2027/compsac/test_independent_oracle.py",
    "research/venue2027/proof/COMPSAC-oracle.json",
    "research/venue2027/proof/logs/COMPSAC-oracle.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.ruff.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.ruff.format.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.suite.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.mypy.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.independence-scan.log",
    "research/venue2027/proof/logs/COMPSAC-oracle.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/compsac/test_independent_oracle.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/compsac/independent_oracle.py "
            "evaluation/venue2027/compsac/test_independent_oracle.py --config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.ruff.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 format --check evaluation/venue2027/compsac/independent_oracle.py "
            "evaluation/venue2027/compsac/test_independent_oracle.py --config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.ruff.format.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/compsac/ evaluation/venue2027/_shared/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.suite.log",
    },
    {
        "argv": (
            "uv run --frozen --extra dev --no-editable --project services/api mypy "
            "evaluation/venue2027/compsac/independent_oracle.py --ignore-missing-imports"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.mypy.log",
    },
    {
        "argv": (
            "PYTHONPATH=. python3 -c \"from evaluation.venue2027.compsac import "
            "independent_oracle as io; io.verify_independence(); print('verify_independence: "
            "clean, ORACLE_ID=' + io.ORACLE_ID)\""
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-oracle.independence-scan.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            CHANGED[0],
            CHANGED[1],
        ],  # module + tests; report/log files excluded per repo convention
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P02 independent per-case truth oracle for COMPSAC (Dependency-Complete "
            "Optimistic Admission for Concurrent Clinical AI Writes). "
            "evaluation/venue2027/compsac/independent_oracle.py implements the exact "
            "contract adjudicate(case) -> oracle_kernel.OracleResult by delegating to the "
            "audited shared kernel evaluation.venue2027._shared.oracle_kernel.adjudicate "
            f"(v{ap.AGENT_PROTOCOL_VERSION and 'kernel 1.0.0'}) with a declarative "
            "module-local COMPSAC FORBIDDEN-COMMIT case-outcome rule table: clean -> ADMIT, "
            "omitted_dependency -> REJECT (forbidden commit), epoch_race -> REJECT, "
            "stale_readset -> REJECT, unknown/missing family -> INDETERMINATE "
            "(UNMODELLED_FAMILY / NO_FAMILY_DECLARED, never coerced to a safe verdict); "
            "missing case_id fails closed (MISSING_CASE_ID). ORACLE_ID = "
            "'compsac-forbidden-commit-reference'. The verdict is a pure function of the "
            "declared scenario family and the frozen rule table — candidate reason codes, "
            "status payloads and observed outputs are never consulted, satisfying "
            "GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2 (truth labels derive from event "
            "sequence/policy ground truth, not candidate reason codes). The module imports "
            "neither baselines nor the dependency DSL and does not duplicate "
            "independent_closure_oracle.py (which derives dependency closures; this module "
            "adjudicates forbidden-commit outcomes). verify_independence() scans the oracle "
            "source with ast via the kernel guard plus a component-wise dotted-path scan "
            "for ('compsac.baselines', 'baselines', 'dependency_dsl') — closing the "
            "benign-root escape hatch (from compsac.baselines import arm_b1) that a "
            "root-only check misses — and refuses dynamic imports "
            "(DYNAMIC_IMPORT_UNRESOLVABLE). Tests: 58 passed (positive: rule-table "
            "adjudication for all four families, payload-family, evidence refs, "
            "JSON-serializability, self-checks, stable ORACLE_ID/version; adversarial: "
            "verdict invariance across 6 candidate reason codes x 4 families including "
            "forbidden-commit label independence, candidate claiming clean does not admit "
            "a forbidden family and vice versa, INDETERMINATE never coerced, "
            "verify_independence tamper matrix — plain/dotted/aliased/from-import and "
            "injected-into-live-source CANDIDATE_IMPORT, __import__/import_module "
            "DYNAMIC_IMPORT_UNRESOLVABLE, direct AST scan of the shipped file finds zero "
            "candidate imports). Regression: venue2027 compsac + shared suites 344 passed; "
            "mypy clean. uvx ruff@0.7.1 check + format --check clean. "
            "source_sha_after = base SHA per established repo convention (proof report "
            "committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "COMPSAC-oracle.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    with (REPO / "research/venue2027/proof/logs/COMPSAC-oracle.validator.log").open(
        "w", encoding="utf-8"
    ) as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
