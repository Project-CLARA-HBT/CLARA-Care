"""Unit tests for E02 Minimal Alternative Baseline comparator, runner, seal, and reproduction."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from evaluation.comparator_studies.minimal_readset_token.seal import seal_experiment_e02
from reproduce_e02 import NetworkAccessProhibitedError, disable_network, reproduce_and_verify_e02


def test_network_disabled_prohibits_sockets_e02() -> None:
    disable_network()
    with pytest.raises(NetworkAccessProhibitedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_seal_and_reproduce_e02() -> None:
    artifact_dir = Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E02_minimal_baseline")
    protocol_path = Path("protocols/E02_minimal_baseline/protocol.json")
    schedules_path = Path("protocols/E01_binding_components/schedules.json")
    method_card_path = Path("evaluation/comparator_studies/minimal_readset_token/METHOD_CARD.md")

    # Seal experiment
    seal_doc = seal_experiment_e02(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
        schedules_path=schedules_path,
        method_card_path=method_card_path,
        run_id="GLHS-Q2-R2-20260928-R01",
        backend="isolated_sqlite",
    )
    assert seal_doc["status"] == "SEALED"
    assert seal_doc["executed_executions"] == 1408
    assert seal_doc["claim_eligible"] is True

    # Reproduce and verify offline
    report = reproduce_and_verify_e02(
        artifact_dir=artifact_dir,
        schedules_path=schedules_path,
    )
    assert report["status"] == "REPRODUCED_AND_VERIFIED"
    assert report["seal_verified"] is True
    assert report["claim_eligible"] is True
    assert report["clean_controls_admitted_rate"] == 1.0
    assert report["adversarial_false_accept_rate"] == 0.0
    assert report["exact_decision_match"] is True
    assert report["total_schedules"] == 352
    assert report["total_executions"] == 1408
    assert report["checksums_verified_count"] >= 8


def test_e02_artifact_structure_completeness() -> None:
    artifact_dir = Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E02_minimal_baseline")
    assert (artifact_dir / "protocol.json").is_file()
    assert (artifact_dir / "protocol.sha256").is_file()
    assert (artifact_dir / "environment.json").is_file()
    assert (artifact_dir / "raw" / "runs.jsonl").is_file()
    assert (artifact_dir / "derived" / "comparison_summary.json").is_file()
    assert (artifact_dir / "derived" / "comparison_summary.md").is_file()
    assert (artifact_dir / "derived" / "comparator_method_card.md").is_file()
    assert (artifact_dir / "validation.json").is_file()
    assert (artifact_dir / "checksums.sha256").is_file()
    assert (artifact_dir / "seal.json").is_file()
