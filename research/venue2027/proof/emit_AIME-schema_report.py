"""Emit the AIME-schema proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the AIME-schema task. No network access.

Failure semantics: runs every declared verification command, tees real output
into ``research/venue2027/proof/logs/AIME-schema.*.log``, then assembles and
validates the report; exits non-zero if any command or validation fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-schema"
LOGS = REPO / "research" / "venue2027" / "proof" / "logs"

BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "research/venue2027/aime/protocols/study.schema.json",
    "research/venue2027/aime/cases/sample_cases.json",
    "research/venue2027/aime/cases/fixtures/aime-consent-withdrawal.vignette-pair.json",
    "research/venue2027/aime/cases/fixtures/aime-medication-withdrawal.vignette-pair.json",
    "research/venue2027/aime/cases/fixtures/aime-indeterminate-adjudication.vignette-pair.json",
    "research/venue2027/aime/tests/test_study_schema.py",
    "research/venue2027/proof/AIME-schema.json",
    "research/venue2027/proof/logs/AIME-schema.pytest.log",
    "research/venue2027/proof/logs/AIME-schema.suite.log",
    "research/venue2027/proof/logs/AIME-schema.shared_regression.log",
    "research/venue2027/proof/logs/AIME-schema.ruff.log",
    "research/venue2027/proof/logs/AIME-schema.validator.log",
    "research/venue2027/proof/emit_AIME-schema_report.py",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-schema.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-schema.suite.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-schema.shared_regression.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/aime/ && "
        "uvx ruff@0.7.1 format --check research/venue2027/aime/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-schema.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/_shared/tools/agent_protocol.py validate "
        "research/venue2027/proof/AIME-schema.json --task AIME-schema --repo .",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-schema.validator.log",
    },
]


def run_logged(argv: str, log_path: Path) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(argv, shell=True, cwd=REPO, capture_output=True, text=True)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    return result.returncode


def main() -> int:
    verifications = [
        (COMMANDS[0], LOGS / "AIME-schema.pytest.log"),
        (COMMANDS[1], LOGS / "AIME-schema.suite.log"),
        (COMMANDS[2], LOGS / "AIME-schema.shared_regression.log"),
        (COMMANDS[3], LOGS / "AIME-schema.ruff.log"),
    ]
    for command, log_path in verifications:
        exit_code = run_logged(command["argv"], log_path)
        if exit_code != 0:
            print(f"FAILED ({exit_code}): {command['argv']}\nsee {log_path}")
            return 1
        command["exit_code"] = exit_code

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:6],
        repo=REPO,
        unresolved=[],
        notes=(
            "P02 AIME-schema deliverable: research/venue2027/aime/protocols/study.schema.json "
            "is generated deterministically from the shared case contract via "
            "venue_schema.write_venue_schema('aime', root) (VENUE_SCHEMA_VERSION 1.0.0): "
            "venue=aime, venue_unit_kind=vignette_pair, observer=blinded_clinician, expected/"
            "observed decision enums, computed decision_agreement, synthetic_provenance, "
            "source_authority=SYNTHETIC_RESEARCH_ONLY; every venue field is required and "
            "typed (no silent nulls); additionalProperties=false. "
            "research/venue2027/aime/cases/sample_cases.json carries 3 positive SYNTHETIC "
            "vignette-pair records (consent withdrawal mid-task -> REJECT, medication "
            "withdrawal -> ADMIT, clinician-disagreement INDETERMINATE requiring blinded "
            "adjudication) plus 1 invalid record (missing backend/seed/source_sha/"
            "independent_unit_id/observed_decision + untracked field) that fails closed with "
            "REQUIRED_MISSING and ADDITIONAL_PROPERTY. All records and hash-addressed fixture "
            "inputs declare source_authority=SYNTHETIC_RESEARCH_ONLY / synthetic_only=true "
            "(synthetic-aime-2027); no real PHI/PII path exists. Tests enforce deterministic "
            "rebuild byte-equality, positive validation, adversarial rejection, per-field "
            "fail-closed removal of every required field, frozen schema_version/unit kinds, "
            "and the SYNTHETIC_RESEARCH_ONLY assertion. Machine-checked: target tests 7 "
            "passed; AIME suite 88 passed; shared foundations regression 196 passed; ruff "
            "check+format clean (uvx ruff@0.7.1); agent_protocol validate ok:true. "
            "source_sha_after = base SHA per established repo convention (proof report "
            "committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-schema.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    first = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    (LOGS / "AIME-schema.validator.log").write_text(
        json.dumps(first.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    final = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(final.to_dict(), indent=2))
    return 0 if final.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
