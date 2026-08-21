"""Standard Two-Phase Locking (2PL) Baseline.

Locks entity partitions without governance anchors (PolicyAnchor or ProfileAndConsentAnchor).
Lacks the Layer 1 Deterministic Clinical Safety Barrier, allowing TOCTOU drift and severe DDI leaks,
and is vulnerable to lock acquisition ordering deadlocks.
"""

from __future__ import annotations

import random
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

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore


class Standard2PLEngine(BaselineEngine):
    """Standard 2PL Engine locking only entity partitions without governance anchors."""

    def __init__(self, db_url: str | None = None, enable_random_lock_order: bool = False) -> None:
        super().__init__(db_url)
        self.lock = threading.RLock()
        self.partition_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.partition_versions: dict[str, int] = defaultdict(lambda: 1)
        self.enable_random_lock_order = enable_random_lock_order

    @property
    def name(self) -> str:
        return "Standard 2PL (Entity Partition Locking without Governance Anchors)"

    def setup(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        self.reset()
        if self.is_postgres and psycopg and self.db_url:
            try:
                with psycopg.connect(self.db_url, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS benchmark_std2pl_partitions (
                                partition_id VARCHAR(128) PRIMARY KEY,
                                profile_id VARCHAR(64) NOT NULL,
                                version INT NOT NULL DEFAULT 1,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                        """)
            except Exception:
                self.is_postgres = False

    def reset(self) -> None:
        with self.lock:
            self.partition_locks.clear()
            self.partition_versions.clear()
            self.simulated.reset()

    def execute_transaction(self, tx: ClinicalWorkloadItem) -> TxnResult:
        t_start = time.perf_counter()

        if self.is_postgres and psycopg and self.db_url:
            try:
                return self._execute_postgres_2pl(tx, t_start)
            except Exception:
                return self._execute_simulated_2pl(tx, t_start)
        else:
            return self._execute_simulated_2pl(tx, t_start)

    def _execute_postgres_2pl(self, tx: ClinicalWorkloadItem, t_start: float) -> TxnResult:
        """Executes 2PL in PostgreSQL without governance anchors."""
        if not self.db_url:
            return self._execute_simulated_2pl(tx, t_start)
        try:
            with psycopg.connect(self.db_url) as conn:
                conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                with conn.cursor(row_factory=dict_row) as cur:
                    # Lock entity partitions (unordered)
                    for pid in tx.target_partitions:
                        cur.execute(
                            "SELECT partition_id, version FROM benchmark_std2pl_partitions WHERE partition_id = %s FOR UPDATE",
                            (pid,),
                        )

                    # TOCTOU governance drift passes through because 2PL lacks governance anchors
                    if tx.has_governance_drift:
                        conn.commit()
                        t_end = time.perf_counter()
                        return TxnResult(
                            workload_id=tx.workload_id,
                            status=TxnStatus.UNSAFE_COMMIT,
                            unsafe_category=UnsafeCommitCategory.TOCTOU_VIOLATION,
                            latency_ms=(t_end - t_start) * 1000.0,
                            violation_reason="TOCTOU consent drift committed unsafely (missing ProfileAndConsentAnchor)",
                        )

                    # Severe DDI passes through because standard 2PL lacks clinical DDI barrier
                    if tx.has_severe_ddi:
                        conn.commit()
                        t_end = time.perf_counter()
                        return TxnResult(
                            workload_id=tx.workload_id,
                            status=TxnStatus.UNSAFE_COMMIT,
                            unsafe_category=UnsafeCommitCategory.DDI_LEAK,
                            latency_ms=(t_end - t_start) * 1000.0,
                            violation_reason="Severe DDI committed unsafely (missing Layer 1 Clinical Barrier)",
                        )

                    for pid in tx.target_partitions:
                        cur.execute("""
                            INSERT INTO benchmark_std2pl_partitions (partition_id, profile_id, version, updated_at)
                            VALUES (%s, %s, 1, NOW())
                            ON CONFLICT (partition_id) DO UPDATE SET version = benchmark_std2pl_partitions.version + 1, updated_at = NOW();
                        """, (pid, tx.profile_id))

                    conn.commit()
                    t_end = time.perf_counter()
                    return TxnResult(
                        workload_id=tx.workload_id,
                        status=TxnStatus.VALID_COMMIT,
                        latency_ms=(t_end - t_start) * 1000.0,
                    )
        except Exception as exc:
            t_end = time.perf_counter()
            # If deadlock occurred in PostgreSQL (SQLSTATE 40P01)
            is_deadlock = "deadlock" in str(exc).lower() or "40p01" in str(exc).lower()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.SAFE_ABORT if is_deadlock else TxnStatus.ERROR,
                abort_category=AbortCategory.DEADLOCK if is_deadlock else AbortCategory.NONE,
                latency_ms=(t_end - t_start) * 1000.0,
                violation_reason=f"Standard 2PL lock failure: {exc}",
            )

    def _execute_simulated_2pl(self, tx: ClinicalWorkloadItem, t_start: float) -> TxnResult:
        """Simulates 2PL lock acquisition over entity partitions."""
        partitions = list(tx.target_partitions)
        if self.enable_random_lock_order and len(partitions) > 1:
            random.shuffle(partitions)

        acquired_locks: list[threading.Lock] = []
        try:
            for p in partitions:
                lk = self.partition_locks[p]
                # Non-blocking with timeout to detect simulated deadlocks
                acquired = lk.acquire(timeout=0.20)
                if not acquired:
                    t_end = time.perf_counter()
                    return TxnResult(
                        workload_id=tx.workload_id,
                        status=TxnStatus.SAFE_ABORT,
                        abort_category=AbortCategory.DEADLOCK,
                        latency_ms=(t_end - t_start) * 1000.0,
                        violation_reason="Standard 2PL lock acquisition timeout (potential deadlock cycle)",
                    )
                acquired_locks.append(lk)

            # 1. TOCTOU Revocation Race (No governance anchor)
            if tx.has_governance_drift:
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.TOCTOU_VIOLATION,
                    latency_ms=(t_end - t_start) * 1000.0,
                    violation_reason="TOCTOU consent drift passed 2PL without governance anchor check",
                )

            # 2. Severe DDI (No clinical barrier)
            if tx.has_severe_ddi:
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.DDI_LEAK,
                    latency_ms=(t_end - t_start) * 1000.0,
                    violation_reason="Severe DDI passed Standard 2PL without clinical safety gate",
                )

            # 3. Valid Commit
            for p in partitions:
                self.partition_versions[p] += 1

            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.VALID_COMMIT,
                latency_ms=(t_end - t_start) * 1000.0,
            )

        finally:
            for lk in reversed(acquired_locks):
                lk.release()
