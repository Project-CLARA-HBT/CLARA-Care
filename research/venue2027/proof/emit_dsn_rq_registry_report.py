"""Emit research/venue2027/proof/DSN-rq_registry.json via agent_protocol."""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
SHARED_TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(SHARED_TOOLS.resolve()))

import agent_protocol  # noqa: E402

build_report = agent_protocol.build_report
validate_report = agent_protocol.validate_report

BEFORE = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"
AFTER = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/dsn/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-rq_registry.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/dsn/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-rq_registry.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/dsn/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-rq_registry.ruff.log",
    },
    {
        "argv": "uvx ruff@0.7.1 format --check research/venue2027/dsn/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-rq_registry.format.log",
    },
]

ARTIFACTS = [
    "research/venue2027/dsn/rq_and_estimands.yaml",
    "research/venue2027/dsn/tests/test_rq_registry.py",
    "research/venue2027/proof/logs/DSN-rq_registry.pytest.log",
    "research/venue2027/proof/logs/DSN-rq_registry.suite.log",
    "research/venue2027/proof/logs/DSN-rq_registry.ruff.log",
    "research/venue2027/proof/logs/DSN-rq_registry.format.log",
]

NOTES = (
    "Frozen RQ/estimand/hypothesis registry (rq_and_estimands.yaml v1.0.0, "
    "JSON-compatible YAML subset parsed by a tiny stdlib parser - no pyyaml). For each of "
    "RQ1-RQ3 exactly the required fields are preregistered: verbatim blueprint question_text, "
    "independent unit (deduplicated crash/replay history per RQ1/RQ2; matched benchmark "
    "repetition per RQ3 - never per-event pseudo-replication), population, estimand, paired "
    "contrast (RQ1: B3-B1 McNemar discordant histories; RQ2: B3-B2 Wilcoxon signed-rank paired "
    "counts; RQ3: B3-B1 durable-write/latency and B3-B2 RTO paired bootstrap at indifference "
    "margins), primary + secondary metrics, two-sided null/alternative, pre-registered minimum "
    "useful difference (RQ1: 0.01 per history; RQ2: >=1 event or 0.01 mean per history; RQ3: "
    "0.5 fsync / 15% p99 latency / 15% RTO p99 margins), confounders, pilot-based power method "
    "(never sample size from target p-values), clustered analysis method, oracle, "
    "missingness policy, randomization, baseline parity requirement, plan_status="
    "PLANNED_PREREGISTERED, per-RQ falsification_condition and pairwise-distinct "
    "primary_endpoint (RQ1 joint-inconsistency event per history; RQ2 replay-safety failure "
    "count per history; RQ3 paired cost contrast per repetition). Design artifact only: "
    "status=PREREGISTERED_DESIGN_NO_RESULTS, zero observed results - all numeric quantities "
    "are design parameters (48x4x3x5 factorial cells, alpha levels, frozen margins, "
    "Clopper-Pearson formula), enforced by RESULT_SHAPES regexes. 26 stdlib tests pass "
    "(exactly-3-RQs, all-16-fields nonempty, nonempty actionable falsification naming B1/B2, "
    "distinct primary endpoints, history/repetition units, cluster analysis, pilot-based "
    "power, no-result-numbers, blueprint-verbatim questions, B0-B3 arms, E15-E22/GovRed "
    "nonreuse, tab-free file, 5 parser vectors incl. indentation/colon/tab/empty rejections, "
    "7 tamper vectors: deleted field, blank falsification, shared endpoint, wrong RQ count, "
    "results status, missing arm, poisoned result text). DSN venue suite 106 passed. "
    "uvx ruff@0.7.1 check + format --check clean (repo-wide check has 1017 pre-existing "
    "errors on the base commit, none in research/venue2027/dsn/). Per sibling DSN-prior "
    "convention, source_sha_after records the base SHA of the single task commit; the "
    "commit is created immediately after report hash freeze."
)


def main() -> int:
    report = build_report(
        task_id="DSN-rq_registry",
        status="PASS",
        source_sha_before=BEFORE,
        source_sha_after=AFTER,
        changed_paths=[
            "research/venue2027/dsn/rq_and_estimands.yaml",
            "research/venue2027/dsn/tests/test_rq_registry.py",
            "research/venue2027/proof/DSN-rq_registry.json",
            "research/venue2027/proof/logs/DSN-rq_registry.pytest.log",
            "research/venue2027/proof/logs/DSN-rq_registry.suite.log",
            "research/venue2027/proof/logs/DSN-rq_registry.ruff.log",
            "research/venue2027/proof/logs/DSN-rq_registry.format.log",
        ],
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research/venue2027/proof/DSN-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-rq_registry",
        completed_tasks=["DSN-scope", "SH-analysis_policy"],
        task_dependencies=["DSN-scope", "SH-analysis_policy"],
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
