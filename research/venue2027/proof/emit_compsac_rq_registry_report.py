"""Emit research/venue2027/proof/COMPSAC-rq_registry.json via agent_protocol."""

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

BEFORE = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"
AFTER = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/compsac/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-rq_registry.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/compsac/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.check.log",
    },
    {
        "argv": "uvx ruff@0.7.1 format --check research/venue2027/compsac/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.log",
    },
]

ARTIFACTS = [
    "research/venue2027/compsac/rq_and_estimands.yaml",
    "research/venue2027/compsac/tests/test_rq_registry.py",
    "research/venue2027/proof/logs/COMPSAC-rq_registry.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.check.log",
    "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.log",
]

NOTES = (
    "P01 RQ registry frozen as preregistered_only design decisions (compsac-rq-registry-v1, "
    "JSON-serializable via read_rqs()->RQPlan; no measured results recorded). Exactly 3 RQs, "
    "each with all 14 required fields: RQ1 dependency-complete read set vs global OCC with the "
    "two-gate primary endpoint (safety gate = forbidden commit rate, zero required, one-sided "
    "Clopper-Pearson 1-0.05**(1/N) bound vs frozen margin 0.01; utility gate = oracle-defined "
    "false-stale rate, min useful difference 0.10 absolute with cluster-bootstrap CI low > 0); "
    "RQ2 omitted-dependency propagation + separate-oracle per-fault-family detection with "
    "Clopper-Pearson intervals and Fisher exact arm contrasts, indeterminate in denominator; "
    "RQ3 B4-vs-B2 committed throughput ratio over the fanout x workers (1/2/4/8/16) x Zipf x "
    "density grid with crossover = smallest tested level whose ratio CI includes 1. Independent "
    "unit = one independent logical schedule per the shared schedule engine "
    "(evaluation/venue2027/_shared/schedules.py 1.0.0), cluster = schedule (never per-event "
    "pseudo-replication); population = case x arm x seed with >= 5 independent seeds per "
    "setting; statistical analysis frozen to the shared analysis_policy.py 1.0.0 (exact McNemar "
    "+ seeded cluster bootstrap, seed 2027, 2000 resamples); all five blueprint arms B0-B4 and "
    "the import-disjoint oracle declared; SQLite-never-as-PostgreSQL and E15-E22 archive "
    "refusals carried in the analysis contract. Tests: 17 passed including adversarial "
    "fail-closed loader probes (comment-only, unterminated-flow, no-colon inputs refused) and "
    "an invented-results regex scan; ruff check + format clean on the touched test file. "
    "Pre-existing repo-wide ruff errors (273) verified identical at base SHA with and without "
    "the new files; zero in research/venue2027/compsac. Deliverable commit SHA reported in "
    "task handoff (a commit cannot embed its own SHA)."
)


def main() -> int:
    report = build_report(
        task_id="COMPSAC-rq_registry",
        status="PASS",
        source_sha_before=BEFORE,
        source_sha_after=AFTER,
        changed_paths=[
            "research/venue2027/compsac/rq_and_estimands.yaml",
            "research/venue2027/compsac/tests/test_rq_registry.py",
            "research/venue2027/proof/COMPSAC-rq_registry.json",
            "research/venue2027/proof/logs/COMPSAC-rq_registry.pytest.log",
            "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.check.log",
            "research/venue2027/proof/logs/COMPSAC-rq_registry.ruff.log",
        ],
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research/venue2027/proof/COMPSAC-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="COMPSAC-rq_registry",
        completed_tasks=["COMPSAC-scope", "SH-analysis_policy"],
        task_dependencies=["COMPSAC-scope", "SH-analysis_policy"],
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
