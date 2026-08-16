from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.governance_adversarial.seal_development import seal, verify_seal


def _probe() -> dict[str, object]:
    return {
        "schema_version": "govred-boundary-development-probe-v1",
        "status": "development_boundary_probe_not_headline",
    }


def test_development_seal_requires_expected_transfer_hash(tmp_path: Path) -> None:
    probe = tmp_path / "boundary_path_probe.json"
    probe.write_text(json.dumps(_probe()), encoding="utf-8")
    expected = hashlib.sha256(probe.read_bytes()).hexdigest()
    seal_path = seal(run_dir=tmp_path, expected_probe_sha256=expected)
    payload = json.loads(seal_path.read_text(encoding="utf-8"))
    assert payload["headline_claims_permitted"] is False
    assert payload["files"]["boundary_path_probe.json"] == expected
    assert verify_seal(run_dir=tmp_path)["expected_probe_sha256"] == expected


def test_development_seal_rejects_corrupted_transfer(tmp_path: Path) -> None:
    (tmp_path / "boundary_path_probe.json").write_bytes(b"\x00corrupted")
    with pytest.raises(ValueError, match="govred_development_probe_invalid_json"):
        seal(run_dir=tmp_path, expected_probe_sha256="a" * 64)


def test_development_seal_detects_post_seal_mutation(tmp_path: Path) -> None:
    probe = tmp_path / "boundary_path_probe.json"
    probe.write_text(json.dumps(_probe()), encoding="utf-8")
    seal(run_dir=tmp_path, expected_probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest())
    probe.write_text(json.dumps({**_probe(), "mutated": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="govred_development_seal_hash_mismatch"):
        verify_seal(run_dir=tmp_path)
