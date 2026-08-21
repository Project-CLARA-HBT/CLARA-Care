from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Self

import pytest
import yaml

from datasets.adapters.diabetes_130_tabular import MEDICATION_FIELDS, SUMMARY_FIELDS
from datasets.adapters.eicu_tabular import (
    PATIENT_MEMBER,
    PATIENT_REQUIRED_FIELDS,
    TABLES,
)
from datasets.adapters.omop_cdm import TABLES as OMOP_TABLES
from scripts.data import _registry
from scripts.data._registry import DatasetRegistryError, canonical_json, load_registry
from scripts.data.fetch import fetch_dataset
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
    assert rows["cms_de_synpuf_omop"]["local_status"] == "PRESENT_UNVERIFIED"
    assert rows["cms_de_synpuf_omop_100k"]["local_status"] == "PRESENT_UNVERIFIED"
    assert rows["synthea_coherent"]["local_status"] == "PRESENT_UNVERIFIED"


def test_data_cli_bootstrap_does_not_shadow_standard_library_inspect() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/data/normalize.py", "--help"],
        cwd=_registry.repository_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


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


def test_verify_checks_provider_sha256_manifest_inside_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    data = b"subject,value\n1,synthetic\n"
    digest = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("expected.csv", data)
        archive.writestr("SHA256SUMS.txt", f"{digest} expected.csv\n")
    registry_path = _registry_file(
        tmp_path,
        _entry(
            expected_files=["expected.csv", "SHA256SUMS.txt"],
            provider_checksum_manifest="SHA256SUMS.txt",
        ),
    )

    verification = verify_dataset("fixture_data", registry_path)

    assert verification["canonical_checksum_status"] == "VERIFIED_PROVIDER_SHA256"
    assert verification["provider_checksum"]["verified_file_count"] == 1


def test_verify_rejects_provider_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("expected.csv", "changed")
        archive.writestr("SHA256SUMS.txt", f"{'0' * 64} expected.csv\n")
    registry_path = _registry_file(
        tmp_path,
        _entry(
            expected_files=["expected.csv", "SHA256SUMS.txt"],
            provider_checksum_manifest="SHA256SUMS.txt",
        ),
    )

    with pytest.raises(DatasetRegistryError, match="PROVIDER_CHECKSUM_MISMATCH"):
        verify_dataset("fixture_data", registry_path)


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


def test_partial_download_is_not_reported_as_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    raw_dir = tmp_path / "datasets" / "raw" / "fixture_data"
    raw_dir.mkdir(parents=True)
    (raw_dir / ".fixture.zip.part").write_bytes(b"incomplete")
    registry_path = _registry_file(tmp_path, _entry(local_candidates=[]))

    rows = inventory(registry_path)

    assert rows[0]["local_status"] == "NOT_AVAILABLE"
    with pytest.raises(DatasetRegistryError, match="NOT_AVAILABLE"):
        inspect_dataset("fixture_data", registry_path)


def test_verify_rejects_configured_incomplete_source_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    raw_dir = tmp_path / "datasets" / "raw" / "fixture_data"
    raw_dir.mkdir(parents=True)
    (raw_dir / "complete.csv.lzo").write_bytes(b"complete")
    (raw_dir / "complete.csv.lzo.a1B2c3D4").write_bytes(b"partial")
    registry_path = _registry_file(
        tmp_path,
        _entry(local_candidates=[], reject_file_globs=["*.lzo.*"]),
    )

    with pytest.raises(DatasetRegistryError, match="SOURCE_REJECTED_FILE"):
        verify_dataset("fixture_data", registry_path)


def test_fetch_resumes_only_from_valid_https_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    monkeypatch.setattr("scripts.data.fetch.repository_root", lambda: tmp_path)
    registry_path = _registry_file(
        tmp_path,
        _entry(
            download_method="https_archive",
            download_url="https://example.invalid/archive/",
            download_filename="fixture.zip",
        ),
    )
    raw_dir = tmp_path / "datasets" / "raw" / "fixture_data"
    raw_dir.mkdir(parents=True)
    (raw_dir / ".fixture.zip.part").write_bytes(b"abc")

    class Response:
        status = 206

        def __init__(self) -> None:
            self.headers = {"Content-Range": "bytes 3-5/6"}
            self._read = False

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://example.invalid/archive/"

        def read(self, _size: int) -> bytes:
            if self._read:
                return b""
            self._read = True
            return b"def"

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())

    result = fetch_dataset(
        "fixture_data", accept_license=True, resume=True, registry_path=registry_path
    )

    assert result["resumed_from_bytes"] == 3
    assert (raw_dir / "fixture.zip").read_bytes() == b"abcdef"


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
    manifest = json.loads((output / "normalization_manifest.json").read_text(encoding="utf-8"))
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
        "dataset_registry_entry_sha256": hashlib.sha256(
            canonical_json(_entry()).encode()
        ).hexdigest(),
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

    expanded_registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    expanded_registry["datasets"].append(_entry(id="unrelated_data"))
    registry_path.write_text(yaml.safe_dump(expanded_registry), encoding="utf-8")
    report = verify_frozen_manifest(
        "fixture_data", manifest_path=manifest_path, registry_path=registry_path
    )
    assert report["registry_binding_status"] == "DATASET_ENTRY_UNCHANGED"

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
    assert all(
        record["original_payload_pointer"].endswith("diabetic_data.csv#L2") for record in records
    )
    manifest = json.loads((output / "normalization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["metrics"]["source_row_count"] == 1
    assert manifest["metrics"]["duplicate_encounter_id_count"] == 0


def test_omop_normalization_minimizes_demographics_and_preserves_source_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    source = tmp_path / "omop"
    source.mkdir()
    person_payload = (
        "person_id,person_source_value,gender_source_value\n"
        "subject-1,private-source-id,Synthetic Name\n"
    )
    with gzip.open(source / "person.csv.gz", "wt", encoding="utf-8") as stream:
        stream.write(person_payload)
    condition = next(item for item in OMOP_TABLES if item.name == "condition_occurrence")
    row = {
        "condition_occurrence_id": "condition-1",
        "person_id": "subject-1",
        "visit_occurrence_id": "visit-1",
        "condition_start_date": "2020-01-02",
        "condition_start_datetime": "",
        "condition_end_date": "2020-01-03",
        "condition_end_datetime": "",
        **{field: "synthetic" for field in condition.value_fields},
    }
    row["condition_concept_id"] = "0"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    with gzip.open(source / "condition_occurrence.csv.gz", "wt", encoding="utf-8") as stream:
        stream.write(output.getvalue())
    registry_path = _registry_file(
        tmp_path,
        _entry(
            adapter="omop_cdm",
            schema="OMOP CDM",
            raw_path="omop",
            local_candidates=[],
            expected_files=["person.csv.gz", "condition_occurrence.csv.gz"],
        ),
    )

    normalized = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    with gzip.open(normalized / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        rendered = stream.read()
    records = [json.loads(line) for line in rendered.splitlines()]

    assert len(records) == 1
    assert records[0]["source_subject"] == "subject-1"
    assert records[0]["valid_time"] == "2020-01-02"
    assert records[0]["valid_time_field"] == "condition_start_date"
    assert records[0]["normalized_value"]["valid_end"] == "2020-01-03"
    assert records[0]["knowledge_time"] is None
    assert records[0]["estimated_time"] is False
    assert "unmapped_concept_id" in records[0]["uncertainty"]
    assert "private-source-id" not in rendered
    assert "Synthetic Name" not in rendered
    manifest = json.loads((normalized / "normalization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["metrics"]["record_count"] == 1
    assert "person" in manifest["metrics"]["omitted_reference_or_derived_tables"]


def _gzip_csv(row: dict[str, str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return gzip.compress(output.getvalue().encode())


def _tar_gz(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, payload in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return output.getvalue()


def test_eicu_normalization_preserves_minute_offsets_without_fabricated_datetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "fixture.zip"
    patient = {field: "value" for field in PATIENT_REQUIRED_FIELDS}
    patient.update(
        {
            "patientunitstayid": "stay-1",
            "patienthealthsystemstayid": "health-stay-1",
            "uniquepid": "subject-1",
            "unitdischargeoffset": "60",
        }
    )
    expected_files = [PATIENT_MEMBER]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(PATIENT_MEMBER, _gzip_csv(patient))
        for index, contract in enumerate(TABLES, start=1):
            row = {
                "patientunitstayid": "stay-1",
                contract.primary_key: str(index),
                **{field: "5" for field in contract.offset_fields},
                **{field: "value" for field in contract.value_fields},
            }
            archive.writestr(contract.member, _gzip_csv(row))
            expected_files.append(contract.member)
    registry_path = _registry_file(
        tmp_path,
        _entry(
            adapter="eicu_tabular",
            schema="relational CSV",
            expected_files=expected_files,
        ),
    )

    output = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    records = [
        json.loads(line)
        for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 1 + len(TABLES)
    assert all(record["valid_time"] is not None for record in records)
    assert all(record["knowledge_time"] is None for record in records)
    assert all(record["estimated_time"] is False for record in records)
    assert all("offset" in record["temporal_precision"] for record in records)
    assert all(record["source_subject"] == "subject-1" for record in records)


def test_nested_fhir_bundle_normalization_minimizes_patient_demographics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    patient_full_url = "urn:uuid:patient-1"
    encounter_full_url = "urn:uuid:encounter-1"
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "fullUrl": patient_full_url,
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-1",
                    "name": [{"family": "SyntheticName"}],
                    "address": [{"line": ["SyntheticAddress"]}],
                },
            },
            {
                "fullUrl": encounter_full_url,
                "resource": {
                    "resourceType": "Encounter",
                    "id": "encounter-1",
                    "subject": {"reference": patient_full_url},
                    "period": {"start": "2020-01-01", "end": "2020-01-02"},
                    "status": "finished",
                },
            },
            {
                "fullUrl": "urn:uuid:condition-1",
                "resource": {
                    "resourceType": "Condition",
                    "id": "condition-1",
                    "subject": {"reference": patient_full_url},
                    "context": {"reference": encounter_full_url},
                    "onsetDateTime": "2020-01-01",
                    "code": {"coding": [{"code": "synthetic-code"}]},
                },
            },
            {
                "fullUrl": "urn:uuid:medication-1",
                "resource": {
                    "resourceType": "MedicationOrder",
                    "id": "medication-1",
                    "patient": {"reference": patient_full_url},
                    "encounter": {"reference": encounter_full_url},
                    "authoredOn": "2020-01-01",
                    "medicationCodeableConcept": {"coding": [{"code": "synthetic-medication"}]},
                    "status": "active",
                },
            },
        ],
    }
    nested = _tar_gz({"output/fhir/00/patient-1.json": json.dumps(bundle).encode()})
    outer = _tar_gz({"chunk-1.tar.gz": nested})
    archive_path = tmp_path / "fixture.tar.gz"
    archive_path.write_bytes(outer)
    registry_path = _registry_file(
        tmp_path,
        _entry(
            adapter="nested_fhir_bundle_tar",
            schema="FHIR STU3",
            local_candidates=["fixture.tar.gz"],
            expected_files=["fixture.tar.gz"],
        ),
    )

    verification = verify_dataset("fixture_data", registry_path)
    assert verification["archive"]["nested_archive_count"] == 1
    assert verification["archive"]["nested_fhir_bundle_count"] == 1

    output = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    with gzip.open(output / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        rendered = stream.read()
    records = [json.loads(line) for line in rendered.splitlines()]

    assert len(records) == 3
    assert all(record["evidence_type"] != "Patient" for record in records)
    assert all(record["source_subject"] == "Patient/patient-1" for record in records)
    assert all("chunk-1.tar.gz" in record["original_payload_pointer"] for record in records)
    assert "SyntheticName" not in rendered
    assert "SyntheticAddress" not in rendered
    manifest = json.loads((output / "normalization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["records_file"] == "records.jsonl.gz"
    assert manifest["metrics"]["subject_count"] == 1


def test_coherent_multimodal_normalization_minimizes_patient_and_counts_modalities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_registry, "repository_root", lambda: tmp_path)
    archive_path = tmp_path / "coherent.zip"
    patient_url = "urn:uuid:patient-1"
    encounter_url = "urn:uuid:encounter-1"
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": patient_url,
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-1",
                    "name": [{"family": "SyntheticName"}],
                },
            },
            {
                "fullUrl": encounter_url,
                "resource": {
                    "resourceType": "Encounter",
                    "id": "encounter-1",
                    "subject": {"reference": patient_url},
                    "period": {"start": "2020-01-01"},
                },
            },
            {
                "fullUrl": "urn:uuid:condition-1",
                "resource": {
                    "resourceType": "Condition",
                    "id": "condition-1",
                    "subject": {"reference": patient_url},
                    "encounter": {"reference": encounter_url},
                    "onsetDateTime": "2020-01-01",
                    "code": {"coding": [{"code": "synthetic"}]},
                },
            },
        ],
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fhir/patient-bundle.json", json.dumps(bundle))
        archive.writestr("fhir/organizations.json", "{}")
        archive.writestr("csv/patients.csv", "id,name\n1,SyntheticName\n")
        archive.writestr("dicom/name_with_phi.dcm", b"synthetic")
    registry_path = _registry_file(
        tmp_path,
        _entry(
            adapter="coherent_multimodal",
            schema="FHIR plus linked modalities",
            local_candidates=["coherent.zip"],
            expected_files=["fhir/patient-bundle.json"],
        ),
    )

    output = normalize_dataset(
        "fixture_data", output=tmp_path / "normalized", registry_path=registry_path
    )
    with gzip.open(output / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        rendered = stream.read()
    records = [json.loads(line) for line in rendered.splitlines()]

    assert len(records) == 2
    assert all(record["source_subject"] == "Patient/patient-1" for record in records)
    assert "SyntheticName" not in rendered
    assert "patient-bundle.json" not in rendered
    assert all(
        record["original_payload_pointer"].startswith("zip-member-sha256://") for record in records
    )
    manifest = json.loads((output / "normalization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["metrics"]["bundle_count"] == 1
    assert manifest["metrics"]["modality_member_counts"] == {
        "csv": 1,
        "dicom": 1,
        "fhir": 2,
    }
