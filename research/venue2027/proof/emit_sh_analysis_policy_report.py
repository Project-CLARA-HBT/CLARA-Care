"""Emit research/venue2027/proof/SH-analysis_policy.json via agent_protocol."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.venue2027._shared.tools.agent_protocol import build_report, validate_report  # noqa: E402

BEFORE = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"
AFTER = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/_shared/test_analysis_policy.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SH-analysis_policy.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/_shared/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SH-analysis_policy.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/_shared/ --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SH-analysis_policy.ruff.log",
    },
    {
        "argv": "uv run --frozen --extra dev --no-editable --project services/api mypy evaluation/venue2027/_shared/analysis_policy.py --ignore-missing-imports",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SH-analysis_policy.mypy.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/_shared/analysis_policy.py",
    "evaluation/venue2027/_shared/test_analysis_policy.py",
    "research/venue2027/proof/logs/SH-analysis_policy.pytest.log",
    "research/venue2027/proof/logs/SH-analysis_policy.suite.log",
    "research/venue2027/proof/logs/SH-analysis_policy.ruff.log",
    "research/venue2027/proof/logs/SH-analysis_policy.mypy.log",
]

NOTES = (
    "Frozen inferential analysis contract (analysis_policy.py v1.0.0, stdlib-only): "
    "exact two-sided McNemar (exact binomial on discordant pairs; references 22/1024 for (1,9) "
    "and 120920/2^20 for (6,14) reproduced), seeded deterministic cluster bootstrap CI resampling "
    "whole cluster_id groups (raw per-unit differences retained for recalculation per evidence "
    "protocol rule 8), Clopper-Pearson zero-event upper bound 1-0.05**(1/n) (0/598 -> ~0.0050), "
    "two_gate_non_inferiority requiring BOTH the one-sided safety bound to meet the frozen margin "
    "AND the utility improvement to meet its criterion (a non-significant safety difference is "
    "never a certificate; 0/10 inside margin 0.02 still fails because the CP bound 0.2589 "
    "exceeds it), and assert_frozen_analysis refusing post-hoc endpoint/test/margin/unit/alpha/"
    "seed changes with stable reason_code ANALYSIS_DRIFT (seed change refused; 200 same-patient "
    "events stay one cluster, n_clusters=1, degenerate CI at the point estimate). 25 positive + "
    "adversarial tests pass; full _shared suite 68 passed; ruff and mypy clean."
)


def main() -> int:
    report = build_report(
        task_id="SH-analysis_policy",
        status="PASS",
        source_sha_before=BEFORE,
        source_sha_after=AFTER,
        changed_paths=[
            "evaluation/venue2027/_shared/analysis_policy.py",
            "evaluation/venue2027/_shared/test_analysis_policy.py",
            "research/venue2027/proof/SH-analysis_policy.json",
            "research/venue2027/proof/logs/SH-analysis_policy.pytest.log",
            "research/venue2027/proof/logs/SH-analysis_policy.suite.log",
            "research/venue2027/proof/logs/SH-analysis_policy.ruff.log",
            "research/venue2027/proof/logs/SH-analysis_policy.mypy.log",
        ],
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research/venue2027/proof/SH-analysis_policy.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="SH-analysis_policy",
        completed_tasks=["SH-independent_oracle"],
        task_dependencies=["SH-independent_oracle"],
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
