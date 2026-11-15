"""Emit POPETS-X08_minimal_privacy task report and validate."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/minimal_disclosure.py",
    "evaluation/venue2027/popets/test_minimal_privacy.py",
    "research/venue2027/proof/POPETS-X08_minimal_privacy.json",
    "research/venue2027/proof/emit_popets_x08_minimal_privacy_report.py",
    "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.pytest.log",
    "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.ruff.log",
    "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/minimal_disclosure.py",
    "evaluation/venue2027/popets/test_minimal_privacy.py",
    "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.pytest.log",
    "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.ruff.log",
]


def main() -> int:
    # 1. Run pytest and capture real log
    pytest_cmd = "python3 -m pytest -q evaluation/venue2027/popets/test_minimal_privacy.py"
    res_pytest = subprocess.run(
        pytest_cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    pytest_log = REPO / "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.pytest.log"
    pytest_log.write_text(res_pytest.stdout + res_pytest.stderr, encoding="utf-8")
    assert res_pytest.returncode == 0, f"pytest failed with exit {res_pytest.returncode}"

    # 2. Run ruff and capture real log
    ruff_cmd = "uvx ruff@0.7.1 check evaluation/venue2027/popets/minimal_disclosure.py evaluation/venue2027/popets/test_minimal_privacy.py"
    res_ruff = subprocess.run(
        ruff_cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    ruff_log = REPO / "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.ruff.log"
    ruff_log.write_text(res_ruff.stdout + res_ruff.stderr, encoding="utf-8")
    assert res_ruff.returncode == 0, f"ruff failed with exit {res_ruff.returncode}"

    # 3. Build report
    report = ap.build_report(
        task_id="POPETS-X08_minimal_privacy",
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": pytest_cmd,
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.pytest.log",
            },
            {
                "argv": ruff_cmd,
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.ruff.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "POPETS-X08_minimal_privacy (Phase P04, RQ3): implemented minimal outbound disclosure control "
            "in evaluation/venue2027/popets/minimal_disclosure.py adhering to task dependency + active purpose "
            "rather than original full EHR summary. Restricts disclosed context to the minimal field set demanded "
            "by the task and authorized by purpose; reports withheld fields and payload. Fails closed on any "
            "unresolved or unknown graph edge (missing ancestor, unlinked derivation, cross-purpose edge) by falling "
            "back to RECOMPUTATION (recomputation_required=True, reason_code=REASON_RECOMPUTATION_REQUIRED). "
            "Actively refuses full EHR summary disclosure when a strictly minimal context set exists "
            "(reason_code=REASON_FULL_SUMMARY_DISCLOSURE_REFUSED). Implements exact target contract "
            "select_fields(context, task) -> FieldSet and minimal_disclosure(task_dependency, current_purpose, graph) -> Disclosure. "
            "9 unit tests in evaluation/venue2027/popets/test_minimal_privacy.py pass cleanly (positive controls for narrow task "
            "disclosure reduction, purpose change narrowing, lineage-backed resolution, select_fields contract; adversarial controls "
            "for unknown graph edge recomputation fallback, cross-purpose edge fallback, full summary refusal, malformed inputs)."
        ),
    )

    proof_file = REPO / "research/venue2027/proof/POPETS-X08_minimal_privacy.json"
    proof_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # 4. Validate report
    validation = ap.validate_report(
        report,
        repo=REPO,
        expected_task_id="POPETS-X08_minimal_privacy",
    )
    val_log = REPO / "research/venue2027/proof/logs/POPETS-X08_minimal_privacy.validator.log"
    val_log.write_text(json.dumps(validation.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=2))

    return 0 if validation.ok else 1


if __name__ == "__main__":
    sys.exit(main())
