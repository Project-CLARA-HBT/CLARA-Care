"""Standard Two-Phase Locking (2PL) Baseline.

Locks entity partitions using traditional Two-Phase Locking without canonical lock hierarchy ordering.
Vulnerable to lock contention and deadlocks under concurrent multi-resource access.
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
    verify_clinical_safety_and_consent,
)
from evaluation.glhs_systems_benchmark.workload_generator import (
    SEVERE_DDI_PAIRS,
    ClinicalWorkloadItem,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore


class Standard2PLEngine(BaselineEngine):
    """Standard 2PL Engine locking entity partitions without canonical DAG hierarchy ordering."""

    def __init__(self, db_url: str | None = None, enable_random_lock_order: bool = False) -> None:
        super().__init__(db_url)
        self.lock = threading.RLock()
        self.policy_epochs: dict[str, int] = {"glhs_policy_v1": 1}
        self.consent_epochs: dict[str, int] = defaultdict(lambda: 1)
        self.partition_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.partition_versions: dict[str, int] = defaultdict(lambda: 1)
        self.active_medications: dict[str, set[str]] = defaultdict(set)
        self.ddi_pairs = [frozenset(pair) for pair in SEVERE_DDI_PAIRS]
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
                            CREATE TABLE IF NOT EXISTS glhs_policy_anchors (
                                policy_id VARCHAR(64) PRIMARY KEY,
                                epoch INT NOT NULL DEFAULT 1,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS glhs_profile_consent_anchors (
                                profile_id VARCHAR(64) PRIMARY KEY,
                                consent_epoch INT NOT NULL DEFAULT 1,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                        """)
            except Exception:
                self.is_postgres = False

    def reset(self) -> None:
        with self.lock:
            self.policy_epochs = {"glhs_policy_v1": 1}
            self.consent_epochs.clear()
            self.partition_locks.clear()
            self.partition_versions.clear()
            self.active_medications.clear()
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
        """Executes 2PL in PostgreSQL with entity partition locking."""
        if not self.db_url:
            return self._execute_simulated_2pl(tx, t_start)
        try:
            with psycopg.connect(self.db_url) as conn:
                conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                with conn.cursor(row_factory=dict_row) as cur:
                    # 1. Read Policy and Consent anchors
                    cur.execute(
                        "SELECT policy_id, epoch FROM glhs_policy_anchors WHERE policy_id = %s",
                        (tx.policy_id,),
                    )
                    p_row = cur.fetchone()
                    curr_policy_epoch = p_row["epoch"] if p_row else 1

                    cur.execute(
                        "SELECT profile_id, consent_epoch FROM glhs_profile_consent_anchors WHERE profile_id = %s",
                        (tx.profile_id,),
                    )
                    c_row = cur.fetchone()
                    curr_consent_epoch = c_row["consent_epoch"] if c_row else 1

                    # 2. Lock entity partitions (unordered acquisition)
                    partitions = list(tx.target_partitions)
                    if self.enable_random_lock_order and len(partitions) > 1:
                        random.shuffle(partitions)

                    for pid in partitions:
                        cur.execute(
                            "SELECT partition_id, version FROM benchmark_std2pl_partitions WHERE partition_id = %s FOR UPDATE",
                            (pid,),
                        )

                    # 3. Normalized application verification & clinical safety check
                    ok, status, abort_cat, reason = verify_clinical_safety_and_consent(
                        tx=tx,
                        current_policy_epoch=curr_policy_epoch,
                        current_consent_epoch=curr_consent_epoch,
                        active_medications=list(self.active_medications[tx.profile_id]),
                        ddi_pairs=self.ddi_pairs,
                    )
                    if not ok:
                        conn.rollback()
                        t_end = time.perf_counter()
                        return TxnResult(
                            workload_id=tx.workload_id,
                            status=status,
                            abort_category=abort_cat,
                            latency_ms=(t_end - t_start) * 1000.0,
                            violation_reason=reason,
                        )

                    for pid in partitions:
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

        # 1. Normalized application verification & clinical safety check
        curr_policy_epoch = self.policy_epochs.get(tx.policy_id, 1)
        curr_consent_epoch = self.consent_epochs[tx.profile_id]

        ok, status, abort_cat, reason = verify_clinical_safety_and_consent(
            tx=tx,
            current_policy_epoch=curr_policy_epoch,
            current_consent_epoch=curr_consent_epoch,
            active_medications=list(self.active_medications[tx.profile_id]),
            ddi_pairs=self.ddi_pairs,
        )
        if not ok:
            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=status,
                abort_category=abort_cat,
                latency_ms=(t_end - t_start) * 1000.0,
                violation_reason=reason,
            )

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

            # Valid Commit
            for p in partitions:
                self.partition_versions[p] += 1
            for med in tx.proposed_medications:
                self.active_medications[tx.profile_id].add(med.strip().lower())

            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.VALID_COMMIT,
                latency_ms=(t_end - t_start) * 1000.0,
            )

        finally:
            for lk in reversed(acquired_locks):
                lk.release()
