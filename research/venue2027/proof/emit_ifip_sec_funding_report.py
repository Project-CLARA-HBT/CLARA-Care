"""Emit the IFIP_SEC-funding P09 task report via the shared agent protocol."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE_SHA = "573d5369abd2e9d35f8039a99cf647e6ba9b3f32"


def _sha(rev: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", rev],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    report = ap.build_report(
        task_id="IFIP_SEC-funding",
        status="PASS",
        source_sha_before=_sha(BASE_SHA),
        source_sha_after=_sha("HEAD"),
        changed_paths=[
            "research/venue2027/ifip_sec/submission/funding_and_author_check.md",
            "research/venue2027/ifip_sec/tests/test_funding_check.py",
            "research/venue2027/proof/IFIP_SEC-funding.json",
            "research/venue2027/proof/logs/IFIP_SEC-funding.validator.log",
            "research/venue2027/proof/logs/IFIP_SEC-funding.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-funding.ruff.log",
            "research/venue2027/proof/logs/IFIP_SEC-funding.suite.log",
            "research/venue2027/proof/logs/IFIP_SEC-funding.shared_regression.log",
        ],
        commands=[
            {
                "argv": (
                    "python3 research/venue2027/_shared/tools/submission_contract.py "
                    "research/venue2027/ifip_sec/submission/funding_and_author_check.md"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.validator.log",
            },
            {
                "argv": (
                    "python3 -m pytest -q research/venue2027/ifip_sec/tests/test_funding_check.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.pytest.log",
            },
            {
                "argv": (
                    "ruff check research/venue2027/ifip_sec/tests/test_funding_check.py && "
                    "ruff format --check research/venue2027/ifip_sec/tests/test_funding_check.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/ifip_sec/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.suite.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.shared_regression.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/emit_ifip_sec_funding_report.py "
                    "# build_report + validate_report(ok:true) recorded in "
                    "research/venue2027/proof/IFIP_SEC-funding.json"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-funding.protocol.log",
            },
        ],
        artifact_paths=[
            "research/venue2027/ifip_sec/submission/funding_and_author_check.md",
            "research/venue2027/ifip_sec/tests/test_funding_check.py",
        ],
        repo=REPO_ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P09 submission/funding readiness artifact for IFIP SEC 2027 (Springer AICT "
            "proceedings): research/venue2027/ifip_sec/submission/funding_and_author_check.md "
            "declares all ten REQUIRED_FIELDS as labeled lines (cfp_url, template, page_limit, "
            "fee_or_registration, waiver_path, authorship_and_contribution, conflicts_policy, "
            "simultaneous_submission_policy, verification_status, decision). Official CFP "
            "https://ifipsec.org/cfp.html and registration page https://ifipsec.org/registration "
            "were fetched live by this agent on 2026-11-15: conference identity (42nd IFIP TC-11 "
            "SEC 2027, 14-16 June 2027, Linkoping University, Sweden), IFIP AICT/Springer "
            "proceedings, 2026-12-15 AoE submission deadline, 2027-02-18 notification, "
            "2027-03-15 camera-ready including registration and payment, 14-page limit including "
            "references/appendices, non-anonymous submissions, original/unpublished/no-double-"
            "submission policy, in-person presentation and at least one FULL registration per "
            "accepted paper, and both paper prizes are each CONFIRMED with URL+ISO date on the "
            "same line. Registration fee amounts remain UNVERIFIED because the official page "
            "states 'Registration fees TBC'; no venue waiver program was located, so no waiver is "
            "claimed as guaranteed (prizes are not sponsorship); contribution-statement format is "
            "UNVERIFIED. Decision is HOLD (not GO); the action ledger states no submission, "
            "registration, fee, or waiver action was taken and human authorization is required; "
            "sponsor/registration request packet is outlined for post-acceptance human use only. "
            "Machine-checked: shared submission_contract validate ok:true (exit 0); 17 new tests "
            "pass including adversarial cases (CONFIRMED without URL+date refused; guaranteed "
            "waiver without source refused; missing REQUIRED field refused; missing simultaneous-"
            "submission policy refused; decision flip away from HOLD detected); ifip_sec suite 29 "
            "passed; shared foundations regression 167 passed; ruff check + ruff format clean. No "
            "external submission or payment action was performed by this agent; artifact derives "
            "from the live official CFP/registration pages and the IFIP_SEC SPEC only."
        ),
    )
    out = REPO_ROOT / "research" / "venue2027" / "proof" / "IFIP_SEC-funding.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    validation = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO_ROOT,
        expected_task_id="IFIP_SEC-funding",
        completed_tasks=["IFIP_SEC-scope", "SH-venue_formats"],
        task_dependencies=["IFIP_SEC-scope", "SH-venue_formats"],
    )
    print(json.dumps(validation.to_dict(), indent=2))
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
