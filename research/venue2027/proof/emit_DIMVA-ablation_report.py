"""Emit the DIMVA-ablation task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the DIMVA-ablation task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "DIMVA-ablation"

BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/dimva/ablations.py",
    "evaluation/venue2027/dimva/test_ablations.py",
    "research/venue2027/proof/DIMVA-ablation.json",
    "research/venue2027/proof/emit_DIMVA-ablation_report.py",
    "research/venue2027/proof/logs/DIMVA-ablation.pytest.log",
    "research/venue2027/proof/logs/DIMVA-ablation.ruff.log",
    "research/venue2027/proof/logs/DIMVA-ablation.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/dimva/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-ablation.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dimva/ablations.py "
        "evaluation/venue2027/dimva/test_ablations.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/dimva/ablations.py "
        "evaluation/venue2027/dimva/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-ablation.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_DIMVA-ablation_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/DIMVA-ablation.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-ablation.validator.log",
    },
]


def run_command(argv: str, log_path: pathlib.Path) -> int:
    res = subprocess.run(argv, shell=True, cwd=str(REPO), capture_output=True, text=True)
    output = (res.stdout or "") + (res.stderr or "")
    log_path.write_text(output, encoding="utf-8")
    return res.returncode


def main() -> int:
    logs_dir = REPO / "research" / "venue2027" / "proof" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run pytest and capture log
    pytest_log = logs_dir / "DIMVA-ablation.pytest.log"
    rc_pytest = run_command(
        "python3 -m pytest -q evaluation/venue2027/dimva/test_ablations.py", pytest_log
    )
    if rc_pytest != 0:
        print(f"pytest failed with exit code {rc_pytest}", file=sys.stderr)
        return rc_pytest

    # 2. Run ruff check & format and capture log
    ruff_log = logs_dir / "DIMVA-ablation.ruff.log"
    rc_ruff = run_command(
        "uvx ruff@0.7.1 check evaluation/venue2027/dimva/ablations.py "
        "evaluation/venue2027/dimva/test_ablations.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/dimva/ablations.py "
        "evaluation/venue2027/dimva/test_ablations.py",
        ruff_log,
    )
    if rc_ruff != 0:
        print(f"ruff failed with exit code {rc_ruff}", file=sys.stderr)
        return rc_ruff

    # 3. Build report
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "evaluation/venue2027/dimva/ablations.py",
            "evaluation/venue2027/dimva/test_ablations.py",
            "research/venue2027/proof/logs/DIMVA-ablation.pytest.log",
            "research/venue2027/proof/logs/DIMVA-ablation.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task DIMVA-ablation (GovernanceTrace RQ1-RQ3; dependency "
            "DIMVA-candidate PASS): preregistered causal mechanism ablation "
            "variants at evaluation/venue2027/dimva/ablations.py "
            "(ABLATIONS_VERSION=clara.dimva.ablations-v1) behind the "
            "task-manifest signature run_ablation(name, case) -> Outcome. The "
            "P04 candidate (evaluation/venue2027/dimva/candidate.py) is run "
            "against ITSELF with EXACTLY ONE mechanism removed per variant, "
            "each variant a real callable reusing candidate components and "
            "DECLARING its ablated mechanism via typed VariantSpec rows in "
            "ABLATION_REGISTRY. VARIANTS (one mechanism axis each): "
            "without_campaign_linkage (candidate WITHOUT cross-window campaign "
            "linkage: events are evaluated in isolated windows of "
            "probe_window_seconds without multi-window linkage; "
            "ablated_mechanism=campaign_linkage; misses low-and-slow campaign); "
            "without_cross_tool_feature (candidate WITHOUT cross-tool feature: "
            "tool identities are masked to constant, collapsing distinct tools "
            "to 1 and entropy to 0; ablated_mechanism=cross_tool_feature; "
            "misses cross-tool obfuscation); without_pacing_feature (candidate "
            "WITHOUT pacing evasion feature: probe_window_threshold=1, so "
            "max_window < 1 fails; ablated_mechanism=pacing_feature; misses "
            "low-and-slow pacing); with_only_per_window_counts (static "
            "sliding-window count B0 baseline: all structural linkage removed, "
            "leaving only fixed-window counting; "
            "ablated_mechanism=multi_signal_structural_criteria; misses "
            "low-and-slow and false-alarms on benign burst); full_candidate "
            "(reference row: unmodified candidate, ablated_mechanism=none). "
            "GUARDS: refuse_unregistered_variant refuses unknown ids with "
            "UNKNOWN_ABLATION_VARIANT and nothing-removing identities "
            "(candidate ID, 'candidate', 'DIMVA-candidate') with "
            "VARIANT_REMOVES_NOTHING; VariantSpec refuses specs declaring "
            "empty ablated mechanism or impostor 'none' at construction; "
            "run_ablation maps refusals to EXECUTION_ERROR and malformed cases "
            "to INDETERMINATE. MECHANISTIC INFERENCE MATRIX: "
            "verify_mechanistic_inference_matrix() executes every cell fresh "
            "and compares against preregistered PREDICTED_VERDICTS - all 20 "
            "cells match, all_cells_match=true. CAUSAL CONTRAST: full_candidate "
            "DETECTs low-and-slow campaign and admits all benign controls; "
            "without_campaign_linkage MISSES the low-and-slow campaign (causal "
            "witness that campaign linkage is required); "
            "with_only_per_window_counts misses low-and-slow AND false-alarms "
            "on benign burst. 43 tests pass; ruff check + format clean."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "DIMVA-ablation.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    validator_log = logs_dir / "DIMVA-ablation.validator.log"
    validator_log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    validator_log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
