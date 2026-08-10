from __future__ import annotations

import pytest

from evaluation.commitloop.secret_scan import expand_paths, scan_paths


def test_secret_scan_detects_actual_key_and_authorization_material(tmp_path) -> None:
    key = tmp_path / "key.txt"
    key.write_text("sk-" + "abcdefghijklmnopqrstuvwxyz")
    header = tmp_path / "header.txt"
    header.write_text("Authorization: Bearer " + "abcdefghijklmno")
    assert scan_paths([key, header]) == [str(header), str(key)]


def test_secret_scan_permits_blank_placeholders_and_nonsecret_identifiers(tmp_path) -> None:
    placeholder = tmp_path / "placeholder.env"
    placeholder.write_text("ROUTER_API_KEY=\nmodel=antigravity/gemini-3.6-flash-high\n")
    assert scan_paths([placeholder]) == []


def test_explicit_scan_paths_stay_within_repository(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "safe.txt").write_text("safe")
    assert expand_paths(tmp_path, ["source"]) == [source / "safe.txt"]
    with pytest.raises(ValueError, match="scan_path_outside_repo"):
        expand_paths(tmp_path, ["../outside"])
