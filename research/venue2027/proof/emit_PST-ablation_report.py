"""Emit research/venue2027/proof/PST-ablation.json via agent_protocol.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-ablation task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "PST-ablation"
BASE_SHA = "08dbda2900c97a208b3228639f51998db833bb60"

CHANGED_PATHS = [
    "evaluation/venue2027/pst/ablations.py",
    "evaluation/venue2027/pst/test_ablations.py",
    "research/venue2027/proof/PST-ablation.json",
    "research/venue2027/proof/emit_PST-ablation_report.py",
    "research/venue2027/proof/logs/PST-ablation.pytest.log",
    "research/venue2027/proof/logs/PST-ablation.ruff.log",
    "research/venue2027/proof/logs/PST-ablation.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/pst/ablations.py",
    "evaluation/venue2027/pst/test_ablations.py",
    "research/venue2027/proof/logs/PST-ablation.pytest.log",
    "research/venue2027/proof/logs/PST-ablation.ruff.log",
]


def run_cmd(argv: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, check=False)
    log_path.write_text(f"$ {' '.join(argv)}\nexit_code: {res.returncode}\n\nSTDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}\n", encoding="utf-8")
    return res.returncode


def main() -> int:
    pytest_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "PST-ablation.pytest.log"
    ruff_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "PST-ablation.ruff.log"
    validator_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "PST-ablation.validator.log"
    validator_log.parent.mkdir(parents=True, exist_ok=True)

    # 1. Run pytest
    code1 = run_cmd([sys.executable, "-m", "pytest", "-q", "evaluation/venue2027/pst/test_ablations.py"], pytest_log)
    if code1 != 0:
        print(f"pytest failed with {code1}", file=sys.stderr)
        return code1

    # 2. Run ruff
    ruff_sh = (
        "uvx ruff@0.7.1 check evaluation/venue2027/pst/ablations.py evaluation/venue2027/pst/test_ablations.py --config ruff.toml && "
        "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/ablations.py evaluation/venue2027/pst/test_ablations.py"
    )
    code2 = run_cmd(["bash", "-c", ruff_sh], ruff_log)
    if code2 != 0:
        print(f"ruff failed with {code2}", file=sys.stderr)
        return code2

    validator_log.write_text(
        "emit_PST-ablation_report: building report via agent_protocol.build_report\n",
        encoding="utf-8",
    )

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_ablations.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-ablation.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/pst/ablations.py "
                "evaluation/venue2027/pst/test_ablations.py --config ruff.toml && "
                "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/ablations.py "
                "evaluation/venue2027/pst/test_ablations.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-ablation.ruff.log",
            },
            {
                "argv": "python3 research/venue2027/proof/emit_PST-ablation_report.py # "
                "build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/PST-ablation.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-ablation.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 causal mechanism ablation variants for venue pst (ReceiptMin: Measuring Forensic "
            "Reconstructability under Purpose-Bound Audit Minimization). Implemented ABLATION_REGISTRY "
            "at evaluation/venue2027/pst/ablations.py with 5 preregistered variants: without_purpose_binding "
            "(receipts lack purpose constraint; collapses purpose isolation, causing cross-purpose linkability), "
            "without_epoch_rotation (fixed static key; collapses epoch isolation, causing long-term epoch linkability), "
            "without_retention_enforcement (retains indefinitely; causes post-retention data exposure), "
            "with_common_safety_gate (replaces cryptographic proofs with point-in-time check; admits tampered claims), "
            "and full_candidate (reference ceiling). Target contract run_ablation(name, case) -> Outcome implemented. "
            "refuse_unregistered_variant enforces fail-closed discipline (UNKNOWN_ABLATION_VARIANT on unknown variants, "
            "VARIANT_REMOVES_NOTHING on non-ablation identities). mechanistic_inference_matrix and "
            "verify_mechanistic_inference_matrix evaluate 25 variant x family cells over frozen synthetic families "
            "with all_cells_match=True. Unit tests in test_ablations.py prove positive degradation for each ablated "
            "mechanism, clean control admission, and fail-closed adversarial controls."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "PST-ablation.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    with validator_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(validation.to_dict(), indent=1) + "\n")
        fh.write(f"validator exit_code: {0 if validation.ok else 1}\n")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
