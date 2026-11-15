"""Emit the ACNS-runner proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-runner task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-runner"

CHANGED = [
    "evaluation/venue2027/acns/runner.py",
    "evaluation/venue2027/acns/test_runner.py",
    "research/venue2027/proof/artifacts/acns_run_bundle.jsonl",
    "research/venue2027/proof/ACNS-runner.json",
    "research/venue2027/proof/logs/ACNS-runner.pytest.log",
    "research/venue2027/proof/logs/ACNS-runner.ruff.log",
    "research/venue2027/proof/logs/ACNS-runner.suite.log",
    "research/venue2027/proof/logs/ACNS-runner.validator.log",
    "research/venue2027/proof/emit_acns_runner_report.py",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_runner.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-runner.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/acns/runner.py "
            "evaluation/venue2027/acns/test_runner.py && uvx ruff@0.7.1 format "
            "--check evaluation/venue2027/acns/runner.py evaluation/venue2027/acns/test_runner.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-runner.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-runner.suite.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/acns/runner.py",
    "evaluation/venue2027/acns/test_runner.py",
    "research/venue2027/proof/artifacts/acns_run_bundle.jsonl",
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before="28ff55110f980f42002524cef126290e91258cd6",
        source_sha_after="28ff55110f980f42002524cef126290e91258cd6",
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "ACNS-runner (Phase P05, venue acns; SoK: Evidence Boundaries of Attestation in "
            "Tool-Using AI Systems): delivered evaluation/venue2027/acns/runner.py implementing "
            "run_campaign(config) -> RunBundle, executing all SoK reference classes "
            "(B0-attestation-only, B1-receipt-without-binding, B2-timestamp-only, "
            "B3-evidence-boundary-aware) over the corpus/evidence records (synthetic-acns-2027) "
            "with equal config, recording evidence-boundary verdicts per record, mutually exclusive "
            "outcomes, source commit SHA, and seeds. Reuses evaluation/venue2027/_shared/harness.py. "
            "Deterministic: identical configs yield identical pair digests and outcome distributions. "
            "Equal config enforcement: differing seeds across arms, differing arm_configs, unequal "
            "timeouts or retry budgets are strictly refused fail-closed with UNEQUAL_CONFIG. Denominator "
            "completeness: crashing arms are captured as EXECUTION_ERROR (counted_as_success=False) "
            "and never dropped; denominator_total is fully partitioned across mutually exclusive buckets. "
            "Evidence-boundary verdicts: every record carries baseline detail and independent oracle "
            "adjudication (B3 achieves 100% agreement with oracle; B0/B1/B2 exhibit expected blind spots). "
            "Real sample run bundle generated at research/venue2027/proof/artifacts/acns_run_bundle.jsonl "
            "recording 16 pairs (4 arms x 4 records: admit=12, reject=4, complete=True). "
            "Tests: 19 passed in evaluation/venue2027/acns/test_runner.py (positive and adversarial "
            "controls); full ACNS suite regression: 162 passed in evaluation/venue2027/acns/. "
            "ruff@0.7.1 check and format clean on touched paths. source_sha_after = base SHA per repo "
            "convention."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-runner.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    val_log = REPO / "research" / "venue2027" / "proof" / "logs" / "ACNS-runner.validator.log"
    val_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
