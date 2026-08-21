"""Execute a frozen GovRed manifest through an operator-owned boundary adapter.

The adapter is responsible for the real HTTP/auth/cache/PostgreSQL/audit path.
This module enforces the frozen case/arm pairing and persists only the sanitized
classification contract consumed by ``validate_results.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import os
from pathlib import Path
from typing import Protocol

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json
from evaluation.governance_adversarial.observation import BoundaryObservation, classify
from evaluation.governance_adversarial.protocol import ARMS, validate_manifest
from evaluation.governance_adversarial.research_arms import isolated_arm_config

RESULT_COLUMNS = (
    "case_id",
    "family",
    "arm",
    "execution_id",
    "run_status",
    "retry_count",
    "observation_artifact_ref",
    "observation_artifact_sha256",
    "boundary_path_attested",
    "normalized_outcome",
    "unauthorized_disclosure",
    "successful_bypass",
    "stale_or_unauthorized_commit",
    "wrong_subject_exposure",
    "cache_index_revocation_failure",
    "audit_reconstruction_complete",
    "response_sha256",
    "latency_ms",
    "availability_error",
)


class BoundaryAdapter(Protocol):
    def __call__(self, *, case: dict[str, object], arm: dict[str, object]) -> dict[str, object]: ...


_REQUIRED_BOUNDARY_STAGES = frozenset({"http", "postgres", "cache", "audit"})


def _validate_artifact_binding(
    *, artifact_root: Path, artifact_ref: object, artifact_sha256: object
) -> tuple[str, str]:
    """Require a hash-bound, root-contained artifact instead of adapter self-report."""

    if not isinstance(artifact_ref, str) or not artifact_ref:
        raise FreezeError("govred_adapter_artifact_ref_missing")
    if (
        not isinstance(artifact_sha256, str)
        or len(artifact_sha256) != 64
        or any(character not in "0123456789abcdef" for character in artifact_sha256)
    ):
        raise FreezeError("govred_adapter_artifact_hash_invalid")
    root = artifact_root.resolve()
    candidate = (root / artifact_ref).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise FreezeError("govred_adapter_artifact_outside_root") from exc
    if not candidate.is_file():
        raise FreezeError("govred_adapter_artifact_missing")
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != artifact_sha256:
        raise FreezeError("govred_adapter_artifact_hash_mismatch")
    return artifact_ref, artifact_sha256


def _validate_boundary_evidence(
    value: dict[str, object], *, artifact_root: Path
) -> tuple[str, str]:
    """Require traceable observation evidence for every real-boundary result."""

    artifact_ref = value.get("observation_artifact_ref")
    artifact_sha256 = value.get("observation_artifact_sha256")
    stages = value.get("boundary_path_attestation")
    if not isinstance(stages, dict) or set(stages) != _REQUIRED_BOUNDARY_STAGES:
        raise FreezeError("govred_adapter_boundary_path_attestation_invalid")
    if any(stage is not True for stage in stages.values()):
        raise FreezeError("govred_adapter_boundary_path_incomplete")
    try:
        return _validate_artifact_binding(
            artifact_root=artifact_root,
            artifact_ref=artifact_ref,
            artifact_sha256=artifact_sha256,
        )
    except FreezeError as exc:
        if str(exc) == "govred_adapter_artifact_ref_missing":
            raise FreezeError("govred_adapter_observation_artifact_missing") from exc
        if str(exc) == "govred_adapter_artifact_hash_invalid":
            raise FreezeError("govred_adapter_observation_artifact_hash_invalid") from exc
        raise


def _validate_arm_implementation(
    arm_name: str, value: dict[str, object], *, artifact_root: Path
) -> None:
    """Require implementation evidence, not only a declared research-arm name."""

    expected = isolated_arm_config(arm_name)
    attestation = value.get("arm_implementation_attestation")
    if not isinstance(attestation, dict):
        raise FreezeError("govred_adapter_arm_implementation_attestation_missing")
    for key in (
        "name",
        "bind_snapshot",
        "revalidate_state",
        "revalidate_governance",
        "research_only",
    ):
        if attestation.get(key) != expected[key]:
            raise FreezeError("govred_adapter_arm_implementation_semantics_invalid")
    if attestation.get("runtime_mode") != "isolated_research_only":
        raise FreezeError("govred_adapter_arm_implementation_runtime_invalid")
    if attestation.get("production_defaults_unchanged") is not True:
        raise FreezeError("govred_adapter_arm_implementation_production_guard_missing")
    artifact_ref = attestation.get("implementation_artifact_ref")
    artifact_sha256 = attestation.get("implementation_artifact_sha256")
    revision = attestation.get("implementation_revision")
    try:
        _validate_artifact_binding(
            artifact_root=artifact_root,
            artifact_ref=artifact_ref,
            artifact_sha256=artifact_sha256,
        )
    except FreezeError as exc:
        if str(exc) == "govred_adapter_artifact_ref_missing":
            raise FreezeError("govred_adapter_arm_implementation_artifact_missing") from exc
        if str(exc) == "govred_adapter_artifact_hash_invalid":
            raise FreezeError("govred_adapter_arm_implementation_artifact_hash_invalid") from exc
        raise
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise FreezeError("govred_adapter_arm_implementation_revision_invalid")


def _load_adapter(reference: str) -> BoundaryAdapter:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise FreezeError("govred_adapter_reference_invalid")
    try:
        adapter = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise FreezeError("govred_adapter_unavailable") from exc
    if not callable(adapter):
        raise FreezeError("govred_adapter_not_callable")
    return adapter


def _not_run(case: dict[str, object], arm: str) -> dict[str, str]:
    return {
        "case_id": str(case["case_id"]),
        "family": str(case["family"]),
        "arm": arm,
        "execution_id": "",
        "run_status": "NOT_RUN",
        "retry_count": "0",
        "observation_artifact_ref": "",
        "observation_artifact_sha256": "",
        "boundary_path_attested": "false",
        "normalized_outcome": "",
        "unauthorized_disclosure": "",
        "successful_bypass": "",
        "stale_or_unauthorized_commit": "",
        "wrong_subject_exposure": "",
        "cache_index_revocation_failure": "",
        "audit_reconstruction_complete": "",
        "response_sha256": "",
        "latency_ms": "0",
        "availability_error": "",
    }


def _executed(
    case: dict[str, object], arm: str, value: dict[str, object], *, artifact_root: Path
) -> dict[str, str]:
    if value.get("isolated_attestation") is not True:
        raise FreezeError("govred_adapter_isolation_attestation_missing")
    if value.get("arm_name") != arm:
        raise FreezeError("govred_adapter_arm_attestation_invalid")
    _validate_arm_implementation(arm, value, artifact_root=artifact_root)
    observation = value.get("observation")
    if not isinstance(observation, BoundaryObservation):
        raise FreezeError("govred_adapter_observation_invalid")
    oracle = case["oracle"]
    assert isinstance(oracle, dict)
    classified = classify(
        observation=observation,
        sentinel_token=str(oracle["sentinel_token"]),
        expected_rejection=True,
    )
    execution_id = value.get("execution_id")
    retry_count = value.get("retry_count", 0)
    normalized_outcome = value.get("normalized_outcome")
    if (
        not isinstance(execution_id, str)
        or not execution_id
        or not isinstance(normalized_outcome, str)
        or not normalized_outcome
    ):
        raise FreezeError("govred_adapter_execution_metadata_invalid")
    if not isinstance(retry_count, int) or retry_count < 0:
        raise FreezeError("govred_adapter_retry_count_invalid")
    observation_ref, observation_sha256 = _validate_boundary_evidence(
        value, artifact_root=artifact_root
    )
    return {
        "case_id": str(case["case_id"]),
        "family": str(case["family"]),
        "arm": arm,
        "execution_id": execution_id,
        "run_status": "EXECUTED",
        "retry_count": str(retry_count),
        "observation_artifact_ref": observation_ref,
        "observation_artifact_sha256": observation_sha256,
        "boundary_path_attested": "true",
        "normalized_outcome": normalized_outcome,
        **{key: value for key, value in classified.items() if key in RESULT_COLUMNS},
    }


def execute(
    *, manifest_path: Path, adapter_reference: str, output_path: Path, artifact_root: Path
) -> None:
    if os.environ.get("CLARA_GOVRED_ISOLATED_RESEARCH") != "1":
        raise FreezeError("govred_execution_requires_isolated_research_attestation")
    manifest = validate_manifest(load_frozen_json(manifest_path), require_frozen=True)
    if manifest.get("partition") != "locked_test":
        raise FreezeError("govred_manifest_not_locked_test")
    adapter = _load_adapter(adapter_reference)
    rows: list[dict[str, str]] = []
    for case in manifest["cases"]:
        assert isinstance(case, dict)
        for arm_name in case["arm_applicability"]:
            if arm_name not in ARMS:
                raise FreezeError("govred_manifest_arm_invalid")
            arm = isolated_arm_config(str(arm_name))
            result = adapter(case=case, arm=arm)
            if result.get("run_status") == "NOT_RUN":
                rows.append(_not_run(case, str(arm_name)))
            else:
                rows.append(_executed(case, str(arm_name), result, artifact_root=artifact_root))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--adapter", required=True, help="module:function")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        execute(
            manifest_path=args.manifest,
            adapter_reference=args.adapter,
            output_path=args.output,
            artifact_root=args.artifact_root,
        )
    except FreezeError as exc:
        parser.error(str(exc))
