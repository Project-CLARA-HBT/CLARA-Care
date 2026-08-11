from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts.data import _registry
from scripts.data._registry import DatasetRegistryError, load_registry
from scripts.data.inspect import inspect_dataset
from scripts.data.list_sources import inventory
from scripts.data.normalize import normalize_dataset
from scripts.data.verify import verify_dataset


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
