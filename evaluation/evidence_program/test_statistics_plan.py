from pathlib import Path

from evaluation.evidence_program.validate_statistics_plan import validate


def test_statistics_plan_has_subject_cluster_and_claim_boundary() -> None:
    validate(Path("evaluation/evidence_program/statistics_plan.json"))
