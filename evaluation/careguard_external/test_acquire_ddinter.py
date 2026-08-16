from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.careguard_external.acquire_ddinter import (
    DDINTER_FILES,
    build_manifest,
    record_inventory,
    verify_archive,
)
from evaluation.careguard_external.source_manifest import validate_source_manifest


def test_inventory_is_complete_and_manifest_is_source_valid(tmp_path: Path) -> None:
    archive = tmp_path / "controlled-ddinter"
    archive.mkdir()
    for index, name in enumerate(DDINTER_FILES):
        (archive / name).write_text(
            "drug_a,drug_b,severity\n"
            f"drug-{index},other-{index},major\n",
            encoding="utf-8",
        )

    inventory, payload_hashes = record_inventory(archive / name for name in DDINTER_FILES)
    assert len(inventory) == len(DDINTER_FILES)
    assert len({row["source_record_id"] for row in inventory}) == len(DDINTER_FILES)
    assert inventory[0]["source_record_hash"] == hashlib.sha256(
        b'{"record":{"drug_a":"drug-0","drug_b":"other-0","severity":"major"},'
        b'"row_number":1,"source_file":"ddinter_downloads_code_A.csv"}'
    ).hexdigest()
    assert set(payload_hashes) == set(DDINTER_FILES)

    manifest_path = tmp_path / "ddinter-manifest.json"
    manifest_path.write_text(
        json.dumps(
            build_manifest(archive_dir=archive, retrieved_at=datetime(2026, 8, 17, tzinfo=UTC))
        ),
        encoding="utf-8",
    )
    validated = validate_source_manifest(manifest_path)
    assert validated["row_count"] == len(DDINTER_FILES)
    assert validated["redistribution_policy"] == "raw_prohibited"
    assert verify_archive(manifest_path=manifest_path)["verification_status"] == "archive_matches_manifest"

    (archive / DDINTER_FILES[0]).write_text("drug_a,drug_b,severity\ntampered,row,major\n", encoding="utf-8")
    try:
        verify_archive(manifest_path=manifest_path)
    except ValueError as exc:
        assert str(exc) == "careguard_ddinter_archive_payload_hash_mismatch"
    else:
        raise AssertionError("modified controlled payload must fail verification")
