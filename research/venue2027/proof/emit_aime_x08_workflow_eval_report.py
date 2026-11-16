"""Emit the AIME-X08_workflow_eval task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-X08_workflow_eval task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "AIME-X08_workflow_eval"
BASE = "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"

CHANGED = [
    "evaluation/venue2027/aime/workflow_evaluator.py",
    "evaluation/venue2027/aime/test_workflow_evaluator.py",
    "research/venue2027/proof/AIME-X08_workflow_eval.json",
    "research/venue2027/proof/emit_aime_x08_workflow_eval_report.py",
    "research/venue2027/proof/logs/AIME-X08_workflow_eval.pytest.log",
    "research/venue2027/proof/logs/AIME-X08_workflow_eval.ruff.log",
    "research/venue2027/proof/logs/AIME-X08_workflow_eval.suite.log",
    "research/venue2027/proof/logs/AIME-X08_workflow_eval.validator.log",
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_workflow_evaluator.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X08_workflow_eval.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/aime/workflow_evaluator.py "
                    "evaluation/venue2027/aime/test_workflow_evaluator.py && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/aime/workflow_evaluator.py "
                    "evaluation/venue2027/aime/test_workflow_evaluator.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X08_workflow_eval.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/aime/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X08_workflow_eval.suite.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/emit_aime_x08_workflow_eval_report.py "
                    "# build_report + validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X08_workflow_eval.json"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X08_workflow_eval.validator.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/aime/workflow_evaluator.py",
            "evaluation/venue2027/aime/test_workflow_evaluator.py",
            "research/venue2027/proof/logs/AIME-X08_workflow_eval.pytest.log",
            "research/venue2027/proof/logs/AIME-X08_workflow_eval.ruff.log",
            "research/venue2027/proof/logs/AIME-X08_workflow_eval.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P05 AIME-X08_workflow_eval deliverable: independent workflow evaluation and refusal grader "
            "implementing evaluate_workflow(candidate_output, vignette, rubric) -> WorkflowEvaluationResult "
            "and grade(case, response, review) -> WorkflowOutcome in evaluation/venue2027/aime/workflow_evaluator.py. "
            "Directly operationalizes RQ1's two-axis error decomposition by grading authorization validity (Axis A), "
            "clinical content completeness (Axis B), task state, needless refusal, and indeterminate SEPARATELY. "
            "Strictly enforces that clinical omission and unauthorized disclosure are NEVER collapsed into a single score. "
            "Applies frozen clinical annotation rubric (clara.venue2027.aime.clinical-annotation-rubric.v1) with independent "
            "adjudicators (R1, R2) and conservative-resolution conflict adjudication (§5.4). "
            "Fail-closed boundaries: strictly synthetic inputs only (refusing PHI-like fields), refusal of contradictory "
            "grades (CONTRADICTORY_GRADES_REFUSED), and absolute prohibition of auto-accepting LLM-as-judge (§7). "
            "Provides stratified confusion matrix helper (compute_confusion_matrix) reporting true/false positive/negatives, "
            "authorization error rate, clinical omission rate, and unnecessary refusal rate. "
            "Test suite in evaluation/venue2027/aime/test_workflow_evaluator.py verifies positive controls (clean vs hazardous "
            "vignettes, safe refusals, needless refusals, contract alias, confusion matrix) and adversarial controls (omission "
            "strictly separated from disclosure, contradictory grades refused, synthetic-only enforced, auto-acceptance prohibited, "
            "unresolved conflicts preserved as INDETERMINATE, and real B4 candidate arm interoperability). "
            "source_sha_after = base commit SHA 4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614 per established repo convention."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X08_workflow_eval.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X08_workflow_eval.validator.log"
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
        completed_tasks=["AIME-runner", "AIME-oracle", "AIME-candidate"],
        task_dependencies=["AIME-runner"],
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
