"""Emit the AIME-funding proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the AIME-funding task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-funding"

CHANGED = [
    "research/venue2027/aime/submission/funding_and_author_check.md",
    "research/venue2027/aime/tests/test_funding_check.py",
    "research/venue2027/proof/AIME-funding.json",
    "research/venue2027/proof/logs/AIME-funding.validator.log",
    "research/venue2027/proof/logs/AIME-funding.pytest.log",
    "research/venue2027/proof/logs/AIME-funding.ruff.log",
    "research/venue2027/proof/logs/AIME-funding.suite.log",
    "research/venue2027/proof/logs/AIME-funding.shared_regression.log",
    "research/venue2027/proof/logs/AIME-funding.protocol.log",
]

COMMANDS = [
    {
        "argv": "python3 research/venue2027/_shared/tools/submission_contract.py "
        "research/venue2027/aime/submission/funding_and_author_check.md",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-funding.validator.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/test_funding_check.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-funding.pytest.log",
    },
    {
        "argv": "ruff check research/venue2027/aime/ && ruff format --check "
        "research/venue2027/aime/tests/test_funding_check.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-funding.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-funding.suite.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-funding.shared_regression.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before="573d5369abd2e9d35f8039a99cf647e6ba9b3f32",
        source_sha_after="573d5369abd2e9d35f8039a99cf647e6ba9b3f32",
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:2],
        repo=REPO,
        unresolved=[],
        notes=(
            "P09 submission/funding readiness artifact for AIME 2027 (Springer LNCS/LNAI, "
            "Artificial Intelligence in Medicine): "
            "research/venue2027/aime/submission/funding_and_author_check.md declares all ten "
            "REQUIRED_FIELDS as labeled lines (cfp_url, template, page_limit, fee_or_registration, "
            "waiver_path, authorship_and_contribution, conflicts_policy, "
            "simultaneous_submission_policy, verification_status, decision). Every external "
            "CFP/deadline/fee/waiver fact is UNVERIFIED (live CFP not fetched; re-verify at "
            "submission); the Springer proceedings-series attribution is itself a candidate "
            "classification. decision is HOLD (not GO) because verification is pending; no waiver "
            "is claimed as guaranteed; the action ledger states no submission, registration, fee, "
            "or waiver action was taken and human authorization is required. States the P09 "
            "double-submission refusal policy and an explicit ethics boundary: the study is "
            "synthetic-only (synthetic-aime-2027), and any human-involved extension requires "
            "independent ethics review (IRB/REC or equivalent) before that work begins. Includes "
            "a sponsor/registration request packet outline (post-acceptance only). "
            "Machine-checked: shared submission_contract validate ok:true (exit 0); 16 new tests "
            "pass including adversarial cases (CONFIRMED without URL+date refused; guaranteed "
            "waiver without source refused; missing REQUIRED field refused; missing "
            "simultaneous-submission policy refused; CONFIRMED deadline without citation "
            "refused); AIME suite 65 passed; shared foundations regression 167 passed; ruff "
            "check+format clean. No external submission or payment action was performed by this "
            "agent; artifact derives from the AIME SPEC and SH-venue_formats checklist only. "
            "source_sha_after = base SHA per established repo convention (proof report committed "
            "together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-funding.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
