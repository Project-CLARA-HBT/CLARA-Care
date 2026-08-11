from __future__ import annotations

import gzip
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from datasets.adapters.diabetes_130_tabular import MEDICATION_FIELDS, SUMMARY_FIELDS
from scripts.data import _registry
from scripts.data._registry import DatasetRegistryError, canonical_json, load_registry
from scripts.data.inspect import inspect_dataset
from scripts.data.list_sources import inventory
from scripts.data.normalize import normalize_dataset
from scripts.data.verify import verify_dataset
from scripts.data.verify_manifest import verify_frozen_manifest


def _entry(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "fixture_data",
        "display_name": "Fixture data",
        "provider": "test",
        "canonical_source": "https://example.invalid/data",
        "mirror_source": None,
        "download_method": "operator_manual",
        "download_url": None,
        "license": "test-only",
        "access_class": "open",
        "evidence_class": "test",
        "synthetic": True,
        "schema": "fixture",
        "version": "1",
        "release_date": None,
        "acquired_at": None,
        "raw_path": "datasets/raw/fixture_data",
        "normalized_path": "datasets/normalized/fixture_data",
        "local_candidates": ["fixture.zip"],
        "expected_files": ["fixture.zip"],
        "checksum_manifest": "datasets/manifests/fixture_data.json",
        "subject_identifier": "subject",
        "encounter_identifier": "encounter",
        "valid_time_fields": "valid_at",
        "knowledge_time_fields": "unknown",
        "provenance_fields": "source row",
        "clinical_domains": ["fixture"],
        "known_limitations": "test-only",
        "adapter": "fixture",
    }
    value.update(overrides)
    return value


def _registry_file(root: Path, entry: dict[str, object]) -> Path:
    path = root / "registry.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "clara-dataset-registry.v1",
                "raw_data_policy": "local_or_external_only",
                "datasets": [entry],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_repository_registry_is_valid_without_requiring_untracked_raw_data() -> None:
    registry = load_registry()
    assert len(registry["datasets"]) >= 8
    rows = {row["id"]: row for row in inventory()}
    syntheticmass_status = rows["syntheticmass_fhir_v1"]["local_status"]
    assert syntheticmass_status in {
        "PRESENT_UNVERIFIED",
        "NOT_AVAILABLE",
    }
    assert syntheticmass_status != "VERIFIED"
    assert rows["synthea_omop_2_8m"]["local_status"] == "NOT_AVAILABLE"


def test_registry_rejects_escaping_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    path = _registry_file(tmp_path, _entry(raw_path="../escape"))
    with pytest.raises(DatasetRegistryError, match="unsafe_raw_path"):
        load_registry(path)


def test_inspect_and_verify_hash_a_safe_local_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("record.json", json.dumps({"subject": "synthetic"}))
    registry_path = _registry_file(tmp_path, _entry())

    inspection = inspect_dataset("fixture_data", registry_path)
    assert inspection["status"] == "PRESENT_UNVERIFIED"
    verification = verify_dataset("fixture_data", registry_path)
    assert verification["status"] == "VERIFIED_LOCAL_INTEGRITY"
    assert verification["archive"]["member_count"] == 1
    assert verification["archive"]["unsafe_member_count"] == 0
    assert len(verification["files"][0]["sha256"]) == 64


def test_verify_accepts_expected_files_inside_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/expected.csv", "subject,value\n1,synthetic\n")
    registry_path = _registry_file(
        tmp_path,
        _entry(expected_files=["expected.csv"]),
    )

    verification = verify_dataset("fixture_data", registry_path)

    assert verification["expected_files_present"] is True


def test_verify_probes_archives_inside_registered_raw_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    raw_dir = tmp_path / "datasets" / "raw" / "fixture_data"
    raw_dir.mkdir(parents=True)
    archive_path = raw_dir / "download.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("expected.csv", "subject,value\n1,synthetic\n")
    registry_path = _registry_file(
        tmp_path,
        _entry(local_candidates=[], expected_files=["expected.csv"]),
    )

    verification = verify_dataset("fixture_data", registry_path)

    assert verification["expected_files_present"] is True
    assert verification["archive"]["archive_count"] == 1
    assert verification["archive"]["archives"][0]["format"] == "zip"


def test_missing_and_credentialed_sources_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    missing = _registry_file(tmp_path, _entry(local_candidates=[]))
    with pytest.raises(DatasetRegistryError, match="NOT_AVAILABLE"):
        inspect_dataset("fixture_data", missing)

    credentialed = _registry_file(
        tmp_path,
        _entry(access_class="credentialed", local_candidates=[]),
    )
    with pytest.raises(DatasetRegistryError, match="ACCESS_REQUIRED"):
        verify_dataset("fixture_data", credentialed)


def test_fhir_normalization_preserves_source_times_and_missing_knowledge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    resources = [
        {
            "resourceType": "Observation",
            "id": "obs-1",
            "status": "final",
            "subject": {"reference": "Patient/source-1"},
            "encounter": {"reference": "Encounter/enc-1"},
            "effectiveDateTime": "2026-01-02T03:04:05Z",
            "meta": {"lastUpdated": "2026-01-03T00:00:00Z"},
            "valueQuantity": {"value": 7.1, "unit": "mmol/L"},
        },
        {
            "resourceType": "Condition",
            "id": "condition-1",
            "subject": {"reference": "Patient/source-1"},
            "recordedDate": "2026-01-04",
        },
    ]
    payload = "".join(json.dumps(item) + "\n" for item in resources).encode()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fhir/resources.ndjson.gz", gzip.compress(payload))
    registry_path = _registry_file(
        tmp_path,
        _entry(adapter="fhir_ndjson_archive", schema="FHIR R4"),
    )

    output = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    records = [
        json.loads(line)
        for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    observation, condition = records
    assert observation["knowledge_time_field"] == "meta.lastUpdated"
    assert observation["temporal_precision"] == "datetime"
    assert observation["original_payload_pointer"].endswith("resources.ndjson.gz#L1")
    assert condition["knowledge_time"] is None
    assert condition["knowledge_time_field"] is None
    assert condition["temporal_precision"] == "day"
    assert condition["estimated_time"] is False
    manifest = json.loads(
        (output / "normalization_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["metrics"]["subject_count"] == 1
    assert manifest["estimated_times_created"] == 0


def test_frozen_manifest_verifier_accepts_exact_source_and_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    monkeypatch.setattr("scripts.data.verify_manifest.repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("record.json", json.dumps({"subject": "synthetic"}))
    registry_path = _registry_file(tmp_path, _entry())
    verification = verify_dataset("fixture_data", registry_path)
    payload = {
        "schema_version": "clara-dataset-freeze.v1",
        "status": "FROZEN_LOCAL_INTEGRITY_METADATA",
        "dataset_id": "fixture_data",
        "canonical_source": "https://example.invalid/data",
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "source_git_sha": "a" * 40,
        "verification": verification,
    }
    payload["manifest_payload_sha256"] = hashlib.sha256(
        canonical_json(payload).encode()
    ).hexdigest()
    manifest_path = tmp_path / "datasets" / "manifests" / "fixture_data.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    report = verify_frozen_manifest(
        "fixture_data", manifest_path=manifest_path, registry_path=registry_path
    )
    assert report["status"] == "VERIFIED_FROZEN_LOCAL_INTEGRITY_MANIFEST"
    assert report["source_git_commit_status"] == "NOT_CHECKED_NO_GIT_METADATA"

    payload["verification"]["total_bytes"] = 1
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DatasetRegistryError, match="MANIFEST_PAYLOAD_HASH_MISMATCH"):
        verify_frozen_manifest(
            "fixture_data", manifest_path=manifest_path, registry_path=registry_path
        )


def test_diabetes_normalization_preserves_unknown_time_and_source_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    row = {
        "encounter_id": "enc-1",
        "patient_nbr": "subject-1",
        "diag_1": "250.01",
        "diag_2": "?",
        "diag_3": "401",
        "max_glu_serum": "None",
        "A1Cresult": ">8",
        **{field: "No" for field in MEDICATION_FIELDS},
        **{field: "0" for field in SUMMARY_FIELDS},
    }
    row["insulin"] = "Up"
    with zipfile.ZipFile(archive_path, "w") as archive:
        header = list(row)
        csv_payload = ",".join(header) + "\n" + ",".join(row[field] for field in header) + "\n"
        archive.writestr("diabetic_data.csv", csv_payload)
    registry_path = _registry_file(
        tmp_path,
        _entry(
            adapter="diabetes_130_tabular",
            schema="tabular encounter CSV",
            expected_files=["diabetic_data.csv"],
        ),
    )

    output = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    records = [
        json.loads(line)
        for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 1 + 2 + len(MEDICATION_FIELDS) + 1
    assert all(record["valid_time"] is None for record in records)
    assert all(record["knowledge_time"] is None for record in records)
    assert all(record["estimated_time"] is False for record in records)
    assert all(record["original_payload_pointer"].endswith("diabetic_data.csv#L2") for record in records)
    manifest = json.loads(
        (output / "normalization_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["metrics"]["source_row_count"] == 1
    assert manifest["metrics"]["duplicate_encounter_id_count"] == 0
