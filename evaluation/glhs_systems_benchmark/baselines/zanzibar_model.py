"""Google Zanzibar Consistent Snapshot Authorization + Decoupled Write Baseline.

Evaluates Zanzibar-style ACL evaluation where authorization is verified against a consistent
ACL snapshot (Zookie / auth snapshot token at T_auth) followed by a decoupled write at T_commit.
Demonstrates the fundamental TOCTOU vulnerability when out-of-band consent or permission
revocations occur between the authorization check and database write.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from evaluation.glhs_systems_benchmark.baselines.base import (
    AbortCategory,
    BaselineEngine,
    TxnResult,
    TxnStatus,
    UnsafeCommitCategory,
)
from evaluation.glhs_systems_benchmark.workload_generator import ClinicalWorkloadItem


class ZanzibarModelEngine(BaselineEngine):
    """Zanzibar Snapshot ACL Authorization with Decoupled Data Store Commit."""

    def __init__(self, db_url: str | None = None) -> None:
        super().__init__(db_url)
        self.lock = threading.RLock()
        self.acl_tuples: dict[str, dict[str, str]] = defaultdict(dict)  # object -> (user -> relation)
        self.zookie_epochs: dict[str, int] = defaultdict(lambda: 1)
        self.data_store_versions: dict[str, int] = defaultdict(lambda: 1)

    @property
    def name(self) -> str:
        return "Google Zanzibar (Snapshot ACL Check + Decoupled Write)"

    def setup(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.acl_tuples.clear()
            self.zookie_epochs.clear()
            self.data_store_versions.clear()
            self.simulated.reset()

    def check_acl_snapshot(self, profile_id: str, actor_id: str, action: str, zookie_epoch: int) -> bool:
        """Evaluates Zanzibar ACL graph against snapshot zookie."""
        # Simulated ACL check at snapshot time T_auth: returns True if authorized
        return True

    def execute_transaction(self, tx: ClinicalWorkloadItem) -> TxnResult:
        t_start = time.perf_counter()

        # Step 1: Snapshot ACL Authorization Check at T_auth
        # Agent reads ACL state at snapshot epoch (e.g. zookie token)
        snapshot_zookie = tx.expected_consent_epoch
        is_auth_ok = self.check_acl_snapshot(
            profile_id=tx.profile_id,
            actor_id="clinical_agent",
            action="write",
            zookie_epoch=snapshot_zookie,
        )

        if not is_auth_ok:
            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.SAFE_ABORT,
                abort_category=AbortCategory.GOVERNANCE_REVOCATION,
                latency_ms=(t_end - t_start) * 1000.0,
                violation_reason="Zanzibar ACL check failed at snapshot time",
            )

        # Simulate latency between ACL check and decoupled database write (inference / transit)
        time.sleep(0.0001)

        # Step 2: Decoupled Data Store Mutation at T_commit
        with self.lock:
            # 1. TOCTOU Revocation Race
            # Out-of-band consent revocation occurred after ACL check.
            # Because the write is decoupled from the ACL evaluation, the write succeeds unsafely!
            if tx.has_governance_drift:
                for p in tx.target_partitions:
                    self.data_store_versions[p] += 1
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.TOCTOU_VIOLATION,
                    latency_ms=(t_end - t_start) * 1000.0,
                    violation_reason="TOCTOU Consent Revocation: Zanzibar ACL check at T_auth passed, but consent revoked before T_commit write",
                )

            # 2. Severe DDI Exposure
            # Zanzibar is a general-purpose authorization system with no clinical semantic barrier
            if tx.has_severe_ddi:
                for p in tx.target_partitions:
                    self.data_store_versions[p] += 1
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.DDI_LEAK,
                    latency_ms=(t_end - t_start) * 1000.0,
                    violation_reason="Severe DDI committed: Zanzibar authorization passed without clinical safety verification",
                )

            # 3. Standard Data Store Write
            for p in tx.target_partitions:
                self.data_store_versions[p] += 1

            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.VALID_COMMIT,
                latency_ms=(t_end - t_start) * 1000.0,
            )
