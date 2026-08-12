from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.external_validation.freeze_common_offset_glhs_result import (
    freeze,
    verify_freeze,
)
from evaluation.external_validation.run_common_offset_glhs import (
    PRODUCTION_PATH,
    PROTOCOL_SCHEMA_VERSION,
    PROTOCOL_STATUS,
    SYSTEMS,
    TEMPORAL_MAPPING,
    run,
)
from evaluation.external_validation.validate_common_offset_glhs import validate


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object], hash_field: str) -> None:
    unsigned = dict(payload)
    unsigned[hash_field] = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    path.write_text(json.dumps(unsigned, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _event(identifier: str, *, source_index: int, offset: int) -> dict[str, object]:
    return {
        "event_id": identifier * 24,
        "source_index": source_index,
        "valid_offset_minutes": offset,
        "value_fingerprint": identifier * 64,
        "source_pointer_sha256": identifier * 64,
    }


def _frozen_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    tasks = tmp_path / "tasks.jsonl"
    rows = [
        {
            "task_id": "a" * 24,
            "subject_token": "1" * 32,
            "encounter_token": "2" * 32,
            "domain": "medications",
            "slot_fingerprint": "3" * 24,
            "structured_events": [
                _event("b", source_index=2, offset=10),
                _event("c", source_index=1, offset=20),
            ],
            "source_target_event_id": "c" * 24,
            "ground_truth_kind": "source_offset_derived_not_clinician_adjudicated",
            "knowledge_time_status": "UNAVAILABLE_NOT_ESTIMATED",
        },
        {
            "task_id": "d" * 24,
            "subject_token": "1" * 32,
            "encounter_token": "2" * 32,
            "domain": "observations",
            "slot_fingerprint": "4" * 24,
            "structured_events": [
                _event("e", source_index=8, offset=-30),
                _event("f", source_index=7, offset=0),
            ],
            "source_target_event_id": "f" * 24,
            "ground_truth_kind": "source_offset_derived_not_clinician_adjudicated",
            "knowledge_time_status": "UNAVAILABLE_NOT_ESTIMATED",
        },
    ]
    tasks.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    cohort = tmp_path / "cohort.json"
    _write_json(
        cohort,
        {
            "schema_version": "clara-common-offset-source-tasks.v1",
            "status": "FROZEN_DEVELOPER_PREPARED_SOURCE_DERIVED",
            "tasks_sha256": _sha(tasks),
            "task_count": 2,
            "event_count": 4,
            "represented_evaluation_subject_count": 1,
            "clinical_oracle": False,
            "headline_eligible": False,
        },
        "manifest_payload_sha256",
    )
    protocol = tmp_path / "protocol.json"
    runner = Path(__file__).with_name("run_common_offset_glhs.py")
    validator = Path(__file__).with_name("validate_common_offset_glhs.py")
    _write_json(
        protocol,
        {
            "schema_version": PROTOCOL_SCHEMA_VERSION,
            "status": PROTOCOL_STATUS,
            "freeze_id": "fixture-common-offset-glhs-v1",
            "dataset_id": "eicu_crd_demo_2_0_1",
            "systems": list(SYSTEMS),
            "primary_invariant": (
                "production_glhs_reconstruction_exact_parity_with_unique_latest_valid_offset"
            ),
            "tasks_sha256": _sha(tasks),
            "cohort_manifest_sha256": _sha(cohort),
            "cohort_manifest_payload_sha256": json.loads(
                cohort.read_text(encoding="utf-8")
            )["manifest_payload_sha256"],
            "runner_sha256": _sha(runner),
            "validator_sha256": _sha(validator),
            "implementation_git_sha": "0" * 40,
            "frozen_task_count": 2,
            "frozen_event_count": 4,
            "frozen_subject_count": 1,
            "analysis_unit": "source_subject",
            "failure_policy": "missing_invalid_or_error_is_failure",
            "production_path": PRODUCTION_PATH,
            "execution_boundary": "in_process_api_owned_service_layer_sqlite",
            "temporal_mapping": TEMPORAL_MAPPING,
            "clinical_oracle": False,
            "headline_eligible": False,
            "provider_calls_planned": 0,
        },
        "protocol_payload_sha256",
    )
    return tasks, cohort, protocol


def test_common_offset_runner_uses_production_glhs_and_preserves_claim_boundary(
    tmp_path: Path,
) -> None:
    tasks, cohort, protocol = _frozen_inputs(tmp_path)
    output = tmp_path / "run"

    result = run(
        tasks,
        cohort,
        protocol,
        output,
        enforce_repository_freeze=False,
    )
    validation = validate(output, tasks, cohort, protocol)

    assert result["status"] == "PASS"
    assert result["primary_result"] == {
        "correct": 2,
        "total": 2,
        "missing": 0,
        "pass": True,
    }
    assert result["system_results"][SYSTEMS[1]]["correct"] == 0
    assert result["row_counts"] == {
        "evidence": 4,
        "assertions": 4,
        "transitions": 4,
        "state_versions": 4,
    }
    assert result["relative_time_encoding"]["absolute_clinical_time"] == (
        "UNAVAILABLE_NOT_ESTIMATED"
    )
    assert result["clinical_oracle"] is False
    assert result["provider_calls"] == 0
    assert validation["production_glhs_correct"] == 2
    assert not (output / "scratch.sqlite3").exists()


def test_common_offset_validator_rejects_tampered_artifact(tmp_path: Path) -> None:
    tasks, cohort, protocol = _frozen_inputs(tmp_path)
    output = tmp_path / "run"
    run(tasks, cohort, protocol, output, enforce_repository_freeze=False)
    (output / "report.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum_mismatch"):
        validate(output, tasks, cohort, protocol)


def test_common_offset_runner_rejects_unbound_implementation(tmp_path: Path) -> None:
    tasks, cohort, protocol = _frozen_inputs(tmp_path)
    payload = json.loads(protocol.read_text(encoding="utf-8"))
    payload["runner_sha256"] = "0" * 64
    payload.pop("protocol_payload_sha256")
    _write_json(protocol, payload, "protocol_payload_sha256")

    with pytest.raises(ValueError, match="protocol_runner_mismatch"):
        run(
            tasks,
            cohort,
            protocol,
            tmp_path / "run",
            enforce_repository_freeze=False,
        )


def test_common_offset_result_freeze_is_sanitized_and_revalidates(tmp_path: Path) -> None:
    tasks, cohort, protocol = _frozen_inputs(tmp_path)
    output = tmp_path / "run"
    destination = tmp_path / "result-freeze.json"
    run(tasks, cohort, protocol, output, enforce_repository_freeze=False)

    frozen = freeze(
        output,
        tasks,
        cohort,
        protocol,
        destination,
        enforce_repository_freeze=False,
    )
    verification = verify_freeze(destination)

    assert frozen["status"] == "FROZEN_VALID_SOURCE_DERIVED_EXECUTION"
    assert frozen["primary_result"]["correct"] == 2
    assert frozen["clinical_oracle"] is False
    assert "subject_token" not in destination.read_text(encoding="utf-8")
    assert verification["status"] == "VALID"


def test_common_offset_result_freeze_rejects_tampered_aggregate(tmp_path: Path) -> None:
    tasks, cohort, protocol = _frozen_inputs(tmp_path)
    output = tmp_path / "run"
    destination = tmp_path / "result-freeze.json"
    run(tasks, cohort, protocol, output, enforce_repository_freeze=False)
    freeze(
        output,
        tasks,
        cohort,
        protocol,
        destination,
        enforce_repository_freeze=False,
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["headline_eligible"] = True
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="payload_hash_mismatch"):
        verify_freeze(destination, verify_local_artifact=False)
