"""Emit the DSN-funding P09 task report via the shared agent protocol."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _sha(rev: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", rev],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    report = ap.build_report(
        task_id="DSN-funding",
        status="PASS",
        source_sha_before=_sha("152c89116069072bcb82678702c7b0d70a0fccfb"),
        source_sha_after=_sha("HEAD"),
        changed_paths=[
            "research/venue2027/dsn/submission/funding_and_author_check.md",
            "research/venue2027/dsn/tests/test_funding_check.py",
            "research/venue2027/proof/DSN-funding.json",
            "research/venue2027/proof/logs/DSN-funding.validator.log",
            "research/venue2027/proof/logs/DSN-funding.pytest.log",
            "research/venue2027/proof/logs/DSN-funding.ruff.log",
            "research/venue2027/proof/logs/DSN-funding.suite.log",
            "research/venue2027/proof/logs/DSN-funding.shared_regression.log",
        ],
        commands=[
            {
                "argv": (
                    "python3 research/venue2027/_shared/tools/submission_contract.py "
                    "research/venue2027/dsn/submission/funding_and_author_check.md"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-funding.validator.log",
            },
            {
                "argv": (
                    "python3 -m pytest -q "
                    "research/venue2027/dsn/tests/test_funding_check.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-funding.pytest.log",
            },
            {
                "argv": "ruff check research/venue2027/dsn/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-funding.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/dsn/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-funding.suite.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-funding.shared_regression.log",
            },
        ],
        artifact_paths=[
            "research/venue2027/dsn/submission/funding_and_author_check.md",
            "research/venue2027/dsn/tests/test_funding_check.py",
        ],
        repo=REPO_ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P09 submission/funding readiness artifact for DSN 2027: "
            "research/venue2027/dsn/submission/funding_and_author_check.md declares all ten "
            "REQUIRED_FIELDS as labeled lines (cfp_url, template, page_limit, "
            "fee_or_registration, waiver_path, authorship_and_contribution, conflicts_policy, "
            "simultaneous_submission_policy, verification_status, decision). Every external "
            "CFP/fee/waiver fact is UNVERIFIED with reason 'live CFP not fetched; re-verify at "
            "submission'; decision is HOLD (not GO) because verification is pending; no waiver "
            "is claimed as guaranteed; the action ledger states no submission, registration, "
            "fee, or waiver action was taken and human authorization is required. Includes a "
            "sponsor/registration request packet outline (post-acceptance only). Machine-"
            "checked: shared submission_contract validate ok:true (exit 0); 13 new tests pass "
            "including adversarial cases (CONFIRMED without URL+date refused; guaranteed "
            "waiver without source refused; missing REQUIRED field refused; missing "
            "simultaneous-submission policy refused); DSN suite 38 passed; shared foundations "
            "regression 167 passed; ruff clean. No external submission or payment action was "
            "performed by this agent; artifact derives from the DSN SPEC and "
            "SH-venue_formats checklist only."
        ),
    )
    out = REPO_ROOT / "research" / "venue2027" / "proof" / "DSN-funding.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    validation = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO_ROOT,
        expected_task_id="DSN-funding",
        completed_tasks=["DSN-scope", "SH-venue_formats"],
        task_dependencies=["DSN-scope", "SH-venue_formats"],
    )
    print(json.dumps(validation.to_dict(), indent=2))
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
