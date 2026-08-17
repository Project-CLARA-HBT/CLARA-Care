from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evaluation.careguard_external.acquire_dav import build_manifest
from evaluation.careguard_external.source_manifest import validate_source_manifest


def test_dav_manifest_accepts_pending_redistribution_review(tmp_path: Path) -> None:
    export = tmp_path / "dav.csv"
    export.write_text("registration_no,product_name\nVD-1,Thuoc A\n", encoding="utf-8")
    manifest = build_manifest(
        source_path=export,
        source_url="https://dichvucong.dav.gov.vn/export/approved.csv",
        release="DAV export 2026-08-17",
        record_id_field="registration_no",
        access_terms="Operator-authorized official export; acquisition permitted.", license_text="",
        redistribution_review_status="PENDING", retrieved_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_source_manifest(path)["redistribution_review_status"] == "PENDING"
    assert manifest["redistribution_policy"] == "raw_prohibited"


def test_dav_manifest_rejects_non_dav_or_duplicate_source_identifier(tmp_path: Path) -> None:
    export = tmp_path / "dav.json"
    export.write_text('[{"id":"VD-1"},{"id":"VD-1"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="careguard_dav_source_url_not_official"):
        build_manifest(
            source_path=export,
            source_url="https://example.test/export",
            release="v1",
            record_id_field="id",
            access_terms="authorized",
            license_text="",
            redistribution_review_status="PENDING",
            retrieved_at=datetime(2026, 8, 17, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="careguard_dav_record_identifier_invalid"):
        build_manifest(
            source_path=export,
            source_url="https://dav.gov.vn/export",
            release="v1",
            record_id_field="id",
            access_terms="authorized",
            license_text="",
            redistribution_review_status="PENDING",
            retrieved_at=datetime(2026, 8, 17, tzinfo=UTC),
        )
