"""Fail-closed validation for classified GovRed boundary observations."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json
from evaluation.governance_adversarial.protocol import ARMS, FAMILIES, validate_manifest

# Compatibility name retained for callers that previously imported it.  These
# are now the complete RIVF family identifiers rather than a transport subset.
SCENARIOS = frozenset(FAMILIES)
COLUMNS = frozenset(
    {
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
    }
)
BOOLEAN_COLUMNS = COLUMNS.intersection(
    {
        "unauthorized_disclosure",
        "successful_bypass",
        "stale_or_unauthorized_commit",
        "wrong_subject_exposure",
        "cache_index_revocation_failure",
        "audit_reconstruction_complete",
        "availability_error",
        "boundary_path_attested",
    }
)


def _bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise FreezeError("govred_boolean_value_invalid")
    return value == "true"


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_result_evidence(row: dict[str, str]) -> None:
    """Validate evidence fields independent of frozen-manifest pairing."""

    if row["run_status"] == "EXECUTED":
        if not row["observation_artifact_ref"] or not _is_sha256(
            row["observation_artifact_sha256"]
        ):
            raise FreezeError("govred_executed_result_evidence_incomplete")
        if row["boundary_path_attested"] != "true":
            raise FreezeError("govred_executed_result_boundary_path_incomplete")
    elif (
        any(row[name] for name in ("observation_artifact_ref", "observation_artifact_sha256"))
        or row["boundary_path_attested"] != "false"
    ):
        raise FreezeError("govred_not_run_must_not_claim_evidence")


def validate(results: Path, manifest: Path) -> None:
    metadata = validate_manifest(load_frozen_json(manifest), require_frozen=True)
    if metadata.get("partition") != "locked_test":
        raise FreezeError("govred_manifest_not_locked_test")
    endpoint_sha = metadata.get("endpoint_manifest_sha256")
    if not isinstance(endpoint_sha, str) or len(endpoint_sha) != 64:
        raise FreezeError("govred_endpoint_manifest_hash_missing")
    if not metadata.get("environment_attestation"):
        raise FreezeError("govred_environment_attestation_missing")
    if not metadata.get("independent_curator_attestation"):
        raise FreezeError("govred_independent_curator_attestation_missing")
    with results.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("govred_result_schema_incomplete")
        rows = list(reader)
    cases = {case["case_id"]: case for case in metadata["cases"]}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        case_id, arm = row["case_id"], row["arm"]
        if case_id not in cases or row["family"] != cases[case_id]["family"]:
            raise FreezeError("govred_result_not_in_frozen_manifest")
        if arm not in ARMS or arm not in cases[case_id]["arm_applicability"]:
            raise FreezeError("govred_result_arm_not_applicable")
        if (case_id, arm) in seen:
            raise FreezeError("govred_duplicate_logical_case_arm")
        seen.add((case_id, arm))
        if row["run_status"] not in {"EXECUTED", "NOT_RUN"}:
            raise FreezeError("govred_result_run_status_invalid")
        try:
            retries = int(row["retry_count"])
            latency = float(row["latency_ms"])
        except ValueError as exc:
            raise FreezeError("govred_result_numeric_invalid") from exc
        if retries < 0 or latency < 0:
            raise FreezeError("govred_result_numeric_invalid")
        if row["run_status"] == "EXECUTED":
            if (
                not row["execution_id"]
                or not row["normalized_outcome"]
                or not _is_sha256(row["response_sha256"])
            ):
                raise FreezeError("govred_executed_result_observation_incomplete")
            for name in BOOLEAN_COLUMNS:
                _bool(row[name])
        elif any(row[name] for name in ("execution_id", "normalized_outcome", "response_sha256")):
            raise FreezeError("govred_not_run_must_not_claim_observation")
        _validate_result_evidence(row)
    expected = {
        (case_id, arm) for case_id, case in cases.items() for arm in case["arm_applicability"]
    }
    if seen != expected:
        raise FreezeError("govred_result_pairing_incomplete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.results, args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
