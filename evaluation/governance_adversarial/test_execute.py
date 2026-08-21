from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.execute import _executed, execute
from evaluation.governance_adversarial.observation import BoundaryObservation


def _artifact(root: Path, name: str, content: bytes) -> tuple[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return name, hashlib.sha256(content).hexdigest()


def test_execution_requires_explicit_isolated_attestation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLARA_GOVRED_ISOLATED_RESEARCH", raising=False)
    with pytest.raises(
        FreezeError, match="govred_execution_requires_isolated_research_attestation"
    ):
        execute(
            manifest_path=Path("missing.json"),
            adapter_reference="missing:adapter",
            output_path=Path("result.csv"),
            artifact_root=Path("artifacts/govred/test"),
        )


def test_executed_row_requires_real_boundary_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    case = {
        "case_id": "case-1",
        "family": "cross_subject_retrieval",
        "oracle": {"sentinel_token": "S"},
    }
    observation = BoundaryObservation(
        status_code=403,
        response_body=b"denied",
        db_before_sha256="a" * 64,
        db_after_sha256="a" * 64,
        audit_reconstruction_complete=True,
        cache_index_revocation_failure=False,
        commit_occurred=False,
        latency_ms=1.0,
        availability_error=False,
    )
    implementation_ref, implementation_hash = _artifact(
        tmp_path, "arm-implementation.json", b'{"arm":"GLHS_STRICT"}\n'
    )
    observation_ref, observation_hash = _artifact(
        tmp_path, "observation.json", b'{"sanitized":true}\n'
    )
    value = {
        "isolated_attestation": True,
        "arm_name": "GLHS_STRICT",
        "arm_implementation_attestation": {
            "name": "GLHS_STRICT",
            "bind_snapshot": True,
            "revalidate_state": True,
            "revalidate_governance": True,
            "research_only": True,
            "runtime_mode": "isolated_research_only",
            "production_defaults_unchanged": True,
            "implementation_artifact_ref": implementation_ref,
            "implementation_artifact_sha256": implementation_hash,
            "implementation_revision": "d" * 40,
        },
        "observation": observation,
        "execution_id": "synthetic-execution",
        "normalized_outcome": "rejected",
        "boundary_path_attestation": {"http": True, "postgres": True, "cache": True, "audit": True},
        "observation_artifact_ref": observation_ref,
        "observation_artifact_sha256": observation_hash,
    }
    row = _executed(case, "GLHS_STRICT", value, artifact_root=tmp_path)
    assert row["boundary_path_attested"] == "true"
    value.pop("boundary_path_attestation")
    with pytest.raises(FreezeError, match="govred_adapter_boundary_path_attestation_invalid"):
        _executed(case, "GLHS_STRICT", value, artifact_root=tmp_path)


def test_executed_row_rejects_declared_arm_without_implementation_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    with pytest.raises(FreezeError, match="govred_adapter_arm_implementation_attestation_missing"):
        _executed(
            {
                "case_id": "case-1",
                "family": "cross_subject_retrieval",
                "oracle": {"sentinel_token": "S"},
            },
            "UNBOUND",
            {"isolated_attestation": True, "arm_name": "UNBOUND"},
            artifact_root=tmp_path,
        )


def test_executed_row_rejects_unverifiable_or_outside_artifact_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    case = {
        "case_id": "case-1",
        "family": "cross_subject_retrieval",
        "oracle": {"sentinel_token": "S"},
    }
    observation = BoundaryObservation(
        status_code=403,
        response_body=b"denied",
        db_before_sha256="a" * 64,
        db_after_sha256="a" * 64,
        audit_reconstruction_complete=True,
        cache_index_revocation_failure=False,
        commit_occurred=False,
        latency_ms=1.0,
        availability_error=False,
    )
    implementation_ref, implementation_hash = _artifact(tmp_path, "arm.json", b"arm")
    value = {
        "isolated_attestation": True,
        "arm_name": "GLHS_STRICT",
        "observation": observation,
        "execution_id": "synthetic-execution",
        "normalized_outcome": "rejected",
        "boundary_path_attestation": {"http": True, "postgres": True, "cache": True, "audit": True},
        "observation_artifact_ref": "../outside.json",
        "observation_artifact_sha256": "a" * 64,
        "arm_implementation_attestation": {
            "name": "GLHS_STRICT",
            "bind_snapshot": True,
            "revalidate_state": True,
            "revalidate_governance": True,
            "research_only": True,
            "runtime_mode": "isolated_research_only",
            "production_defaults_unchanged": True,
            "implementation_artifact_ref": implementation_ref,
            "implementation_artifact_sha256": implementation_hash,
            "implementation_revision": "d" * 40,
        },
    }
    with pytest.raises(FreezeError, match="govred_adapter_artifact_outside_root"):
        _executed(case, "GLHS_STRICT", value, artifact_root=tmp_path)

    observation_ref, _ = _artifact(tmp_path, "observation.json", b"sanitized")
    value["observation_artifact_ref"] = observation_ref
    value["observation_artifact_sha256"] = "b" * 64
    with pytest.raises(FreezeError, match="govred_adapter_artifact_hash_mismatch"):
        _executed(case, "GLHS_STRICT", value, artifact_root=tmp_path)
