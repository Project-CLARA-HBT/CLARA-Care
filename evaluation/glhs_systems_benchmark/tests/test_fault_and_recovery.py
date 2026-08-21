"""Unit and recovery verification tests for fault injection and ledger auditor."""

from __future__ import annotations

import copy
import hashlib

from evaluation.glhs_systems_benchmark.baselines.base import SimulatedCoordinator
from evaluation.glhs_systems_benchmark.fault_and_recovery import (
    FaultInjectionSuite,
    LedgerAuditor,
)


def test_empty_ledger_audit() -> None:
    res = LedgerAuditor.audit_ledger([])
    assert res.is_valid is True
    assert res.total_blocks_checked == 0
    assert res.corrupted_blocks_detected == 0


def test_valid_ledger_audit() -> None:
    coord = SimulatedCoordinator()
    coord.reset()
    for i in range(1, 10):
        coord.append_ledger(
            tx_id=f"tx_{i:03d}",
            profile_id="profile_001",
            payload_hash=hashlib.sha256(f"data_{i}".encode()).hexdigest(),
        )

    res = LedgerAuditor.audit_ledger(coord.ledger_events)
    assert res.is_valid is True
    assert res.total_blocks_checked == 9
    assert res.corrupted_blocks_detected == 0
    assert res.first_corrupted_seq is None


def test_corrupted_signature_detection() -> None:
    coord = SimulatedCoordinator()
    coord.reset()
    for i in range(1, 5):
        coord.append_ledger(
            tx_id=f"tx_{i:03d}",
            profile_id="profile_001",
            payload_hash=hashlib.sha256(f"data_{i}".encode()).hexdigest(),
        )

    tampered = copy.deepcopy(coord.ledger_events)
    tampered[1]["signature"] = "SIG_FORGED_BAD_AUTHENTICATOR"

    res = LedgerAuditor.audit_ledger(tampered)
    assert res.is_valid is False
    assert res.corrupted_blocks_detected == 1
    assert res.first_corrupted_seq == 2
    assert "Invalid cryptographic signature" in res.verification_message


def test_broken_hash_chain_detection() -> None:
    coord = SimulatedCoordinator()
    coord.reset()
    for i in range(1, 5):
        coord.append_ledger(
            tx_id=f"tx_{i:03d}",
            profile_id="profile_001",
            payload_hash=hashlib.sha256(f"data_{i}".encode()).hexdigest(),
        )

    tampered = copy.deepcopy(coord.ledger_events)
    tampered[2]["prev_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"

    res = LedgerAuditor.audit_ledger(tampered)
    assert res.is_valid is False
    assert res.first_corrupted_seq == 3
    assert "Broken hash chain" in res.verification_message


def test_fault_injection_suite_execution() -> None:
    suite = FaultInjectionSuite()
    report = suite.run_all_fault_tests()

    assert report.total_tests == 5
    assert report.passed_tests == 5
    assert report.failed_tests == 0
    assert report.all_passed is True
    assert report.ledger_audit.is_valid is True
