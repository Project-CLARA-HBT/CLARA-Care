"""Standard Optimistic Concurrency Control (OCC) Baseline.

Implements naive OCC with snapshot reads, commit-time version validation, and retry loops.
Lacks Layer 1 Deterministic Clinical Safety Barrier and external governance epoch bindings.
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


class StandardOCCEngine(BaselineEngine):
    """Naive Optimistic Concurrency Control (OCC) with Commit-Time Validation & Retry Loops."""

    def __init__(self, db_url: str | None = None, max_retries: int = 3) -> None:
        super().__init__(db_url)
        self.lock = threading.RLock()
        self.partition_versions: dict[str, int] = defaultdict(lambda: 1)
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "Standard OCC (Naive Optimistic Concurrency with Retries)"

    def setup(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.partition_versions.clear()
            self.simulated.reset()

    def execute_transaction(self, tx: ClinicalWorkloadItem) -> TxnResult:
        t_start = time.perf_counter()
        retries = 0

        while retries <= self.max_retries:
            # 1. Read Phase (No locks held)
            with self.lock:
                snapshot_versions = {p: self.partition_versions[p] for p in tx.target_partitions}

            # Simulate agent reasoning / compute latency
            time.sleep(0.0001)

            # 2. TOCTOU Governance Revocation (OCC lacks external governance check)
            if tx.has_governance_drift:
                with self.lock:
                    for p in tx.target_partitions:
                        self.partition_versions[p] += 1
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.TOCTOU_VIOLATION,
                    latency_ms=(t_end - t_start) * 1000.0,
                    retries=retries,
                    violation_reason="TOCTOU consent drift not included in OCC read-set validation",
                )

            # 3. Severe DDI Exposure (OCC lacks clinical safety barrier)
            if tx.has_severe_ddi:
                with self.lock:
                    for p in tx.target_partitions:
                        self.partition_versions[p] += 1
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=TxnStatus.UNSAFE_COMMIT,
                    unsafe_category=UnsafeCommitCategory.DDI_LEAK,
                    latency_ms=(t_end - t_start) * 1000.0,
                    retries=retries,
                    violation_reason="Severe DDI committed in OCC transaction without clinical barrier",
                )

            # 4. Validation & Commit Phase
            with self.lock:
                conflict = False
                for p, expected_ver in snapshot_versions.items():
                    if self.partition_versions[p] != expected_ver:
                        conflict = True
                        break

                if not conflict:
                    # Atomic commit
                    for p in tx.target_partitions:
                        self.partition_versions[p] += 1
                    t_end = time.perf_counter()
                    return TxnResult(
                        workload_id=tx.workload_id,
                        status=TxnStatus.VALID_COMMIT,
                        latency_ms=(t_end - t_start) * 1000.0,
                        retries=retries,
                    )

            # Conflict encountered -> Retry with backoff
            retries += 1
            if retries <= self.max_retries:
                # Exponential backoff with jitter
                backoff = (0.0005 * (2**retries)) + random.uniform(0.0001, 0.0005)
                time.sleep(backoff)

        # Exhausted retries
        t_end = time.perf_counter()
        return TxnResult(
            workload_id=tx.workload_id,
            status=TxnStatus.SAFE_ABORT,
            abort_category=AbortCategory.TRUE_STALE,
            latency_ms=(t_end - t_start) * 1000.0,
            retries=retries,
            violation_reason="OCC Validation failed: partition modified by concurrent transaction (max retries exhausted)",
        )
