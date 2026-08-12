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
    placeholder.write_text(
        "ROUTER_API_KEY=\n"
        "model=gemini-3.6-flash-high\n"
        "path=research/risk-deep-dive-and-mitigation.md\n"
    )
    assert scan_paths([placeholder]) == []


def test_secret_scan_permits_explicit_redaction_marker(tmp_path) -> None:
    placeholder = tmp_path / "redacted.md"
    placeholder.write_text(
        "ROUTER_API_KEY=[REDACTED]\nOPENAI_API_KEY = [REDACTED]\n"
    )
    assert scan_paths([placeholder]) == []


def test_secret_scan_rejects_redaction_marker_with_appended_material(tmp_path) -> None:
    malformed = tmp_path / "malformed.env"
    malformed.write_text("ROUTER_API_KEY=" + "[REDACTED]" + "unexpected\n")
    assert scan_paths([malformed]) == [str(malformed)]


def test_explicit_scan_paths_stay_within_repository(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "safe.txt").write_text("safe")
    assert expand_paths(tmp_path, ["source"]) == [source / "safe.txt"]
    with pytest.raises(ValueError, match="scan_path_outside_repo"):
        expand_paths(tmp_path, ["../outside"])
