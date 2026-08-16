from __future__ import annotations

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.validate_results import _validate_result_evidence


def _executed() -> dict[str, str]:
    return {
        "run_status": "EXECUTED",
        "observation_artifact_ref": "artifacts/govred/run/observation.json",
        "observation_artifact_sha256": "a" * 64,
        "boundary_path_attested": "true",
    }


def test_executed_row_requires_hashed_complete_boundary_evidence() -> None:
    _validate_result_evidence(_executed())
    row = _executed()
    row["boundary_path_attested"] = "false"
    with pytest.raises(FreezeError, match="govred_executed_result_boundary_path_incomplete"):
        _validate_result_evidence(row)


def test_not_run_row_cannot_claim_boundary_evidence() -> None:
    row = {
        "run_status": "NOT_RUN",
        "observation_artifact_ref": "",
        "observation_artifact_sha256": "",
        "boundary_path_attested": "false",
    }
    _validate_result_evidence(row)
    row["observation_artifact_ref"] = "artifacts/govred/run/observation.json"
    with pytest.raises(FreezeError, match="govred_not_run_must_not_claim_evidence"):
        _validate_result_evidence(row)
