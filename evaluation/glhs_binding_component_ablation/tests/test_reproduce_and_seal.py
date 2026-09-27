"""Unit tests for E01 seal generator and offline reproduction script."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluation.glhs_binding_component_ablation.seal import seal_experiment
from reproduce_e01 import reproduce_and_verify, disable_network, NetworkAccessProhibitedError
import socket


def test_network_disabled_prohibits_sockets() -> None:
    disable_network()
    with pytest.raises(NetworkAccessProhibitedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_reproduce_e01_sealed_artifact() -> None:
    artifact_dir = Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E01_binding_components")
    schedules_path = Path("protocols/E01_binding_components/schedules.json")

    report = reproduce_and_verify(
        artifact_dir=artifact_dir,
        schedules_path=schedules_path,
    )
    assert report["status"] == "REPRODUCED_AND_VERIFIED"
    assert report["seal_verified"] is True
    assert report["claim_eligible"] is True
    assert report["clean_controls_admitted_rate"] == 1.0
    assert report["total_schedules"] == 352
    assert report["total_executions"] == 2816
    assert report["checksums_verified_count"] >= 7


def test_artifact_structure_completeness() -> None:
    artifact_dir = Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E01_binding_components")
    assert (artifact_dir / "protocol.json").is_file()
    assert (artifact_dir / "protocol.sha256").is_file()
    assert (artifact_dir / "environment.json").is_file()
    assert (artifact_dir / "raw" / "runs.jsonl").is_file()
    assert (artifact_dir / "derived" / "summary.json").is_file()
    assert (artifact_dir / "derived" / "summary.md").is_file()
    assert (artifact_dir / "validation.json").is_file()
    assert (artifact_dir / "checksums.sha256").is_file()
    assert (artifact_dir / "seal.json").is_file()
