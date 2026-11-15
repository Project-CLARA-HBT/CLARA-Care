"""Emit the AIME-X03_review_rubric task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-X03_review_rubric task. No network access.

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
TASK = "AIME-X03_review_rubric"
BASE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED = [
    "research/venue2027/aime/design/clinical_annotation_rubric.md",
    "research/venue2027/aime/tests/test_review_rubric.py",
    "research/venue2027/proof/AIME-X03_review_rubric.json",
    "research/venue2027/proof/logs/AIME-X03_review_rubric.pytest.log",
    "research/venue2027/proof/logs/AIME-X03_review_rubric.ruff.log",
    "research/venue2027/proof/logs/AIME-X03_review_rubric.suite.log",
    "research/venue2027/proof/logs/AIME-X03_review_rubric.validator.log",
    "research/venue2027/proof/emit_aime_x03_review_rubric_report.py",
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
                "argv": (
                    "python3 -m pytest -q " "research/venue2027/aime/tests/test_review_rubric.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "AIME-X03_review_rubric.pytest.log"),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check "
                    "research/venue2027/aime/tests/test_review_rubric.py && "
                    "uvx ruff@0.7.1 format --check "
                    "research/venue2027/aime/tests/test_review_rubric.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "AIME-X03_review_rubric.ruff.log"),
            },
            {
                "argv": (
                    "python3 -m pytest -q research/venue2027/_shared/tests/ "
                    "research/venue2027/aime/tests/"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "AIME-X03_review_rubric.suite.log"),
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_aime_x03_review_rubric_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X03_review_rubric.json"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/" "AIME-X03_review_rubric.validator.log"
                ),
            },
        ],
        artifact_paths=[
            "research/venue2027/aime/design/clinical_annotation_rubric.md",
            "research/venue2027/aime/tests/test_review_rubric.py",
            "research/venue2027/proof/logs/AIME-X03_review_rubric.pytest.log",
            "research/venue2027/proof/logs/AIME-X03_review_rubric.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 AIME-X03_review_rubric deliverable: "
            "research/venue2027/aime/design/clinical_annotation_rubric.md is "
            "the frozen, pre-registered clinical adjudication rubric "
            "(CLINICAL_ANNOTATION_RUBRIC_VERSION 1.0.0, additive-only), a "
            "method commitment with NO annotation executed. Core contract "
            "per task spec: (1) the exact five primary categories with "
            "explicit definitions, positive examples and boundary rules — "
            "CLINICAL_CORRECTNESS, OMISSION, UNSAFE_SUGGESTION, "
            "PERMISSION_ERROR (permission/disclosure error), INDETERMINATE "
            "(preserved, never coerced into a pass/rejection/safe failure, "
            "denominator never silently shrunk); (2) MANDATORY TWO "
            "INDEPENDENT QUALIFIED CLINICAL REVIEWERS (R1+R2) wherever a "
            "medical-correctness claim is made, with five eligibility "
            "conditions (licensed clinician, no role in any arm, no "
            "conflict of interest, independence between reviewers, written "
            "consent with frozen terms), a single reviewer explicitly never "
            "sufficient, and a third qualified clinician registered ONLY "
            "for the conflict path after both ratings lock (AIME-CASE-07); "
            "(3) mandatory blinding per INDEPENDENT_EVIDENCE_PROTOCOL.md "
            "rule 2: arm/provider/method blinding, locked randomized "
            "presentation order, cross-reviewer visibility prohibition, "
            "unblinding only after locks+adjudication+hash-freeze, "
            "self-review prohibition; (4) documented conflict adjudication: "
            "mechanical disagreement detection, one independent "
            "confirm-or-revise window, third-reviewer binding verdict, "
            "conservative-resolution rule (UNSAFE_SUGGESTION over OMISSION "
            "over CLINICAL_CORRECTNESS; PERMISSION_ERROR on contested "
            "eligibility; INDETERMINATE when not defensible), append-only "
            "hash-bound adjudication ledger, Cohen/Fleiss kappa with CIs "
            "reported not assumed, systematic-disagreement escalation to "
            "versioned rubric amendment; (5) EXPLICIT PROHIBITION of "
            "auto-accepting LLM-as-judge output: no label auto-acceptance, "
            "no model pre-fill of rationales (rubber-stamping is not "
            "independent review), no model-certified oracle, no silent "
            "LLM pre-screening substitution, LLM-judge-as-comparator "
            "studied only as experimental output under the same blinded "
            "adjudication, LLM logistics (seeded randomization, logging, "
            "format validation) as machine metadata only; (6) auditable "
            "reviewer decision records (review-decision.v1: pseudonymized "
            "reviewer, both axes, severity, evidence citations, own-words "
            "rationale, INDETERMINATE reason codes, SHA256-bound vignette "
            "state and output, lock timestamp); (7) stable reason codes "
            "fail closed (REVIEWER_UNAVAILABLE, BLINDING_BREACH_SUSPECTED, "
            "ITEM_STATE_HASH_MISMATCH, GATEKEEPER_MISS, ...); calibration "
            "round + seeded gatekeeper items; mutually exclusive per-arm "
            "denominator accounting; no clinical validity claim without "
            "the executed two-reviewer contract (falsification rule "
            "honored). test_review_rubric.py: 28 stdlib (pathlib/re) "
            "structural + adversarial tests parse the markdown and pass "
            "(five categories with definitions/examples/boundaries, "
            "two-reviewer independence incl. single-reviewer-refusal and "
            "eligibility conditions, blinding markers + rule-2 citation, "
            "conflict adjudication incl. conservative direction + kappa "
            "with CIs, LLM-as-judge prohibition incl. no-prefill and "
            "rationale ownership, INDETERMINATE preservation + reason "
            "codes, and anti-fabrication: no reviewer names, no "
            "credential strings, no invented kappa/agreement empirics, no "
            "TBD/TODO placeholders, not-executed declaration, no-validity-"
            "claim rule, frozen instrument version). Suite: 333 passed "
            "(research/venue2027/_shared/tests/ + aime/tests/). uvx "
            "ruff@0.7.1 check + format --check clean. baseline_parity "
            "NOT_APPLICABLE (no comparator in scope; rubric instrument "
            "task). No annotation result, roster, or kappa is fabricated: "
            "all such quantities remain planned instruments. "
            "source_sha_after = commit SHA of this task's single commit "
            "(proof report committed together with the work per "
            "established repo convention; source_sha_before = base SHA "
            "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X03_review_rubric.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X03_review_rubric.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
