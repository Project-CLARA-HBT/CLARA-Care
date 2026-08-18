import hashlib
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.evidence_program.release_gate_v2 import (
    CLINICAL_HUMAN_VALIDATION_AVAILABLE,
    CLINICAL_HUMAN_VALIDATION_NOT_AVAILABLE,
    SCHEMA_VERSION,
    validate,
)


def _record(**overrides: object) -> dict:
    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "release_id": "release-v2-001",
        "run_id": "systems-nonclinical-001",
        "code_revision": "a" * 40,
        "protocol_sha256": "b" * 64,
        "clinical_human_validation_status": CLINICAL_HUMAN_VALIDATION_NOT_AVAILABLE,
        "dual_model_supportive_review_attested": True,
        "external_structural_validation_attested": True,
        "real_boundary_governance_attested": True,
        "postgres_concurrency_attested": True,
        "formal_assurance_attested": True,
        "approved_by": "independent-review-board",
        "approved_at": "2026-08-18T00:00:00Z",
    }
    record.update(overrides)
    return record


def _write(tmp_path: Path, record: dict) -> Path:
    path = tmp_path / "release-v2.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_v2_gate_accepts_nonclinical_release_with_human_validation_not_available(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, _record())
    validate(path, repository_root=tmp_path)


def test_v2_gate_refuses_to_mark_clinical_human_validation_available_without_evidence(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        _record(clinical_human_validation_status=CLINICAL_HUMAN_VALIDATION_AVAILABLE),
    )
    with pytest.raises(FreezeError, match="clinical_human_validation_evidence_missing"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_refuses_fabricated_available_with_missing_evidence_bytes(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        _record(
            clinical_human_validation_status=CLINICAL_HUMAN_VALIDATION_AVAILABLE,
            clinical_human_validation_evidence={
                "artifact_path": "no/such/evidence.json",
                "sha256": "0" * 64,
            },
        ),
    )
    with pytest.raises(FreezeError, match="clinical_human_validation_evidence_missing_bytes"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_refuses_available_with_sha_mismatch(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"human_review":"genuine"}', encoding="utf-8")
    path = _write(
        tmp_path,
        _record(
            clinical_human_validation_status=CLINICAL_HUMAN_VALIDATION_AVAILABLE,
            clinical_human_validation_evidence={
                "artifact_path": "evidence.json",
                "sha256": "0" * 64,
            },
        ),
    )
    with pytest.raises(FreezeError, match="clinical_human_validation_evidence_sha_mismatch"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_refuses_available_with_evidence_outside_repository(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        _record(
            clinical_human_validation_status=CLINICAL_HUMAN_VALIDATION_AVAILABLE,
            clinical_human_validation_evidence={
                "artifact_path": "../outside/evidence.json",
                "sha256": "0" * 64,
            },
        ),
    )
    with pytest.raises(
        FreezeError, match="clinical_human_validation_evidence_outside_repository"
    ):
        validate(path, repository_root=tmp_path)


def test_v2_gate_accepts_genuine_available_with_resolvable_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"human_review":"genuine"}', encoding="utf-8")
    declared = hashlib.sha256(evidence.read_bytes()).hexdigest()
    path = _write(
        tmp_path,
        _record(
            clinical_human_validation_status=CLINICAL_HUMAN_VALIDATION_AVAILABLE,
            clinical_human_validation_evidence={
                "artifact_path": "evidence.json",
                "sha256": declared,
            },
        ),
    )
    validate(path, repository_root=tmp_path)


def test_v2_gate_rejects_invalid_human_validation_status(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        _record(clinical_human_validation_status="AVAILABLE_BUT_UNVERIFIED"),
    )
    with pytest.raises(FreezeError, match="clinical_human_validation_invalid_status"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_rejects_missing_nonclinical_attestation(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        _record(real_boundary_governance_attested=False),
    )
    with pytest.raises(FreezeError, match="nonclinical_release_attestation_missing"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_rejects_wrong_schema_version(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        _record(schema_version="clara-release-schema.v1"),
    )
    with pytest.raises(FreezeError, match="release_schema_version_mismatch"):
        validate(path, repository_root=tmp_path)


def test_v2_gate_rejects_missing_required_fields(tmp_path: Path) -> None:
    path = _write(tmp_path, {"status": "approved"})
    with pytest.raises(FreezeError, match="missing_headline_release_fields"):
        validate(path, repository_root=tmp_path)
