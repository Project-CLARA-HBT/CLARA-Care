from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import pytest

import evaluation.careguard_external.acquire_rxnorm as rxnorm
from evaluation.careguard_external.acquire_rxnorm import (
    _archive_inventory,
    build_manifest,
)
from evaluation.careguard_external.source_manifest import validate_source_manifest


def _archive(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("rrf/RXNCONSO.RRF", "A|B|\nC|D|\n")
        archive.writestr("rrf/RXNREL.RRF", "E|F|\n")
    return path


def test_rxnorm_manifest_hashes_every_rrf_record_and_is_source_valid(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "rxnorm.zip")
    manifest = build_manifest(
        archive_path=archive,
        source_url="https://download.nlm.nih.gov/example.zip",
        release="RxNorm_full_prescribe_fixture",
        retrieved_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    assert manifest["row_count"] == 3
    assert manifest["archive_md5"] == hashlib.md5(archive.read_bytes()).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_source_manifest(path)["independence_role"] == "terminology"


def test_rxnorm_inventory_rejects_html_or_zip_without_rrf(tmp_path: Path) -> None:
    html = tmp_path / "login.html"
    html.write_text("<html>login</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="careguard_rxnorm_payload_not_zip"):
        _archive_inventory(html)
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("README.txt", "not an RRF release")
    with pytest.raises(ValueError, match="careguard_rxnorm_rrf_members_missing"):
        _archive_inventory(empty)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_acquisition_refuses_login_html_without_retaining_a_false_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(rxnorm, "urlopen", lambda *_args, **_kwargs: _Response(b"<html>UTS login</html>"))
    with pytest.raises(ValueError, match="careguard_rxnorm_payload_not_zip"):
        rxnorm.acquire(
            archive_dir=tmp_path / "archive",
            source_url="https://download.nlm.nih.gov/example.zip",
            release="fixture",
            expected_md5="a" * 32,
            manifest_path=tmp_path / "manifest.json",
        )
    assert not (tmp_path / "archive/fixture.zip").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_acquisition_writes_a_valid_manifest_only_after_md5_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = _archive(tmp_path / "source.zip")
    payload = archive.read_bytes()
    monkeypatch.setattr(rxnorm, "urlopen", lambda *_args, **_kwargs: _Response(payload))
    manifest_path = tmp_path / "manifest.json"
    manifest = rxnorm.acquire(
        archive_dir=tmp_path / "controlled",
        source_url="https://download.nlm.nih.gov/example.zip",
        release="fixture",
        expected_md5=hashlib.md5(payload).hexdigest(),
        manifest_path=manifest_path,
    )
    assert manifest["row_count"] == 3
    assert validate_source_manifest(manifest_path)["payload_sha256"] == manifest["payload_sha256"]
