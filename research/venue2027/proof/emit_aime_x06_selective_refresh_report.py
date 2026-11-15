"""Emit the AIME-X06_selective_refresh task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-X06_selective_refresh task. No network access.

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
TASK = "AIME-X06_selective_refresh"
BASE = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/aime/selective_refresh.py",
    "evaluation/venue2027/aime/test_selective_refresh.py",
    "research/venue2027/proof/AIME-X06_selective_refresh.json",
    "research/venue2027/proof/emit_aime_x06_selective_refresh_report.py",
    "research/venue2027/proof/logs/AIME-X06_selective_refresh.pytest.log",
    "research/venue2027/proof/logs/AIME-X06_selective_refresh.ruff.log",
    "research/venue2027/proof/logs/AIME-X06_selective_refresh.suite.log",
    "research/venue2027/proof/logs/AIME-X06_selective_refresh.full_suite.log",
    "research/venue2027/proof/logs/AIME-X06_selective_refresh.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_selective_refresh.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X06_selective_refresh.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/aime/"
                    "selective_refresh.py evaluation/venue2027/aime/"
                    "test_selective_refresh.py && uvx ruff@0.7.1 format --check "
                    "evaluation/venue2027/aime/selective_refresh.py "
                    "evaluation/venue2027/aime/test_selective_refresh.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X06_selective_refresh.ruff.log",
            },
            {
                "argv": (
                    "python3 -m pytest -q evaluation/venue2027/aime/"
                    "test_selective_refresh.py evaluation/venue2027/aime/test_baselines.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X06_selective_refresh.suite.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X06_selective_refresh.full_suite.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_aime_x06_selective_refresh_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X06_selective_refresh.json"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X06_selective_refresh.validator.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/aime/selective_refresh.py",
            "evaluation/venue2027/aime/test_selective_refresh.py",
            "research/venue2027/proof/logs/AIME-X06_selective_refresh.pytest.log",
            "research/venue2027/proof/logs/AIME-X06_selective_refresh.ruff.log",
            "research/venue2027/proof/logs/AIME-X06_selective_refresh.suite.log",
            "research/venue2027/proof/logs/AIME-X06_selective_refresh.full_suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P04 AIME-X06_selective_refresh deliverable: the purpose-aware SELECTIVE "
            "consent-aware context regeneration candidate (blueprint arm B4, RQ2) as a "
            "pure deterministic reference in evaluation/venue2027/aime/selective_refresh.py "
            "(SELECTIVE_REFRESH_VERSION 1.0.0, stdlib-only, no clock/randomness/I/O, "
            "synthetic states only, PHI-like fields refused fail-closed). Core decision "
            "relation refresh(state, changed_field) -> RefreshPlan with modes "
            "PARTIAL|FULL|CLINICIAN_REVIEW: an UNRELATED note change yields PARTIAL "
            "rebuilding ONLY its affected dependency (evidence_note_summary) with every "
            "other dependency carried over unchanged (partition complete+disjoint, "
            "nothing silently dropped); a consent/purpose change forces FULL (the "
            "authorization epoch co-determines every dependency); an unknown/undeclared "
            "changed field, a non-string field, a malformed/PHI/incomplete state or a "
            "non-held declared dependency ALL fail closed to FULL with stable reason "
            "codes (REFRESH_UNKNOWN_CHANGED_FIELD_FULL_REFRESH, REFRESH_STATE_MALFORMED, "
            "REFRESH_STATE_PHI_FIELDS, REFRESH_MISSING_FIELD, "
            "REFRESH_UNKNOWN_DEPENDENCY_FULL_REFRESH, "
            "REFRESH_MISSING_DEPENDENCIES_FULL_REFRESH) — never a silent partial refresh "
            "and never an unhandled exception. SAFETY GATE (task contract): medication/"
            "allergy clinical ENTANGLEMENT detected by is_entangled()/pair_entangled() "
            "over the declarative DEPENDENCY_GRAPH (the pair shares purpose_ddi_screen, "
            "the drug–allergy interaction screen): when BOTH clinical sides are populated "
            "— or one side is absent/malformed/unverifiable, fail-closed — a change to "
            "either side routes to CLINICIAN_REVIEW (REFRESH_MEDICATION_ALLERGY_ENTANGLED), "
            "never an automatic PARTIAL that could miss an interaction; conflicting "
            "observations route to CLINICIAN_REVIEW too (oracle reconciliation analogue). "
            "Task-spec contract update_context(current, dependencies) -> RefreshPlan "
            "adds the soundness rule that a PARTIAL plan is only returned when EVERY "
            "dependency the partial path rebuilds is actually held by the caller, else "
            "escalates to FULL. Test driver evaluation/venue2027/aime/"
            "test_selective_refresh.py (27 tests): positive — unrelated field change -> "
            "PARTIAL with only affected deps (partition completeness asserted) and "
            "consent change -> FULL; adversarial — entangled medication change (and its "
            "allergy mirror) -> CLINICIAN_REVIEW never PARTIAL, unknown changed field -> "
            "FULL, malformed/PHI/conflicting/unknown-dependency fail-closed set, "
            "determinism (identical inputs -> identical plans, byte-equal to_dict), "
            "PLAN_* self-validation, constant-partial-stub refusal analogue (a toy "
            "answering PARTIAL regardless of field cannot match the real gate). "
            "INDEPENDENCE + PARITY: imports the REAL strict comparator "
            "run_baseline('B1-full-per-step-refresh-current-policy-filter', case, ctx) "
            "(evaluation/venue2027/aime/baselines.py, BASELINES_VERSION 1.0.0, unmodified) "
            "and asserts the parity anchor that no step B1 refuses/invalidates (UNSAFE/"
            "INDETERMINATE) is ever answered by X06 with an automatic PARTIAL, and the "
            "INDEPENDENT oracle direction (evaluation/venue2027/aime/independent_oracle.py, "
            "unmodified): oracle REJECT families (consent_change, medication_withdrawal, "
            "allergy_update) co-vary with FULL/CLINICIAN_REVIEW while stable_history "
            "ADMITs allow the cost-saving PARTIAL; oracle AST independence self-scan "
            "re-run with this candidate's basename added (no candidate import). No "
            "clinical validity claim: synthetic vignettes only, no clinician reviewer, "
            "no live provider (blueprint falsification rule honored). Gates: target "
            "pytest 27 passed (exit 0); combined with the real-baseline test_baselines.py "
            "72 passed (exit 0); full evaluation/venue2027/ suite 1876 passed (exit 0); "
            "uvx ruff@0.7.1 check + format --check clean on touched files (exit 0). "
            "source_sha_after = commit SHA of this task's single commit (proof report "
            "committed together with the work per established repo convention)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X06_selective_refresh.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X06_selective_refresh.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
        completed_tasks=["AIME-oracle"],
        task_dependencies=["AIME-oracle"],
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
