from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.careguard_external.acquire_dailymed import RAW_FILENAME, build_manifest
from evaluation.careguard_external.source_manifest import validate_source_manifest


def test_dailymed_subset_manifest_is_source_valid(tmp_path: Path) -> None:
    archive = tmp_path / "controlled-dailymed"
    archive.mkdir()
    (archive / RAW_FILENAME).write_text(
        json.dumps(
            {
                "data": [
                    {"setid": "a", "spl_version": 1, "published_date": "Aug 1, 2026", "title": "A"}
                ],
                "metadata": {"db_published_date": "Aug 2, 2026"},
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            build_manifest(archive_dir=archive, retrieved_at=datetime(2026, 8, 17, tzinfo=UTC))
        ),
        encoding="utf-8",
    )
    manifest = validate_source_manifest(path)
    assert manifest["independence_role"] == "regulatory_confirmation"
    assert manifest["row_count"] == 1
    assert manifest["redistribution_policy"] == "derived_only"
