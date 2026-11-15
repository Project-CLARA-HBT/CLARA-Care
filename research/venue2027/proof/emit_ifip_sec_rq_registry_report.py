"""Emit the IFIP_SEC-rq_registry task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"


def main() -> int:
    # Single-commit convention (IFIP_SEC-scope / IFIP_SEC-threat precedent):
    # the required single commit contains this self-referential report, so
    # before == after == the parent source state; the final deliverable commit
    # SHA is reported in the handoff.
    sha = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="IFIP_SEC-rq_registry",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=[
            "research/venue2027/ifip_sec/rq_and_estimands.yaml",
            "research/venue2027/ifip_sec/tests/test_rq_registry.py",
            "research/venue2027/proof/IFIP_SEC-rq_registry.json",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.suite.log",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.ruff.log",
        ],
        commands=[
            {
                "argv": "python3 -m pytest -q research/venue2027/ifip_sec/tests/test_rq_registry.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-rq_registry.pytest.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/ifip_sec/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-rq_registry.suite.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check research/venue2027/ifip_sec/ --config ruff.toml",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-rq_registry.ruff.log",
            },
        ],
        artifact_paths=[
            "research/venue2027/ifip_sec/rq_and_estimands.yaml",
            "research/venue2027/ifip_sec/tests/test_rq_registry.py",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.suite.log",
            "research/venue2027/proof/logs/IFIP_SEC-rq_registry.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P01 frozen RQ/estimand/hypothesis/metrics registry (preregistration, not evidence). "
            "read_rqs()->RQPlan returns exactly RQ1-RQ3, each with all 14 mandated fields "
            "(question verbatim from blueprint, independent_unit, population, estimand, "
            "paired_contrast, primary_metric, secondary_metrics, null H0, alternative H1, "
            "minimum_useful_difference, confounders, power_analysis_method, analysis_method, "
            "falsification_condition, primary_endpoint). Units are unique interleaving "
            "histories / benchmark schedules with within-unit clustering declared; pooling "
            "repeated events as independent draws is refused (the task's registered negative "
            "control). Zero-event handling is one-sided Clopper-Pearson 1-0.05**(1/N), never a "
            "safety proof; RQ3 uses the frozen two-gate non-inferiority certificate with "
            "predeclared margins (token bytes <= +4096, p95 latency <= +10 ms, DB round trips "
            "<= +4). RQ2 requires real PostgreSQL 16 and declares SQLite stand-ins inadmissible. "
            "Denominator categories (eligible/attempted/completed/rejected/indeterminate/"
            "timeout/not_run_external/missing) predeclared in population_common. Paired "
            "contrasts: RQ1 B4-vs-B1 with B2 co-comparator, RQ2 B4-vs-B3, RQ3 B4-vs-B1/B2. "
            "Inferential machinery frozen to evaluation/venue2027/_shared/analysis_policy.py "
            "(exact McNemar, cluster bootstrap, Clopper-Pearson, ANALYSIS_DRIFT). No invented "
            "empirical results: regex gates refuse p-values/CIs/observed rates in the "
            "preregistration. 21 stdlib tests (positive + adversarial mutations refused: "
            "missing field, 4th RQ, per-event unit, SQLite-backed RQ2) pass; full ifip_sec "
            "suite 103 passed; ruff 0.7.1 clean. SHA convention follows repo precedent "
            "(IFIP_SEC-scope / IFIP_SEC-threat): before==after==parent source state because "
            "the single required commit contains this self-referential report; the final "
            "deliverable commit SHA is reported in the handoff."
        ),
    )

    out = REPO / "research/venue2027/proof/IFIP_SEC-rq_registry.json"
    out.write_text(json.dumps(report, indent=4, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        report,
        repo=REPO,
        expected_task_id="IFIP_SEC-rq_registry",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
