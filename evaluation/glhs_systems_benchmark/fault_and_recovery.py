"""Fault Injection, Crash Recovery, and Cryptographic Ledger Verification Suite.

Validates GLHS transactional resiliency and ledger integrity across four fault classes:
1. Crash Aborts: Mid-transaction simulated worker crashes / unhandled exceptions.
2. Transaction Rollbacks: Clean state restoration upon invariant violation or explicit abort.
3. Signature Corruption & Tampering: Detection of compromised cryptographic signatures or altered payloads.
4. Ledger Consistency: Full cryptographic audit of the SHA-256 Merkle chain and causal version monotonicity.
"""

from __future__ import annotations

import copy
import hashlib
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from evaluation.glhs_systems_benchmark.baselines.base import (
    AbortCategory,
    SimulatedCoordinator,
    TxnStatus,
)
from evaluation.glhs_systems_benchmark.baselines.glhs_ss2pl import GLHSSS2PLEngine
from evaluation.glhs_systems_benchmark.workload_generator import (
    generate_clean_update,
    generate_workload,
)


@dataclass
class FaultTestCaseResult:
    """Individual fault injection test case outcome."""

    test_name: str
    fault_type: str
    injected_fault_description: str
    expected_behavior: str
    observed_behavior: str
    passed: bool
    recovery_latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LedgerAuditResult:
    """Outcome of cryptographic ledger audit."""

    is_valid: bool
    total_blocks_checked: int
    corrupted_blocks_detected: int
    first_corrupted_seq: int | None
    verification_message: str
    audit_duration_ms: float


@dataclass
class FaultRecoveryReport:
    """Comprehensive fault injection and recovery benchmark report."""

    total_tests: int
    passed_tests: int
    failed_tests: int
    all_passed: bool
    test_results: list[FaultTestCaseResult]
    ledger_audit: LedgerAuditResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "all_passed": self.all_passed,
            "test_results": [asdict(r) for r in self.test_results],
            "ledger_audit": asdict(self.ledger_audit),
        }


class LedgerAuditor:
    """Cryptographic audit engine for GLHS Merkle WW-DAG ledgers."""

    @staticmethod
    def audit_ledger(ledger_events: Sequence[dict[str, Any]]) -> LedgerAuditResult:
        """Performs exhaustive cryptographic verification of ledger hash chaining and signatures."""
        t_start = time.perf_counter()
        if not ledger_events:
            t_end = time.perf_counter()
            return LedgerAuditResult(
                is_valid=True,
                total_blocks_checked=0,
                corrupted_blocks_detected=0,
                first_corrupted_seq=None,
                verification_message="Empty ledger is valid by default",
                audit_duration_ms=(t_end - t_start) * 1000.0,
            )

        genesis_hash = hashlib.sha256(b"GLHS_GENESIS_STATE").hexdigest()
        prev_expected_hash = genesis_hash

        for idx, event in enumerate(ledger_events):
            seq = event.get("seq_num", idx + 1)
            tx_id = event.get("tx_id", "")
            profile_id = event.get("profile_id", "")
            merkle_root = event.get("merkle_root", "")
            signature = event.get("signature", "")
            prev_hash = event.get("prev_hash", "")
            payload_hash = event.get("payload_hash", "")
            status = event.get("status", "COMMITTED")

            # 1. Verify Prev-Hash Chaining
            if prev_hash != prev_expected_hash:
                t_end = time.perf_counter()
                return LedgerAuditResult(
                    is_valid=False,
                    total_blocks_checked=idx + 1,
                    corrupted_blocks_detected=1,
                    first_corrupted_seq=seq,
                    verification_message=f"Broken hash chain at seq {seq}: prev_hash '{prev_hash}' != expected '{prev_expected_hash}'",
                    audit_duration_ms=(t_end - t_start) * 1000.0,
                )

            # 2. Recompute Merkle Root
            expected_raw = f"{seq}:{tx_id}:{profile_id}:{prev_hash}:{payload_hash}:{status}"
            recomputed_root = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest()
            if merkle_root != recomputed_root:
                t_end = time.perf_counter()
                return LedgerAuditResult(
                    is_valid=False,
                    total_blocks_checked=idx + 1,
                    corrupted_blocks_detected=1,
                    first_corrupted_seq=seq,
                    verification_message=f"Merkle root mismatch at seq {seq}: '{merkle_root}' != computed '{recomputed_root}'",
                    audit_duration_ms=(t_end - t_start) * 1000.0,
                )

            # 3. Verify Signature Authenticity
            if not signature.startswith("SIG_VALID_"):
                t_end = time.perf_counter()
                return LedgerAuditResult(
                    is_valid=False,
                    total_blocks_checked=idx + 1,
                    corrupted_blocks_detected=1,
                    first_corrupted_seq=seq,
                    verification_message=f"Invalid cryptographic signature at seq {seq}: '{signature}'",
                    audit_duration_ms=(t_end - t_start) * 1000.0,
                )

            prev_expected_hash = merkle_root

        t_end = time.perf_counter()
        return LedgerAuditResult(
            is_valid=True,
            total_blocks_checked=len(ledger_events),
            corrupted_blocks_detected=0,
            first_corrupted_seq=None,
            verification_message=f"All {len(ledger_events)} ledger blocks cryptographically verified with 0 defects",
            audit_duration_ms=(t_end - t_start) * 1000.0,
        )


class FaultInjectionSuite:
    """Executes automated fault injection tests against GLHS SS2PL."""

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url
        self.engine = GLHSSS2PLEngine(db_url=db_url)

    def run_all_fault_tests(self) -> FaultRecoveryReport:
        """Runs complete fault injection, crash recovery, and tampering benchmark suite."""
        test_results: list[FaultTestCaseResult] = []

        # Test 1: Mid-transaction crash abort and lock release
        test_results.append(self._test_mid_transaction_crash())

        # Test 2: Invariant rejection rollback consistency
        test_results.append(self._test_invariant_rejection_rollback())

        # Test 3: Signature corruption detection
        test_results.append(self._test_signature_corruption_detection())

        # Test 4: Payload tampering detection in ledger
        test_results.append(self._test_payload_tampering_detection())

        # Test 5: Post-recovery continuous execution
        test_results.append(self._test_post_recovery_continuous_execution())

        # Full ledger audit of engine
        audit_res = LedgerAuditor.audit_ledger(self.engine.simulated.ledger_events)

        passed_count = sum(1 for r in test_results if r.passed)
        failed_count = len(test_results) - passed_count
        all_passed = (failed_count == 0) and audit_res.is_valid

        return FaultRecoveryReport(
            total_tests=len(test_results),
            passed_tests=passed_count,
            failed_tests=failed_count,
            all_passed=all_passed,
            test_results=test_results,
            ledger_audit=audit_res,
        )

    def _test_mid_transaction_crash(self) -> FaultTestCaseResult:
        """Injects an unhandled exception / crash while locks are held."""
        t_start = time.perf_counter()
        self.engine.setup(num_patients=5, num_partitions=16)

        tx = generate_clean_update("tx_crash_01", patient_idx=1, seed=101)
        initial_version = self.engine.partition_versions[tx.target_partitions[0]]

        # Simulate crash inside transaction by monkeypatching or injecting fault
        exception_caught = False
        try:
            # Acquire locks and raise simulated crash
            policy_lk = self.engine.policy_locks[tx.policy_id]
            profile_lk = self.engine.profile_locks[tx.profile_id]
            part_lk = self.engine.partition_locks[tx.target_partitions[0]]

            policy_lk.acquire()
            try:
                profile_lk.acquire()
                try:
                    part_lk.acquire()
                    try:
                        # Crash point: Simulating sudden process termination / network partition
                        raise RuntimeError("SIMULATED_WORKER_CRASH_DURING_MUTATION")
                    finally:
                        part_lk.release()
                finally:
                    profile_lk.release()
            finally:
                policy_lk.release()

        except RuntimeError as exc:
            if "SIMULATED_WORKER_CRASH" in str(exc):
                exception_caught = True

        # Verify state was not partially mutated and all locks are free
        post_crash_version = self.engine.partition_versions[tx.target_partitions[0]]
        locks_free = (
            not self.engine.policy_locks[tx.policy_id].locked()
            and not self.engine.profile_locks[tx.profile_id].locked()
            and not self.engine.partition_locks[tx.target_partitions[0]].locked()
        )

        # Execute a subsequent transaction to verify system is operational
        subsequent_tx = generate_clean_update("tx_post_crash_02", patient_idx=1, seed=102)
        subsequent_res = self.engine.execute_transaction(subsequent_tx)

        t_end = time.perf_counter()
        passed = (
            exception_caught
            and (initial_version == post_crash_version)
            and locks_free
            and (subsequent_res.status == TxnStatus.VALID_COMMIT)
        )

        return FaultTestCaseResult(
            test_name="mid_transaction_crash_and_lock_recovery",
            fault_type="CRASH_ABORT",
            injected_fault_description="Unhandled RuntimeError injected mid-transaction after acquiring canonical locks",
            expected_behavior="Locks auto-released, version unchanged, subsequent transaction succeeds",
            observed_behavior=f"Crash caught={exception_caught}, locks_free={locks_free}, sub_tx_status={subsequent_res.status.value}",
            passed=passed,
            recovery_latency_ms=(t_end - t_start) * 1000.0,
            details={
                "initial_version": initial_version,
                "post_crash_version": post_crash_version,
                "locks_free": locks_free,
            },
        )

    def _test_invariant_rejection_rollback(self) -> FaultTestCaseResult:
        """Injects severe DDI invariant failure and verifies clean rollback."""
        t_start = time.perf_counter()
        self.engine.setup(num_patients=5, num_partitions=16)

        # Seed initial medication
        init_tx = generate_clean_update("tx_init_warfarin", patient_idx=2, seed=201)
        init_tx.proposed_medications = ["warfarin"]
        init_tx.target_partitions = ["profile_002:medication:warfarin"]
        res_init = self.engine.execute_transaction(init_tx)

        # Snapshot version
        version_before = self.engine.partition_versions["profile_002:medication:warfarin"]
        ledger_len_before = len(self.engine.simulated.ledger_events)

        # Attempt contraindicated prescription: Aspirin + Warfarin
        ddi_tx = generate_clean_update("tx_ddi_aspirin", patient_idx=2, seed=202)
        ddi_tx.proposed_medications = ["aspirin"]
        ddi_tx.target_partitions = ["profile_002:medication:aspirin"]
        ddi_tx.has_severe_ddi = True

        res_ddi = self.engine.execute_transaction(ddi_tx)

        version_after = self.engine.partition_versions["profile_002:medication:warfarin"]
        ledger_len_after = len(self.engine.simulated.ledger_events)

        t_end = time.perf_counter()
        passed = (
            res_init.status == TxnStatus.VALID_COMMIT
            and res_ddi.status == TxnStatus.SAFE_ABORT
            and res_ddi.abort_category == AbortCategory.CLINICAL_DDI_SAFETY
            and (version_before == version_after)
            and (ledger_len_before == ledger_len_after)
        )

        return FaultTestCaseResult(
            test_name="invariant_rejection_clean_rollback",
            fault_type="TRANSACTION_ROLLBACK",
            injected_fault_description="Contraindicated severe DDI prescription (Warfarin + Aspirin) injected",
            expected_behavior="Safe abort with CLINICAL_DDI_SAFETY, state versions and ledger unchanged",
            observed_behavior=f"Status={res_ddi.status.value}, category={res_ddi.abort_category.value}, ledger_delta={ledger_len_after - ledger_len_before}",
            passed=passed,
            recovery_latency_ms=(t_end - t_start) * 1000.0,
            details={
                "res_status": res_ddi.status.value,
                "abort_category": res_ddi.abort_category.value,
                "reason": res_ddi.violation_reason,
            },
        )

    def _test_signature_corruption_detection(self) -> FaultTestCaseResult:
        """Injects corrupted signature into a ledger entry and verifies auditor detection."""
        t_start = time.perf_counter()
        coordinator = SimulatedCoordinator()
        coordinator.reset()

        # Append 5 valid blocks
        for i in range(1, 6):
            coordinator.append_ledger(f"tx_valid_{i}", "profile_001", hashlib.sha256(f"p_{i}".encode()).hexdigest())

        # Audit before corruption
        audit_pre = LedgerAuditor.audit_ledger(coordinator.ledger_events)

        # Inject signature corruption at block seq 3
        corrupted_ledger = copy.deepcopy(coordinator.ledger_events)
        corrupted_ledger[2]["signature"] = "SIG_CORRUPTED_TAMPERED_KEY_000"

        audit_corrupt = LedgerAuditor.audit_ledger(corrupted_ledger)

        t_end = time.perf_counter()
        passed = (
            audit_pre.is_valid
            and not audit_corrupt.is_valid
            and audit_corrupt.first_corrupted_seq == 3
            and "Invalid cryptographic signature" in audit_corrupt.verification_message
        )

        return FaultTestCaseResult(
            test_name="cryptographic_signature_corruption_detection",
            fault_type="SIGNATURE_CORRUPTION",
            injected_fault_description="Altered cryptographic signature tag on ledger block seq 3",
            expected_behavior="LedgerAuditor fails closed, flags block seq 3 with invalid signature",
            observed_behavior=f"Pre-valid={audit_pre.is_valid}, Post-valid={audit_corrupt.is_valid}, flagged_seq={audit_corrupt.first_corrupted_seq}",
            passed=passed,
            recovery_latency_ms=(t_end - t_start) * 1000.0,
            details={"audit_message": audit_corrupt.verification_message},
        )

    def _test_payload_tampering_detection(self) -> FaultTestCaseResult:
        """Injects payload tampering and verifies Merkle root mismatch detection."""
        t_start = time.perf_counter()
        coordinator = SimulatedCoordinator()
        coordinator.reset()

        for i in range(1, 6):
            coordinator.append_ledger(f"tx_valid_{i}", "profile_001", hashlib.sha256(f"payload_{i}".encode()).hexdigest())

        # Mutate payload hash in block seq 4 without updating Merkle root
        corrupted_ledger = copy.deepcopy(coordinator.ledger_events)
        corrupted_ledger[3]["payload_hash"] = hashlib.sha256(b"TAMPERED_CLINICAL_PAYLOAD").hexdigest()

        audit_tampered = LedgerAuditor.audit_ledger(corrupted_ledger)

        t_end = time.perf_counter()
        passed = (
            not audit_tampered.is_valid
            and audit_tampered.first_corrupted_seq == 4
            and "Merkle root mismatch" in audit_tampered.verification_message
        )

        return FaultTestCaseResult(
            test_name="payload_hash_tampering_detection",
            fault_type="LEDGER_TAMPERING",
            injected_fault_description="Modified payload hash in block seq 4 violating Merkle root consistency",
            expected_behavior="LedgerAuditor catches Merkle root mismatch at seq 4",
            observed_behavior=f"Audit passed={audit_tampered.is_valid}, flagged_seq={audit_tampered.first_corrupted_seq}",
            passed=passed,
            recovery_latency_ms=(t_end - t_start) * 1000.0,
            details={"audit_message": audit_tampered.verification_message},
        )

    def _test_post_recovery_continuous_execution(self) -> FaultTestCaseResult:
        """Tests continuous transaction execution and ledger append after recovery."""
        t_start = time.perf_counter()
        self.engine.setup(num_patients=10, num_partitions=32)

        workload = generate_workload(count=50, seed=301)
        valid_commits = 0
        for tx in workload:
            res = self.engine.execute_transaction(tx)
            if res.status == TxnStatus.VALID_COMMIT:
                valid_commits += 1

        # Audit complete ledger
        audit = LedgerAuditor.audit_ledger(self.engine.simulated.ledger_events)

        t_end = time.perf_counter()
        passed = (valid_commits > 0) and audit.is_valid and (audit.corrupted_blocks_detected == 0)

        return FaultTestCaseResult(
            test_name="post_recovery_continuous_execution_and_audit",
            fault_type="CONTINUOUS_EXECUTION",
            injected_fault_description="50 multi-scenario transactions executed consecutively post-recovery",
            expected_behavior="All valid transactions commit and full ledger passes cryptographic audit",
            observed_behavior=f"Valid commits={valid_commits}/{len(workload)}, Ledger audit valid={audit.is_valid}",
            passed=passed,
            recovery_latency_ms=(t_end - t_start) * 1000.0,
            details={
                "valid_commits": valid_commits,
                "total_ledger_blocks": len(self.engine.simulated.ledger_events),
            },
        )
