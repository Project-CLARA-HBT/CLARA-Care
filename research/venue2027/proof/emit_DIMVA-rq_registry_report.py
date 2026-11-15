"""Emit the DIMVA-rq_registry task report via agent_protocol.build_report.

Read-only with respect to research data: assembles the handoff report, hashes
the declared artifacts, validates with validate_report (ok must be true), and
writes research/venue2027/proof/DIMVA-rq_registry.json.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "DIMVA-rq_registry"
REPORT_PATH = REPO / "research" / "venue2027" / "proof" / f"{TASK_ID}.json"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    sha_before = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"
    sha_after = _git("rev-parse", "HEAD")
    changed = [
        "research/venue2027/dimva/rq_and_estimands.yaml",
        "research/venue2027/dimva/tests/test_rq_registry.py",
        "research/venue2027/proof/logs/DIMVA-rq_registry.pytest.log",
        "research/venue2027/proof/logs/DIMVA-rq_registry.ruff.log",
        "research/venue2027/proof/logs/DIMVA-rq_registry.suite.log",
        "research/venue2027/proof/DIMVA-rq_registry.json",
    ]
    commands = [
        {
            "argv": "python3 -m pytest -q research/venue2027/dimva/tests/test_rq_registry.py",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DIMVA-rq_registry.pytest.log",
        },
        {
            "argv": (
                "uvx ruff@0.7.1 check research/venue2027/dimva/tests/test_rq_registry.py "
                "--config ruff.toml"
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DIMVA-rq_registry.ruff.log",
        },
        {
            "argv": "python3 -m pytest -q research/venue2027/dimva/tests/",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DIMVA-rq_registry.suite.log",
        },
    ]
    report = agent_protocol.build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=sha_before,
        source_sha_after=sha_after,
        changed_paths=changed,
        commands=commands,
        artifact_paths=[
            "research/venue2027/dimva/rq_and_estimands.yaml",
            "research/venue2027/dimva/tests/test_rq_registry.py",
            "research/venue2027/proof/logs/DIMVA-rq_registry.pytest.log",
            "research/venue2027/proof/logs/DIMVA-rq_registry.ruff.log",
            "research/venue2027/proof/logs/DIMVA-rq_registry.suite.log",
        ],
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P01 RQ/estimand registry for dimva frozen before holdout unsealing. "
            "Exactly three preregistered RQs (RQ1-RQ3), each with research question, "
            "independent unit (campaign/benign session — never per-event), population, "
            "estimand, paired contrast, primary metric (probing detection PR-AUC at the "
            "frozen false-positive budget of 10 false alarms per 1,000 benign sessions — "
            "detection, not prevention), secondary metrics, H0/H1, frozen minimum useful "
            "differences (delta_1/delta_2/delta_3 = 0.05 absolute), confounders, "
            "power/analysis method (exact McNemar + cluster bootstrap 2000 resamples seed "
            "2027, Holm across 3 primary contrasts), falsification_condition and "
            "primary_endpoint. Mechanical falsification register F1-F6. No empirical "
            "results asserted; archive E15-E22 refused as evidence; endpoint_class "
            "detection. stdlib structural tests 20/20 pass; ruff 0.7.1 clean; venue suite "
            "104/104 pass. source_sha_after is the worktree HEAD at emit time; the "
            "deliverable commit SHA is reported in the task handoff."
        ),
    )
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = agent_protocol.validate_report(
        report, repo=REPO, expected_task_id=TASK_ID
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
