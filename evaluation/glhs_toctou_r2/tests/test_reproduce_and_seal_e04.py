"""Tests for E04 protocol freeze, sealing, and offline reproduction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.glhs_toctou_r2.seal import seal_experiment_e04
from reproduce_e04 import reproduce_and_verify, verify_checksums


def test_e04_protocol_freeze_exists() -> None:
    protocol_path = Path("protocols/E04_randomized_toctou/protocol.json")
    assert protocol_path.is_file()
    data = json.loads(protocol_path.read_text(encoding="utf-8"))
    assert data["status"] == "FROZEN"
    assert data["schema_version"] == "glhs-toctou-e04-randomized-v1"
    assert data["generator_spec"]["minimum_schedules"] >= 1024
    assert data["generator_spec"]["total_schedules"] >= 1024


def test_e04_artifact_bundle_verification() -> None:
    artifacts_dir = Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E04_randomized_toctou")
    protocol_path = Path("protocols/E04_randomized_toctou/protocol.json")

    assert artifacts_dir.is_dir()
    assert (artifacts_dir / "seal.json").is_file()
    assert (artifacts_dir / "checksums.sha256").is_file()

    # Verify checksums offline
    checksums = verify_checksums(artifacts_dir)
    assert len(checksums) == 8  # 7 files in inventory + seal.json

    # Reproduce and verify
    result = reproduce_and_verify(artifact_dir=artifacts_dir, protocol_path=protocol_path)
    assert result["status"] == "REPRODUCED_AND_VERIFIED"
    assert result["claim_eligible"] is True
    assert result["total_schedules"] >= 1024


def test_e04_sealing_in_tmp_dir(tmp_path: Path) -> None:
    protocol_path = Path("protocols/E04_randomized_toctou/protocol.json")
    seal = seal_experiment_e04(protocol_path=protocol_path, artifacts_dir=tmp_path)

    assert seal["status"] == "SEALED"
    assert seal["claim_eligible"] is True
    assert seal["forbidden_commits"] == 0
    assert (tmp_path / "seal.json").is_file()
    assert (tmp_path / "checksums.sha256").is_file()
