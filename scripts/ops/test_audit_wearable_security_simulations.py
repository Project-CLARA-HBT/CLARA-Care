#!/usr/bin/env python3
"""Tests for Wearable & Connected Health Operational Threat Simulator."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import pytest

# Ensure repo root and API src are on sys.path
_repo_root = Path(__file__).resolve().parents[2]
_api_src = _repo_root / "services/api/src"
_scripts_ops = _repo_root / "scripts/ops"
for p in (str(_repo_root), str(_api_src), str(_scripts_ops)):
    if p not in sys.path:
        sys.path.insert(0, p)

from simulate_wearable_security_threats import WearableSecuritySimulator, main


@pytest.fixture
def simulator() -> WearableSecuritySimulator:
    sim = WearableSecuritySimulator()
    try:
        yield sim
    finally:
        sim.close()


def test_simulation_suite_clean_pass(simulator: WearableSecuritySimulator) -> None:
    """Full threat simulation suite passes cleanly with zero high/critical failures."""
    results = simulator.run_all_simulations()
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Expected 0 failed simulations, got: {failed}"
    assert len(results) == 12


def test_out_of_order_replay_identical_batch(simulator: WearableSecuritySimulator) -> None:
    """Replaying an identical batch payload produces idempotent response without duplicates."""
    result = simulator.simulate_identical_batch_replay()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_01"


def test_tampered_payload_hash_collision_blocked(simulator: WearableSecuritySimulator) -> None:
    """Modifying record content under identical idempotency key is blocked with HTTP 409."""
    result = simulator.simulate_tampered_payload_hash_collision()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_02"


def test_stale_update_and_tombstone_versioning(simulator: WearableSecuritySimulator) -> None:
    """Tombstone and late updates increment observation version_no rather than corrupting state."""
    result = simulator.simulate_stale_update_and_tombstone_versioning()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_03"


def test_clock_drift_inverted_interval_rejected(simulator: WearableSecuritySimulator) -> None:
    """Schema validator rejects negative interval (observed_end < observed_start)."""
    result = simulator.simulate_clock_drift_inverted_interval()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_04"


def test_clock_drift_invalid_zone_offset_rejected(simulator: WearableSecuritySimulator) -> None:
    """Non-standard UTC timezone offsets (+25:00) fail schema validation."""
    result = simulator.simulate_clock_drift_invalid_zone_offset()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_05"


def test_clock_drift_future_timestamp_detected(simulator: WearableSecuritySimulator) -> None:
    """Future timestamp assertions exceeding allowable window are flagged for quarantine."""
    result = simulator.simulate_clock_drift_future_timestamp_quarantine()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_06"


def test_token_non_exposure_in_serialization(simulator: WearableSecuritySimulator) -> None:
    """Serialized ConnectorResponse contains zero ciphertext or plaintext token fields."""
    result = simulator.simulate_token_non_exposure_in_serialization()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_07"


def test_token_purge_on_disconnect(simulator: WearableSecuritySimulator) -> None:
    """Disconnecting connector zeroes out token ciphertext and key version."""
    result = simulator.simulate_token_purge_on_disconnect()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_08"


def test_cross_profile_anti_enumeration(simulator: WearableSecuritySimulator) -> None:
    """Unauthorized cross-profile connector query returns constant HTTP 404 (anti-enumeration)."""
    result = simulator.simulate_cross_profile_anti_enumeration()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_09"


def test_unconsented_data_type_rejection(simulator: WearableSecuritySimulator) -> None:
    """Importing biometric types outside active user consent raises HTTP 403 Forbidden."""
    result = simulator.simulate_unconsented_data_type_rejection()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_10"


def test_non_finite_metric_rejection(simulator: WearableSecuritySimulator) -> None:
    """NaN and Infinite measurement values are rejected during schema validation."""
    result = simulator.simulate_non_finite_metric_rejection()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_11"


def test_cascading_data_deletion(simulator: WearableSecuritySimulator) -> None:
    """Invoking delete_imported_data removes all observations and daily aggregate projections."""
    result = simulator.simulate_cascading_data_deletion()
    assert result.passed is True
    assert result.scenario_id == "THREAT_SIM_12"


def test_cli_runner_exit_code_zero() -> None:
    """CLI execution with --fail-on-high returns exit code 0."""
    exit_code = main(["--fail-on-high", "--json"])
    assert exit_code == 0
