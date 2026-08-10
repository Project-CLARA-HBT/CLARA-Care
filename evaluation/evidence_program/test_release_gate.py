import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.evidence_program.release_gate import validate


def test_release_gate_rejects_incomplete_attestation(tmp_path: Path) -> None:
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps({"status": "approved"}), encoding="utf-8")

    with pytest.raises(FreezeError, match="missing_headline_release_fields"):
        validate(path)


def test_release_gate_accepts_complete_approved_attestation(tmp_path: Path) -> None:
    path = tmp_path / "attestation.json"
    path.write_text(
        json.dumps(
            {
                "status": "approved",
                "release_id": "release-001",
                "run_id": "run-001",
                "code_revision": "a" * 40,
                "protocol_sha256": "b" * 64,
                "external_cohort_attested": True,
                "independent_adjudication_attested": True,
                "two_model_family_utility_attested": True,
                "real_boundary_adversarial_attested": True,
                "postgres_fullstack_attested": True,
                "approved_by": "independent-review-board",
                "approved_at": "2026-08-10T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    validate(path)
