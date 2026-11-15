"""Emit the POPETS-rq_registry task report via agent_protocol.build_report.

Read-only with respect to research data: assembles the handoff report, hashes
the declared artifacts, validates with validate_report (ok must be true), and
writes research/venue2027/proof/POPETS-rq_registry.json.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "POPETS-rq_registry"
REPORT_PATH = REPO / "research" / "venue2027" / "proof" / f"{TASK_ID}.json"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    sha_before = "293bde7bce7b0a361306e40e04fba931cfc0623d"
    sha_after = _git("rev-parse", "HEAD")
    changed = [
        "research/venue2027/popets/rq_and_estimands.yaml",
        "research/venue2027/popets/tests/test_rq_registry.py",
        "research/venue2027/proof/logs/POPETS-rq_registry.pytest.log",
        "research/venue2027/proof/logs/POPETS-rq_registry.ruff.log",
        "research/venue2027/proof/logs/POPETS-rq_registry.suite.log",
        "research/venue2027/proof/POPETS-rq_registry.json",
    ]
    commands = [
        {
            "argv": "python3 -m pytest -q research/venue2027/popets/tests/test_rq_registry.py",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/POPETS-rq_registry.pytest.log",
        },
        {
            "argv": (
                "uvx ruff@0.7.1 check research/venue2027/popets/tests/test_rq_registry.py "
                "--config ruff.toml"
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/POPETS-rq_registry.ruff.log",
        },
        {
            "argv": "python3 -m pytest -q research/venue2027/popets/tests/",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/POPETS-rq_registry.suite.log",
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
            "research/venue2027/popets/rq_and_estimands.yaml",
            "research/venue2027/popets/tests/test_rq_registry.py",
            "research/venue2027/proof/logs/POPETS-rq_registry.pytest.log",
            "research/venue2027/proof/logs/POPETS-rq_registry.ruff.log",
            "research/venue2027/proof/logs/POPETS-rq_registry.suite.log",
        ],
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P01 RQ/estimand registry for popets frozen before holdout unsealing. "
            "Exactly three preregistered RQs (RQ1-RQ3), each with research question "
            "(verbatim from the blueprint), independent unit (unique synthetic subject "
            "history — never per-dispatch), population (1200 subjects, 3-6 longitudinal "
            "contexts, source-disjoint holdout), estimand, paired contrast, primary metric "
            "(RQ1 future unauthorized disclosure rate + attribute-exposure bytes; RQ2 "
            "disclosure-trace equivalence to B2 within TOST margin + false invalidation vs "
            "B3; RQ3 conditional cache hit rate + p95 latency across factorial lineage "
            "density), secondary metrics, H0/H1, frozen minimum useful differences "
            "(delta_1/delta_2/delta_3 = 0.05 absolute), confounders, power/analysis method "
            "(exact McNemar / TOST + Wilcoxon / repeated-measures ANOVA; subject-clustered "
            "bootstrap 2000 resamples seed 2027, Holm across 3 primary contrasts), "
            "falsification_condition and primary_endpoint. Endpoint class "
            "future_dispatch_noninterference: forensic reconstructability (PST) and "
            "retroactive erasure of already-delivered content refused. Mechanical "
            "falsification register F1-F6. No empirical results asserted; archive E15-E22 "
            "refused as evidence. stdlib-only YAML-subset parser verified identical to "
            "PyYAML on this file; structural tests 23/23 pass; ruff 0.7.1 clean; venue "
            "suite 76/76 pass. source_sha_after is the worktree HEAD at emit time; the "
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
