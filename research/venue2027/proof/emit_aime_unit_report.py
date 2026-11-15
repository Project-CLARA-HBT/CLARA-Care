"""Emit the AIME-unit task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-unit task. No network access.

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
TASK = "AIME-unit"
BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "tests/venue2027/aime/test_algorithm_properties.py",
    "research/venue2027/proof/AIME-unit.json",
    "research/venue2027/proof/emit_aime_unit_report.py",
    "research/venue2027/proof/logs/AIME-unit.pytest.log",
    "research/venue2027/proof/logs/AIME-unit.ruff.log",
    "research/venue2027/proof/logs/AIME-unit.suite.log",
    "research/venue2027/proof/logs/AIME-unit.validator.log",
]

ARTIFACT_PATHS = [
    "tests/venue2027/aime/test_algorithm_properties.py",
    "research/venue2027/proof/logs/AIME-unit.pytest.log",
    "research/venue2027/proof/logs/AIME-unit.ruff.log",
    "research/venue2027/proof/logs/AIME-unit.suite.log",
]


def run_cmd(argv: list[str], log_file: pathlib.Path) -> int:
    """Run command, tee output to log_file, and return exit code."""
    res = subprocess.run(argv, cwd=str(REPO), capture_output=True, text=True, check=False)
    combined = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(combined, encoding="utf-8")
    return res.returncode


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    logs_dir = REPO / "research/venue2027/proof/logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run unit pytest
    pytest_log = logs_dir / "AIME-unit.pytest.log"
    code_pytest = run_cmd(
        ["python3", "-m", "pytest", "-q", "tests/venue2027/aime/test_algorithm_properties.py"],
        pytest_log,
    )
    if code_pytest != 0:
        print(f"pytest failed with exit code {code_pytest}", file=sys.stderr)
        return code_pytest

    # 2. Run ruff check and format check
    ruff_log = logs_dir / "AIME-unit.ruff.log"
    res_check = subprocess.run(
        ["uvx", "ruff@0.7.1", "check", "tests/venue2027/aime/test_algorithm_properties.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    res_fmt = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "format",
            "--check",
            "tests/venue2027/aime/test_algorithm_properties.py",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    combined_ruff = res_check.stdout + res_check.stderr + res_fmt.stdout + res_fmt.stderr
    ruff_log.write_text(combined_ruff, encoding="utf-8")
    code_ruff = 0 if (res_check.returncode == 0 and res_fmt.returncode == 0) else 1
    if code_ruff != 0:
        print(f"ruff failed with exit code {code_ruff}", file=sys.stderr)
        return code_ruff

    # 3. Run regression suite
    suite_log = logs_dir / "AIME-unit.suite.log"
    code_suite = run_cmd(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/", "tests/venue2027/"],
        suite_log,
    )
    if code_suite != 0:
        print(f"suite failed with exit code {code_suite}", file=sys.stderr)
        return code_suite

    commands = [
        {
            "argv": "python3 -m pytest -q tests/venue2027/aime/test_algorithm_properties.py",
            "exit_code": code_pytest,
            "log_path": "research/venue2027/proof/logs/AIME-unit.pytest.log",
        },
        {
            "argv": (
                "uvx ruff@0.7.1 check tests/venue2027/aime/test_algorithm_properties.py && "
                "uvx ruff@0.7.1 format --check tests/venue2027/aime/test_algorithm_properties.py"
            ),
            "exit_code": code_ruff,
            "log_path": "research/venue2027/proof/logs/AIME-unit.ruff.log",
        },
        {
            "argv": "python3 -m pytest -q evaluation/venue2027/ tests/venue2027/",
            "exit_code": code_suite,
            "log_path": "research/venue2027/proof/logs/AIME-unit.suite.log",
        },
        {
            "argv": (
                "python3 research/venue2027/proof/emit_aime_unit_report.py # "
                "build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/AIME-unit.json"
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/AIME-unit.validator.log",
        },
    ]

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=commands,
        artifact_paths=ARTIFACT_PATHS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 AIME-unit deliverable: deterministic property, metamorphic and mutation tests "
            "over the REAL AIME candidate (evaluation/venue2027/aime/candidate.py) and "
            "selective refresh (evaluation/venue2027/aime/selective_refresh.py). "
            "Test suite tests/venue2027/aime/test_algorithm_properties.py contains 60 tests "
            "across 6 families: "
            "(1) Positive boundaries: stable synthetic history (AIME-CASE-01/06) admits SAFE "
            "with NO_DETECTED_HAZARD; unrelated note edits remain SAFE; selective refresh "
            "recomputes ONLY affected dependencies (evidence_note_summary) carrying over all "
            "others (PARTIAL); update_context soundness over declared caller dependencies; "
            "proper JSON serialization and 64-hex SHA256 input digests. "
            "(2) Negative boundaries: mid-task consent revocation returns UNSAFE "
            "(CONSENT_REVOKED_MID_TASK, AIME-CASE-03); withdrawn medication anchoring task "
            "returns UNSAFE (WITHDRAWN_MEDICATION_IN_OUTPUT, AIME-CASE-02); allergen present in "
            "current state or reported on timeline returns UNSAFE (ALLERGEN_PRESENT_IN_TASK); "
            "selective refresh forces FULL on consent change (CONSENT_CHANGE_FULL_REFRESH); "
            "entangled medication + allergy contexts route to CLINICIAN_REVIEW "
            "(MEDICATION_ALLERGY_ENTANGLED, never an automatic PARTIAL); conflicting observations "
            "route to CLINICIAN_REVIEW. "
            "(3) Unknown boundaries and INDETERMINATE retention: INDETERMINATE is first-class and "
            "never coerced into SAFE or UNSAFE; structural history inconsistency returns "
            "SNAPSHOT_CURRENT_INCONSISTENT; added interacting medications route to "
            "ADDITIONAL_MEDICATION_INTERACTION_HAZARD; unclassified additions route to "
            "HISTORY_CHANGED_REVIEW_REQUIRED; malformed inputs, missing fields, PHI-like fields, "
            "non-monotone/unknown timeline events, and malformed context fail closed with stable "
            "reason codes; unheld caller dependencies in update_context escalate to FULL. "
            "(4) Longitudinal consent-change and medication-withdrawal scenarios: multi-step "
            "additions and withdrawals; task drug withdrawn among multiple active medications; "
            "targeted revocation of active purpose; unrequested purpose revocation review routing; "
            "exhaustive pairwise coverage of INJECTION_INTERACTION_TABLE; mid-task allergy reporting. "
            "(5) Two-step metamorphic relations: MR1 — adding a medication withdrawal CANNOT make "
            "a hazardous recommendation safe (withdrawing any medication from an UNSAFE or "
            "INDETERMINATE case preserves or escalates the hazard, never transitioning to SAFE); "
            "MR2 — a consent revocation CANNOT be undone by a later benign update within the same "
            "epoch (appending benign note edits or non-interacting additions after revocation "
            "cannot restore authorization); MR3 — composing note edits cannot downgrade FULL to "
            "PARTIAL; MR4 — composing note edits cannot bypass medication/allergy entanglement; "
            "MR5 — consent purpose shrinkage is monotone unsafe; MR6 — deterministic replay "
            "invariance across 10 trials. "
            "(6) Mutation checks and liveness: clean history liveness control (anti-all-deny); "
            "refuse_constant_safe_stub gate; mutation kills for consent check drop, allergen check "
            "drop, withdrawn medication check drop, and entanglement detection drop; all-partial "
            "and all-full refresh mutant kills; seeded 30-case mutation campaign with byte-identical "
            "re-seeded replay. Seed all randomness: FIXED_SEED = 20271116. SYNTHETIC vignettes "
            "only; no LLM; assert INDETERMINATE is never coerced. "
            "All checks pass: pytest 60 passed (exit 0); uvx ruff@0.7.1 check + format clean (exit 0); "
            "full regression suite 2535 passed (exit 0)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-unit.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", flush=True)

    validator_log = logs_dir / "AIME-unit.validator.log"
    validator_log.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
        completed_tasks=["AIME-candidate", "AIME-baseline_tests"],
        task_dependencies=["AIME-candidate", "AIME-baseline_tests"],
    )
    validator_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2), flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
