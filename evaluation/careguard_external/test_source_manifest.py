from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.careguard_external.source_manifest import (
    validate_source_manifest,
    validate_source_set,
)
from evaluation.evidence_program.freeze import FreezeError


def _manifest(role: str) -> dict[str, object]:
    return {
        "schema_version": "careguard-vn.source-manifest.v1", "status": "FROZEN_ACQUIRED",
        "source_name": role, "independence_role": role, "source_url": "https://example.test/source",
        "retrieved_at_utc": "2026-08-16T00:00:00Z", "version_or_release": "v1",
        "access_terms": "reviewed", "license": "reviewed", "redistribution_policy": "derived_only",
        "payload_sha256": "a" * 64, "row_count": 1,
        "record_hash_algorithm": "sha256(canonical_record_json)",
        "record_hash_inventory": [{"source_record_id": "record", "source_record_hash": "b" * 64}],
        "raw_retention_location": "/controlled/archive/source-v1",
    }


def _write(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_metadata_probe_cannot_be_used_as_final_source(tmp_path: Path) -> None:
    value = _manifest("regulatory_confirmation")
    value["status"] = "METADATA_PROBE_ONLY_NOT_BENCHMARK"
    with pytest.raises(FreezeError, match="careguard_source_manifest_not_frozen_acquired"):
        validate_source_manifest(_write(tmp_path / "probe.json", value))


def test_final_source_set_requires_all_independent_roles(tmp_path: Path) -> None:
    paths = [_write(tmp_path / f"{role}.json", _manifest(role)) for role in (
        "identity_frame", "terminology", "positive_ddi_reference", "regulatory_confirmation",
    )]
    assert len(validate_source_set(paths)) == 4


def test_final_manifest_requires_full_unique_inventory_and_retrieval_metadata(tmp_path: Path) -> None:
    value = _manifest("identity_frame")
    value["row_count"] = 2
    with pytest.raises(FreezeError, match="careguard_source_manifest_inventory_count_mismatch"):
        validate_source_manifest(_write(tmp_path / "incomplete.json", value))
    value["row_count"] = 1
    value["retrieved_at_utc"] = "not-a-date"
    with pytest.raises(FreezeError, match="careguard_source_manifest_retrieved_at_invalid"):
        validate_source_manifest(_write(tmp_path / "bad-date.json", value))


def test_final_manifest_rejects_non_hex_hashes(tmp_path: Path) -> None:
    value = _manifest("identity_frame")
    value["payload_sha256"] = "z" * 64
    with pytest.raises(FreezeError, match="careguard_source_manifest_payload_hash_invalid"):
        validate_source_manifest(_write(tmp_path / "bad-payload.json", value))
