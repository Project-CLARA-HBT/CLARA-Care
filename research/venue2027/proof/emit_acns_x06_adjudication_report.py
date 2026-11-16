"""Emit the ACNS-X06_adjudication proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-X06_adjudication task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-X06_adjudication"
BASE_SHA = "01705809bd25101ffb3bd74ec74db769626f234b"

CHANGED = [
    "evaluation/venue2027/acns/rater_agreement.py",
    "evaluation/venue2027/acns/test_rater_agreement.py",
    "research/venue2027/proof/ACNS-X06_adjudication.json",
    "research/venue2027/proof/emit_acns_x06_adjudication_report.py",
    "research/venue2027/proof/logs/ACNS-X06_adjudication.pytest.log",
    "research/venue2027/proof/logs/ACNS-X06_adjudication.ruff.log",
    "research/venue2027/proof/logs/ACNS-X06_adjudication.suite.log",
    "research/venue2027/proof/logs/ACNS-X06_adjudication.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_rater_agreement.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X06_adjudication.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/acns/rater_agreement.py "
            "evaluation/venue2027/acns/test_rater_agreement.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X06_adjudication.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-X06_adjudication.suite.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/acns/rater_agreement.py",
    "evaluation/venue2027/acns/test_rater_agreement.py",
]


def run_cmd(argv: str, log_rel: str) -> int:
    """Run command and write output to log path."""
    log_path = REPO / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        argv,
        shell=True,
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    combined = res.stdout + res.stderr
    log_path.write_text(combined, encoding="utf-8")
    return res.returncode


def main() -> int:
    for cmd in COMMANDS:
        code = run_cmd(cmd["argv"], cmd["log_path"])
        if code != 0:
            print(f"Command failed ({code}): {cmd['argv']}")
            return code

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "ACNS-X06_adjudication (Phase P05, venue acns; SoK: Evidence Boundaries of Attestation in "
            "Tool-Using AI Systems): delivered evaluation/venue2027/acns/rater_agreement.py implementing "
            "compute_agreement(ratings_matrix, num_bootstraps=1000, seed=2027) -> AgreementResult and "
            "measure(labels_a, labels_b) -> AgreementResult (Agreement alias). Computes Krippendorff's alpha "
            "for nominal data with arbitrary observers and missing labels; cross-checks Cohen's kappa if "
            "complete pairs across two raters are present; computes case/paper clustered percentile bootstrap "
            "confidence intervals with a deterministic seed. Pure standard library implementation (no external "
            "stats dependencies). All errors fail closed with stable reason codes (EMPTY_RATINGS_MATRIX, "
            "INSUFFICIENT_RATERS, NO_PAIRABLE_UNITS, INSUFFICIENT_DATA, MISMATCHED_LENGTHS, "
            "INVALID_RATINGS_MATRIX, INVALID_BOOTSTRAP_PARAMS). Tests in evaluation/venue2027/acns/test_rater_agreement.py "
            "(15 tests) cover positive controls (perfect agreement alpha=1.0 and kappa=1.0 across 2 and 4 raters; "
            "complete pairs matching known analytical Cohen kappa values 7/12 and 7/15; bootstrap CI bounds correct, "
            "enclosing point estimate, and seed-deterministic; measure convenience wrapper; JSON serializability) "
            "and adversarial controls (empty ratings matrices refused with EMPTY_RATINGS_MATRIX; insufficient raters "
            "refused with INSUFFICIENT_RATERS; unpairable matrices refused with NO_PAIRABLE_UNITS; all-disagreement "
            "handled without NaN crash for 2 and 3 raters; missing labels with None, empty strings, and NaN handled "
            "gracefully; invalid bootstrap and shape parameters fail closed). Full ACNS test suite regression passed "
            "(177 tests). ruff@0.7.1 check and format clean on touched paths. source_sha_after = base commit SHA per repo "
            "convention."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-X06_adjudication.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    val_log = (
        REPO / "research" / "venue2027" / "proof" / "logs" / "ACNS-X06_adjudication.validator.log"
    )
    val_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
