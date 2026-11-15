"""Emit the ACNS-baselines proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-baselines task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-baselines"

CHANGED = [
    "evaluation/venue2027/acns/__init__.py",
    "evaluation/venue2027/acns/_smoke_fixtures.py",
    "evaluation/venue2027/acns/baselines.py",
    "evaluation/venue2027/acns/test_baselines.py",
    "research/venue2027/proof/ACNS-baselines.json",
    "research/venue2027/proof/logs/ACNS-baselines.pytest.log",
    "research/venue2027/proof/logs/ACNS-baselines.ruff.log",
    "research/venue2027/proof/logs/ACNS-baselines.suite.log",
    "research/venue2027/proof/logs/ACNS-baselines.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-baselines.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/acns/ && uvx ruff@0.7.1 format --check evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-baselines.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/_shared/ research/venue2027/acns/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-baselines.suite.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before="9b6be889db89c2228c6ea1ac599f0000d03c63a4",
        source_sha_after="9b6be889db89c2228c6ea1ac599f0000d03c63a4",
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:4],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P03 baseline fidelity adapters for ACNS (SoK: Evidence Boundaries of Attestation "
            "in Tool-Using AI Systems): run_baseline(baseline_id,case,ctx)->Outcome over the "
            "four EVIDENCE-BOUNDARY reference classes B0-attestation-only, "
            "B1-receipt-without-binding, B2-timestamp-only, B3-evidence-boundary-aware. "
            "SoK framing honored (novelty_contract section 1): the baselines are analytic "
            "classifiers over synthetic evidence-claim records (synthetic-acns-2027, "
            "_smoke_fixtures.py literals; no PHI/PII, no network, no clock, no provider), "
            "not systems, and each returns a structured EvidenceBoundaryVerdict (granted "
            "lattice level L0-L4, ACCEPT/REJECT, reason code, per-claim gap codes from the "
            "pre-registered register G1-G9 of the threat model). Executed witnesses "
            "(adversarial tests): B0 fails to detect the receipt-quoted-as-execution "
            "downgrade (G2) and accepts an unbound claim; B1 accepts a receipt bound to a "
            "different claim (G4 transplant); B2 accepts an unbound claim on timestamp "
            "freshness alone (G6) and the downgrade; B3 detects all three and grants a "
            "capped level. Constant-allow stub refused (UNKNOWN_BASELINE on both "
            "baseline_id and forged ctx.arm_id); unknown record -> NOT_RUN_EXTERNAL "
            "(retriable, never counted as acceptance); malformed input -> MALFORMED_CASE "
            "fail-closed. Registry fidelity: pinned upstream arm ports "
            "(rats-rfc9334-framework FAITHFUL_PORT, w3c-prov-provenance-audit, "
            "agentdojo/toolemu extraction) do not exist in this worktree (registry rows "
            "honestly UNAVAILABLE_NOT_RUN at task start); per EXECUTION_CONTRACT rule 8 no "
            "toy was substituted under a registry name - the reference classes implement "
            "the task-manifest contract over synthetic fixtures, NOT_RUN_EXTERNAL is the "
            "transparent status when the declared upstream record cannot be located, and "
            "baseline_parity is NOT_APPLICABLE (no registry arm executed; no comparative "
            "claim made). Tests: 33 passed (positive: all 4 classes x all 4 records, "
            "structured JSON-serializable verdicts; adversarial: the stance-separation "
            "witnesses above; fail-closed controls). Shared foundations + acns suite "
            "regression: 105 passed. ruff@0.7.1 check + format clean on touched paths "
            "(repo-wide ruff has pre-existing unrelated findings in untouched services/ and "
            "tests/ files). source_sha_after = base SHA per established repo convention "
            "(proof report committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-baselines.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
