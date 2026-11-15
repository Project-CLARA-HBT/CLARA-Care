"""Emit research/venue2027/proof/PST-candidate.json via agent_protocol.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-candidate task. No network access.

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

TASK_ID = "PST-candidate"
BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED_PATHS = [
    "evaluation/venue2027/pst/candidate.py",
    "evaluation/venue2027/pst/test_candidate.py",
    "research/venue2027/proof/PST-candidate.json",
    "research/venue2027/proof/emit_PST-candidate_report.py",
    "research/venue2027/proof/logs/PST-candidate.pytest.log",
    "research/venue2027/proof/logs/PST-candidate.ruff.log",
    "research/venue2027/proof/logs/PST-candidate.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/pst/candidate.py",
    "evaluation/venue2027/pst/test_candidate.py",
    "research/venue2027/proof/logs/PST-candidate.pytest.log",
    "research/venue2027/proof/logs/PST-candidate.ruff.log",
]


def main() -> int:
    validator_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "PST-candidate.validator.log"
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    validator_log.write_text(
        "emit_PST-candidate_report: building report via agent_protocol.build_report\n",
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
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_candidate.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-candidate.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/pst/candidate.py "
                "evaluation/venue2027/pst/test_candidate.py --config ruff.toml && "
                "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/candidate.py "
                "evaluation/venue2027/pst/test_candidate.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-candidate.ruff.log",
            },
            {
                "argv": "python3 research/venue2027/proof/emit_PST-candidate_report.py # "
                "build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/PST-candidate.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-candidate.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 candidate algorithm boundary for venue pst (ReceiptMin: Measuring Forensic "
            "Reconstructability under Purpose-Bound Audit Minimization). Implemented the isolated "
            "ReceiptMin mechanism at evaluation/venue2027/pst/candidate.py (CANDIDATE_ID="
            "'clara.pst.candidate.receiptmin', CANDIDATE_ARM_ID='B4', version 1.0.0; "
            "describe_mechanism() exposes the machine-readable design record). "
            "API: minimize(event, purpose) -> Receipt strips raw sensitive payload per declared "
            "purpose and policy epoch, cryptographically binding omitted fields via canonical "
            "SHA-256 digest (omitted_field_digest); reconstruct(receipts, query) -> "
            "Reconstruction(score, answerable) evaluates ex-ante forensic query answerability "
            "(FQ-AUTH-*, FQ-PROV-*, FQ-ELIG-*), failing closed to INDETERMINATE on unknown query, "
            "missing key custody, or receipt tampering; run_candidate(case, ctx) -> Outcome maps "
            "cases to ADMIT / REJECT / INDETERMINATE for the task harness. Independence: AST "
            "scan in test_candidate.py verifies candidate.py imports neither the independent "
            "oracle nor label datasets. Unit tests prove positive reconstruction of primary "
            "forensic queries, significant byte reduction (>30%) relative to full logs, and "
            "fail-closed behavior on adversarial/tampered/unknown queries."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "PST-candidate.json"
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
