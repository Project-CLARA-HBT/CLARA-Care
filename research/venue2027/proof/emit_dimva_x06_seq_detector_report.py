"""Emit the DIMVA-X06_seq_detector task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X06_seq_detector task. No network access.

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
BASE = "08dbda2900c97a208b3228639f51998db833bb60"

MODULE = "evaluation/venue2027/dimva/sequence_detector.py"
TESTS = "evaluation/venue2027/dimva/test_sequence_detector.py"
PROOF = "research/venue2027/proof/DIMVA-X06_seq_detector.json"
PYTEST_LOG = "research/venue2027/proof/logs/DIMVA-X06_seq_detector.pytest.log"
RUFF_LOG = "research/venue2027/proof/logs/DIMVA-X06_seq_detector.ruff.log"
VALIDATOR_LOG = "research/venue2027/proof/logs/DIMVA-X06_seq_detector.validator.log"

CHANGED = [
    MODULE,
    TESTS,
    PROOF,
    "research/venue2027/proof/emit_dimva_x06_seq_detector_report.py",
    PYTEST_LOG,
    RUFF_LOG,
    VALIDATOR_LOG,
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X06_seq_detector",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dimva/test_sequence_detector.py",
                "exit_code": 0,
                "log_path": PYTEST_LOG,
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dimva/sequence_detector.py "
                    "evaluation/venue2027/dimva/test_sequence_detector.py"
                ),
                "exit_code": 0,
                "log_path": RUFF_LOG,
            },
        ],
        artifact_paths=[MODULE, TESTS, PYTEST_LOG, RUFF_LOG],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P04 DIMVA-X06_seq_detector deliverable for venue dimva: "
            "evaluation/venue2027/dimva/sequence_detector.py implements a sequence-aware "
            "detector capturing order and transition dynamics over minimal leak-safe agent "
            "event sequences. Exact contracts: fit(train, dev) -> SequenceModel, "
            "score(stream) -> float, detect(events, threshold) -> Detection. "
            "Captures cross-tool transitions after denials, temporal pacing consistency, "
            "dispersion, and low-and-slow fixed-window evasion. Catches low-and-slow campaigns "
            "that per-window count thresholds (B0) and static rules (B1) miss, while strictly "
            "enforcing the RQ1 no-leakage contract (no label peeking, fail closed on reason "
            "codes or label keys). Score is strictly monotonic with campaign length. "
            "Adversarial checks confirm benign bursts, legitimate retries, and clean exploration "
            "do not false-positive at threshold. Pure deterministic stdlib math. "
            "AST scans verify zero imports of oracle or dataset generator modules."
        ),
    )

    out_path = REPO / PROOF
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X06_seq_detector",
    )
    log_path = REPO / VALIDATOR_LOG
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
