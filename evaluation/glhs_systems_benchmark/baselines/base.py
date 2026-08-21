"""Base Interfaces, Telemetry Models, and Database Adapters for Concurrency Baselines."""

from __future__ import annotations

import abc
import enum
import hashlib
import os
import statistics
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from evaluation.glhs_systems_benchmark.workload_generator import (
    ClinicalWorkloadItem,
)


class TxnStatus(enum.StrEnum):
    """Status of a benchmark transaction execution."""

    VALID_COMMIT = "valid_commit"
    SAFE_ABORT = "safe_abort"
    UNSAFE_COMMIT = "unsafe_commit"
    ERROR = "error"


class AbortCategory(enum.StrEnum):
    """Detailed classification of transaction aborts."""

    NONE = "none"
    TRUE_STALE = "true_stale"
    FALSE_STALE = "false_stale"
    GOVERNANCE_REVOCATION = "governance_revocation"
    CLINICAL_DDI_SAFETY = "clinical_ddi_safety"
    SERIALIZATION_FAILURE = "serialization_failure"
    DEADLOCK = "deadlock"


class UnsafeCommitCategory(enum.StrEnum):
    """Classification of unsafe transaction commits (invariant violations)."""

    NONE = "none"
    TOCTOU_VIOLATION = "toctou_violation"
    DDI_LEAK = "ddi_leak"


@dataclass
class TxnResult:
    """Individual transaction execution result telemetry."""

    workload_id: str
    status: TxnStatus
    abort_category: AbortCategory = AbortCategory.NONE
    unsafe_category: UnsafeCommitCategory = UnsafeCommitCategory.NONE
    latency_ms: float = 0.0
    retries: int = 0
    violation_reason: str | None = None
    merkle_root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "status": self.status.value,
            "abort_category": self.abort_category.value,
            "unsafe_category": self.unsafe_category.value,
            "latency_ms": round(self.latency_ms, 4),
            "retries": self.retries,
            "violation_reason": self.violation_reason,
            "merkle_root": self.merkle_root,
        }


@dataclass
class BaselineMetrics:
    """Aggregated performance & safety metrics for a baseline paradigm."""

    paradigm: str
    total_tx: int
    valid_commits: int
    safe_aborts: int
    unsafe_commits: int
    errors: int
    true_stale_aborts: int
    false_stale_aborts: int
    safe_governance_aborts: int
    safe_ddi_aborts: int
    toctou_violations: int
    ddi_leaks: int
    deadlocks: int
    throughput_tps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    unsafe_commit_rate: float
    false_stale_rate: float
    true_stale_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "paradigm": self.paradigm,
            "total_tx": self.total_tx,
            "valid_commits": self.valid_commits,
            "safe_aborts": self.safe_aborts,
            "unsafe_commits": self.unsafe_commits,
            "errors": self.errors,
            "true_stale_aborts": self.true_stale_aborts,
            "false_stale_aborts": self.false_stale_aborts,
            "safe_governance_aborts": self.safe_governance_aborts,
            "safe_ddi_aborts": self.safe_ddi_aborts,
            "toctou_violations": self.toctou_violations,
            "ddi_leaks": self.ddi_leaks,
            "deadlocks": self.deadlocks,
            "throughput_tps": round(self.throughput_tps, 2),
            "latencies_ms": {
                "mean": round(self.mean_latency_ms, 3),
                "p50": round(self.p50_latency_ms, 3),
                "p95": round(self.p95_latency_ms, 3),
                "p99": round(self.p99_latency_ms, 3),
                "min": round(self.min_latency_ms, 3),
                "max": round(self.max_latency_ms, 3),
            },
            "unsafe_commit_rate": round(self.unsafe_commit_rate, 4),
            "false_stale_rate": round(self.false_stale_rate, 4),
            "true_stale_rate": round(self.true_stale_rate, 4),
        }


def compute_metrics(paradigm: str, results: Sequence[TxnResult], elapsed_seconds: float) -> BaselineMetrics:
    """Aggregate individual transaction results into comprehensive benchmark metrics."""
    total = len(results)
    if total == 0:
        return BaselineMetrics(
            paradigm=paradigm,
            total_tx=0,
            valid_commits=0,
            safe_aborts=0,
            unsafe_commits=0,
            errors=0,
            true_stale_aborts=0,
            false_stale_aborts=0,
            safe_governance_aborts=0,
            safe_ddi_aborts=0,
            toctou_violations=0,
            ddi_leaks=0,
            deadlocks=0,
            throughput_tps=0.0,
            mean_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            p99_latency_ms=0.0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            unsafe_commit_rate=0.0,
            false_stale_rate=0.0,
            true_stale_rate=0.0,
        )

    valid_commits = sum(1 for r in results if r.status == TxnStatus.VALID_COMMIT)
    safe_aborts = sum(1 for r in results if r.status == TxnStatus.SAFE_ABORT)
    unsafe_commits = sum(1 for r in results if r.status == TxnStatus.UNSAFE_COMMIT)
    errors = sum(1 for r in results if r.status == TxnStatus.ERROR)

    true_stale = sum(1 for r in results if r.abort_category == AbortCategory.TRUE_STALE)
    false_stale = sum(1 for r in results if r.abort_category == AbortCategory.FALSE_STALE)
    safe_gov = sum(1 for r in results if r.abort_category == AbortCategory.GOVERNANCE_REVOCATION)
    safe_ddi = sum(1 for r in results if r.abort_category == AbortCategory.CLINICAL_DDI_SAFETY)
    deadlocks = sum(1 for r in results if r.abort_category == AbortCategory.DEADLOCK)

    toctou_violations = sum(1 for r in results if r.unsafe_category == UnsafeCommitCategory.TOCTOU_VIOLATION)
    ddi_leaks = sum(1 for r in results if r.unsafe_category == UnsafeCommitCategory.DDI_LEAK)

    latencies = [r.latency_ms for r in results]
    latencies.sort()
    mean_lat = statistics.mean(latencies) if latencies else 0.0
    min_lat = latencies[0] if latencies else 0.0
    max_lat = latencies[-1] if latencies else 0.0

    p50_idx = int(0.50 * (len(latencies) - 1))
    p95_idx = int(0.95 * (len(latencies) - 1))
    p99_idx = int(0.99 * (len(latencies) - 1))

    p50_lat = latencies[p50_idx] if latencies else 0.0
    p95_lat = latencies[p95_idx] if latencies else 0.0
    p99_lat = latencies[p99_idx] if latencies else 0.0

    effective_elapsed = max(1e-6, elapsed_seconds)
    tps = total / effective_elapsed

    return BaselineMetrics(
        paradigm=paradigm,
        total_tx=total,
        valid_commits=valid_commits,
        safe_aborts=safe_aborts,
        unsafe_commits=unsafe_commits,
        errors=errors,
        true_stale_aborts=true_stale,
        false_stale_aborts=false_stale,
        safe_governance_aborts=safe_gov,
        safe_ddi_aborts=safe_ddi,
        toctou_violations=toctou_violations,
        ddi_leaks=ddi_leaks,
        deadlocks=deadlocks,
        throughput_tps=tps,
        mean_latency_ms=mean_lat,
        p50_latency_ms=p50_lat,
        p95_latency_ms=p95_lat,
        p99_latency_ms=p99_lat,
        min_latency_ms=min_lat,
        max_latency_ms=max_lat,
        unsafe_commit_rate=unsafe_commits / total,
        false_stale_rate=false_stale / total,
        true_stale_rate=true_stale / total,
    )


# ---------------------------------------------------------------------------
# Simulated Coordinator for Zero-Dependency & Fast In-Memory Operations
# ---------------------------------------------------------------------------


class SimulatedCoordinator:
    """Thread-safe in-memory transactional coordinator and state store."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.policy_epochs: dict[str, int] = {"glhs_policy_v1": 1}
        self.profile_consent_epochs: dict[str, int] = {}
        self.partition_versions: dict[str, int] = {}
        self.partition_data: dict[str, dict[str, Any]] = {}
        self.active_patient_medications: dict[str, set[str]] = {}
        self.ledger_events: list[dict[str, Any]] = []
        self.resource_locks: dict[str, threading.Lock] = {}
        self._genesis_hash = hashlib.sha256(b"GLHS_GENESIS_STATE").hexdigest()

    def get_resource_lock(self, key: str) -> threading.Lock:
        with self.lock:
            if key not in self.resource_locks:
                self.resource_locks[key] = threading.Lock()
            return self.resource_locks[key]

    def reset(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        with self.lock:
            self.policy_epochs = {"glhs_policy_v1": 1}
            self.profile_consent_epochs.clear()
            self.partition_versions.clear()
            self.partition_data.clear()
            self.active_patient_medications.clear()
            self.ledger_events.clear()
            self.resource_locks.clear()

            # Initialize standard patient profiles
            for p in range(1, num_patients + 1):
                prof_id = f"profile_{p:03d}"
                self.profile_consent_epochs[prof_id] = 1
                self.active_patient_medications[prof_id] = set()

            # Initialize disjoint profiles
            for part_idx in range(num_partitions):
                prof_id = f"profile_disjoint_{part_idx:03d}"
                self.profile_consent_epochs[prof_id] = 1
                slot = f"slot_{part_idx:03d}"
                key = f"{prof_id}:partition:{slot}"
                self.partition_versions[key] = 1
                self.partition_data[key] = {"value": 0}

    def append_ledger(
        self,
        tx_id: str,
        profile_id: str,
        payload_hash: str,
        status: str = "COMMITTED",
        corrupt_signature: bool = False,
    ) -> str:
        with self.lock:
            seq = len(self.ledger_events) + 1
            prev_hash = self.ledger_events[-1]["merkle_root"] if self.ledger_events else self._genesis_hash
            raw_block = f"{seq}:{tx_id}:{profile_id}:{prev_hash}:{payload_hash}:{status}"
            merkle_root = hashlib.sha256(raw_block.encode("utf-8")).hexdigest()
            sig = (
                f"SIG_CORRUPTED_{merkle_root[:16]}"
                if corrupt_signature
                else f"SIG_VALID_{hashlib.sha256((merkle_root + 'SECRET').encode()).hexdigest()[:16]}"
            )
            event = {
                "seq_num": seq,
                "tx_id": tx_id,
                "profile_id": profile_id,
                "merkle_root": merkle_root,
                "signature": sig,
                "prev_hash": prev_hash,
                "payload_hash": payload_hash,
                "status": status,
                "created_at": datetime.now(UTC).isoformat(),
            }
            self.ledger_events.append(event)
            return merkle_root


# ---------------------------------------------------------------------------
# Base Baseline Engine Contract
# ---------------------------------------------------------------------------


class BaselineEngine(abc.ABC):
    """Abstract interface for all transactional concurrency baselines."""

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        self.simulated = SimulatedCoordinator()
        self.is_postgres = bool(
            self.db_url and ("postgresql" in self.db_url or "postgres" in self.db_url)
        )

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Display name of the baseline paradigm."""
        ...

    @abc.abstractmethod
    def setup(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        """Initialize database tables or state before benchmark execution."""
        ...

    @abc.abstractmethod
    def execute_transaction(self, tx: ClinicalWorkloadItem) -> TxnResult:
        """Executes a single clinical transaction under this paradigm's concurrency semantics."""
        ...

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset state between experimental runs."""
        ...

    def teardown(self) -> None:
        """Clean up any database connections or locks."""
        self.reset()
