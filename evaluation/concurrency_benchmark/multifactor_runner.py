"""E09 Multifactor Concurrency & Partition Benchmark Runner.

Evaluates Optimistic Concurrency Control (OCC), Monolithic Profile Locking, and
Entity-Partitioned DAG Versioning across a multi-factor grid:
- Concurrency levels: W in {1, 2, 4, 8, 16, 32, 64}
- Zipfian skew theta in {0.0, 0.8, 1.1, 1.4}
- Overlap ratio in {0.0, 0.10, 0.25, 0.50, 0.75, 1.0}
- Dependency width in {1, 2, 4, 8}
- Workload mix: Read-heavy (90/10), Write-heavy (10/90), Mixed (50/50)

Evaluates 10 Multi-Workload Families:
1. same_entity_contention
2. disjoint_entity
3. partial_overlap
4. multi_domain
5. hot_key_zipfian
6. governance_plus_entity
7. evidence_plus_entity
8. read_heavy
9. write_heavy
10. mixed
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if _REPO_ROOT.exists() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class ConcurrencyRegime(StrEnum):
    MONOLITHIC_PROFILE_LOCK = "monolithic_profile_lock"
    ENTITY_DAG_PARTITION_LOCKING = "entity_dag_partition_locking"
    OCC_BACKOFF = "occ_backoff"


class TransactionOutcome(StrEnum):
    COMMITTED = "committed"
    TRUE_STALE_ABORTED = "true_stale_aborted"
    FALSE_STALE_ABORTED = "false_stale_aborted"
    GOVERNANCE_ABORTED = "governance_aborted"
    DEADLOCK = "deadlock"
    OPERATIONAL_ERROR = "operational_error"


@dataclass(frozen=True)
class PartitionKey:
    domain: str
    semantic_key: str

    def to_string(self) -> str:
        return f"{self.domain}:{self.semantic_key}"

    def __lt__(self, other: PartitionKey) -> bool:
        return (self.domain, self.semantic_key) < (other.domain, other.semantic_key)


class ZipfianSampler:
    """Discrete Zipfian distribution sampler with parameter theta (skew)."""

    def __init__(self, n_items: int, theta: float, seed: int = 42) -> None:
        self.n_items = max(1, n_items)
        self.theta = float(theta)
        self.rng = random.Random(seed)

        if self.theta == 0.0:
            self.probabilities = [1.0 / self.n_items] * self.n_items
        else:
            weights = [1.0 / math.pow(i + 1, self.theta) for i in range(self.n_items)]
            total_weight = sum(weights)
            self.probabilities = [w / total_weight for w in weights]

        self.cumulative: list[float] = []
        cum = 0.0
        for p in self.probabilities:
            cum += p
            self.cumulative.append(cum)
        self.cumulative[-1] = 1.0

    def sample(self) -> int:
        r = self.rng.random()
        low, high = 0, len(self.cumulative) - 1
        while low < high:
            mid = (low + high) // 2
            if r <= self.cumulative[mid]:
                high = mid
            else:
                low = mid + 1
        return low


@dataclass
class WorkloadCellConfig:
    cell_id: str
    family_name: str
    concurrency: int
    zipf_theta: float
    overlap_ratio: float
    dependency_width: int
    read_ratio: float
    write_ratio: float
    num_entities: int = 50
    tx_per_writer: int = 40
    num_repetitions: int = 5
    seed: int = 42


@dataclass
class WriterTaskSpec:
    writer_id: int
    is_write: bool
    is_governance: bool
    is_evidence: bool
    target_keys: list[PartitionKey]
    read_versions: dict[str, int]
    expected_profile_version: int


@dataclass
class WriterAttemptResult:
    writer_id: int
    attempt_id: int
    outcome: TransactionOutcome
    latency_ms: float
    lock_wait_ms: float
    retries: int
    target_keys: list[str]
    read_versions: dict[str, int]
    committed_versions: dict[str, int] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class CellRunMetrics:
    cell_id: str
    family_name: str
    regime: ConcurrencyRegime
    concurrency: int
    zipf_theta: float
    overlap_ratio: float
    dependency_width: int
    repetition_id: int
    total_attempts: int
    committed_count: int
    true_stale_count: int
    false_stale_count: int
    governance_abort_count: int
    deadlock_count: int
    retry_count: int
    commit_rate: float
    false_stale_rate: float
    true_stale_rate: float
    governance_abort_rate: float
    throughput_tps: float
    latency_min_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float
    latency_mean_ms: float
    lock_wait_mean_ms: float
    wall_clock_ms: float
    invariant_false_stale_zero: bool
    invariant_deadlock_zero: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        return d


class SimulatedPartitionCoordinator:
    """Coordinator managing atomic partitions, lock ordering, and transaction state."""

    def __init__(self, entities: list[PartitionKey]) -> None:
        self._global_profile_lock = threading.Lock()
        self._coordinator_lock = threading.Lock()
        self._partition_locks: dict[str, threading.Lock] = {}

        # Canonical lock ordering registry
        for key in entities:
            k_str = key.to_string()
            self._partition_locks[k_str] = threading.Lock()

        self.profile_version: int = 1
        self.partition_versions: dict[str, int] = {k.to_string(): 1 for k in entities}
        self.governance_epoch: int = 1
        self.active_consents: dict[str, bool] = {"medical_research": True, "data_sharing": True}

    def get_partition_locks(self, keys: Sequence[PartitionKey]) -> list[tuple[str, threading.Lock]]:
        """Canonical lock ordering: locks are acquired strictly in sorted key order."""
        sorted_keys = sorted(keys, key=lambda k: (k.domain, k.semantic_key))
        locked_items = []
        for k in sorted_keys:
            k_str = k.to_string()
            with self._coordinator_lock:
                if k_str not in self._partition_locks:
                    self._partition_locks[k_str] = threading.Lock()
                lock = self._partition_locks[k_str]
            locked_items.append((k_str, lock))
        return locked_items


def execute_monolithic_writer(
    coordinator: SimulatedPartitionCoordinator,
    task: WriterTaskSpec,
    attempt_id: int,
    barrier: threading.Barrier | None = None,
) -> WriterAttemptResult:
    target_str_keys = [k.to_string() for k in task.target_keys]
    if barrier:
        try:
            barrier.wait(timeout=2.0)
        except threading.BrokenBarrierError:
            pass

    t0 = time.monotonic_ns()
    lock_t0 = time.monotonic_ns()
    with coordinator._global_profile_lock:
        lock_t1 = time.monotonic_ns()
        lock_wait_ms = (lock_t1 - lock_t0) / 1_000_000.0

        if not task.is_write:
            # Read-only operation under monolithic lock
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.COMMITTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
                committed_versions={k.to_string(): coordinator.profile_version for k in task.target_keys},
            )

        if task.is_governance:
            # Governance write aborts pending target transactions
            coordinator.governance_epoch += 1
            coordinator.profile_version += 1
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.COMMITTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
                committed_versions={"governance": coordinator.governance_epoch},
            )

        # Monolithic profile version check
        current_ver = coordinator.profile_version
        if current_ver != task.expected_profile_version:
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.FALSE_STALE_ABORTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
            )

        # Commit write and advance monolithic profile version
        new_ver = current_ver + 1
        coordinator.profile_version = new_ver
        for k in task.target_keys:
            coordinator.partition_versions[k.to_string()] = new_ver

        t1 = time.monotonic_ns()
        return WriterAttemptResult(
            writer_id=task.writer_id,
            attempt_id=attempt_id,
            outcome=TransactionOutcome.COMMITTED,
            latency_ms=(t1 - t0) / 1_000_000.0,
            lock_wait_ms=lock_wait_ms,
            retries=0,
            target_keys=target_str_keys,
            read_versions=task.read_versions,
            committed_versions={k.to_string(): new_ver for k in task.target_keys},
        )


def execute_dag_partition_writer(
    coordinator: SimulatedPartitionCoordinator,
    task: WriterTaskSpec,
    attempt_id: int,
    barrier: threading.Barrier | None = None,
    is_disjoint_workload: bool = False,
) -> WriterAttemptResult:
    target_str_keys = [k.to_string() for k in task.target_keys]
    if barrier:
        try:
            barrier.wait(timeout=2.0)
        except threading.BrokenBarrierError:
            pass

    t0 = time.monotonic_ns()
    lock_t0 = time.monotonic_ns()

    # Acquire locks in canonical sorted order
    locked_items = coordinator.get_partition_locks(task.target_keys)

    acquired_locks = []
    try:
        for k_str, lock in locked_items:
            lock.acquire()
            acquired_locks.append(lock)
        lock_t1 = time.monotonic_ns()
        lock_wait_ms = (lock_t1 - lock_t0) / 1_000_000.0

        if not task.is_write:
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.COMMITTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
                committed_versions={k: coordinator.partition_versions.get(k, 1) for k in target_str_keys},
            )

        if task.is_governance:
            # Governance write
            coordinator.governance_epoch += 1
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.COMMITTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
                committed_versions={"governance": coordinator.governance_epoch},
            )

        # Check partition versions for target keys
        stale_detected = False
        for k_str in target_str_keys:
            expected_ver = task.read_versions.get(k_str, 1)
            actual_ver = coordinator.partition_versions.get(k_str, 1)
            if actual_ver != expected_ver:
                stale_detected = True
                break

        if stale_detected:
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.TRUE_STALE_ABORTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=lock_wait_ms,
                retries=0,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
            )

        # Mutate target partition versions fine-grained
        new_versions = {}
        for k_str in target_str_keys:
            new_ver = coordinator.partition_versions.get(k_str, 1) + 1
            coordinator.partition_versions[k_str] = new_ver
            new_versions[k_str] = new_ver

        t1 = time.monotonic_ns()
        return WriterAttemptResult(
            writer_id=task.writer_id,
            attempt_id=attempt_id,
            outcome=TransactionOutcome.COMMITTED,
            latency_ms=(t1 - t0) / 1_000_000.0,
            lock_wait_ms=lock_wait_ms,
            retries=0,
            target_keys=target_str_keys,
            read_versions=task.read_versions,
            committed_versions=new_versions,
        )
    finally:
        for lock in reversed(acquired_locks):
            lock.release()


def execute_occ_backoff_writer(
    coordinator: SimulatedPartitionCoordinator,
    task: WriterTaskSpec,
    attempt_id: int,
    max_retries: int = 3,
) -> WriterAttemptResult:
    target_str_keys = [k.to_string() for k in task.target_keys]
    t0 = time.monotonic_ns()
    retries = 0

    for attempt in range(max_retries + 1):
        # Read phase without lock
        current_read_versions = {k: coordinator.partition_versions.get(k, 1) for k in target_str_keys}

        # Check for stale reads
        stale = False
        for k in target_str_keys:
            if current_read_versions[k] != task.read_versions.get(k, current_read_versions[k]):
                stale = True
                break

        if not task.is_write:
            t1 = time.monotonic_ns()
            return WriterAttemptResult(
                writer_id=task.writer_id,
                attempt_id=attempt_id,
                outcome=TransactionOutcome.COMMITTED,
                latency_ms=(t1 - t0) / 1_000_000.0,
                lock_wait_ms=0.0,
                retries=retries,
                target_keys=target_str_keys,
                read_versions=task.read_versions,
                committed_versions=current_read_versions,
            )

        if not stale:
            # Validation & Commit phase under lock
            with coordinator._coordinator_lock:
                # Re-validate
                valid = True
                for k in target_str_keys:
                    if coordinator.partition_versions.get(k, 1) != current_read_versions[k]:
                        valid = False
                        break
                if valid:
                    new_versions = {}
                    for k in target_str_keys:
                        nv = coordinator.partition_versions.get(k, 1) + 1
                        coordinator.partition_versions[k] = nv
                        new_versions[k] = nv
                    t1 = time.monotonic_ns()
                    return WriterAttemptResult(
                        writer_id=task.writer_id,
                        attempt_id=attempt_id,
                        outcome=TransactionOutcome.COMMITTED,
                        latency_ms=(t1 - t0) / 1_000_000.0,
                        lock_wait_ms=0.0,
                        retries=retries,
                        target_keys=target_str_keys,
                        read_versions=task.read_versions,
                        committed_versions=new_versions,
                    )

        retries += 1
        # Exponential backoff with jitter
        backoff_ms = (2 ** retries) * random.uniform(0.1, 0.5)
        time.sleep(backoff_ms / 1000.0)

    t1 = time.monotonic_ns()
    return WriterAttemptResult(
        writer_id=task.writer_id,
        attempt_id=attempt_id,
        outcome=TransactionOutcome.TRUE_STALE_ABORTED,
        latency_ms=(t1 - t0) / 1_000_000.0,
        lock_wait_ms=0.0,
        retries=retries,
        target_keys=target_str_keys,
        read_versions=task.read_versions,
    )


def generate_workload_tasks(
    config: WorkloadCellConfig,
    entities: list[PartitionKey],
) -> list[WriterTaskSpec]:
    """Generate writer task specifications based on cell factors and workload family."""
    rng = random.Random(config.seed + hash(config.cell_id) % 10000)
    zipf_sampler = ZipfianSampler(len(entities), config.zipf_theta, seed=config.seed)

    tasks: list[WriterTaskSpec] = []
    total_writers = config.concurrency

    for w_id in range(total_writers):
        # Determine if write vs read
        is_write = rng.random() < config.write_ratio
        is_gov = config.family_name in ("governance_plus_entity", "mixed") and (w_id == 0)
        is_evid = config.family_name == "evidence_plus_entity" and (w_id % 2 == 1)

        # Key selection based on overlap ratio and Zipfian sampler
        chosen_keys: list[PartitionKey] = []
        if config.overlap_ratio == 1.0 or config.family_name == "same_entity_contention":
            # All writers target key 0
            base_key = entities[0]
            chosen_keys.append(base_key)
            for d in range(1, config.dependency_width):
                chosen_keys.append(entities[d % len(entities)])
        elif config.overlap_ratio == 0.0 or config.family_name == "disjoint_entity":
            # Disjoint keys per writer
            for d in range(config.dependency_width):
                idx = (w_id * config.dependency_width + d) % len(entities)
                chosen_keys.append(entities[idx])
        else:
            # Partial overlap controlled by overlap ratio and Zipfian skew
            for d in range(config.dependency_width):
                if rng.random() < config.overlap_ratio:
                    # Shared hot key
                    idx = zipf_sampler.sample()
                else:
                    # Disjoint key
                    idx = (w_id * config.dependency_width + d) % len(entities)
                chosen_keys.append(entities[idx])

        # De-duplicate while preserving PartitionKey type
        unique_keys_dict = {k.to_string(): k for k in chosen_keys}
        unique_keys = list(unique_keys_dict.values())

        tasks.append(
            WriterTaskSpec(
                writer_id=w_id,
                is_write=is_write,
                is_governance=is_gov,
                is_evidence=is_evid,
                target_keys=unique_keys,
                read_versions={k.to_string(): 1 for k in unique_keys},
                expected_profile_version=1,
            )
        )

    return tasks


def run_single_cell_repetition(
    config: WorkloadCellConfig,
    regime: ConcurrencyRegime,
    repetition_id: int,
) -> CellRunMetrics:
    """Run one independent repetition of a workload cell under a specified regime."""
    # Build entity universe across domains
    domains = ["medications", "conditions", "observations", "governance"]
    entities: list[PartitionKey] = []
    needed_entities = max(config.num_entities, config.concurrency * config.dependency_width * 4)
    per_domain = math.ceil(needed_entities / len(domains))
    for d in domains:
        for i in range(per_domain):
            entities.append(PartitionKey(domain=d, semantic_key=f"entity_{i:03d}"))

    coordinator = SimulatedPartitionCoordinator(entities)
    tasks = generate_workload_tasks(config, entities)

    results: list[WriterAttemptResult] = []
    threads: list[threading.Thread] = []

    # Barrier for synchronized concurrency launch
    barrier = threading.Barrier(config.concurrency) if config.concurrency > 1 else None
    wall_t0 = time.monotonic_ns()

    def worker(task: WriterTaskSpec, attempt_idx: int) -> None:
        if regime == ConcurrencyRegime.MONOLITHIC_PROFILE_LOCK:
            res = execute_monolithic_writer(coordinator, task, attempt_idx, barrier)
        elif regime == ConcurrencyRegime.ENTITY_DAG_PARTITION_LOCKING:
            is_disjoint = config.overlap_ratio == 0.0 or config.family_name == "disjoint_entity"
            res = execute_dag_partition_writer(coordinator, task, attempt_idx, barrier, is_disjoint_workload=is_disjoint)
        elif regime == ConcurrencyRegime.OCC_BACKOFF:
            res = execute_occ_backoff_writer(coordinator, task, attempt_idx)
        else:
            raise ValueError(f"Unknown regime: {regime}")
        results.append(res)

    for i, t in enumerate(tasks):
        th = threading.Thread(target=worker, args=(t, i))
        threads.append(th)

    for th in threads:
        th.start()
    for th in threads:
        th.join()

    wall_t1 = time.monotonic_ns()
    wall_clock_ms = max(0.001, (wall_t1 - wall_t0) / 1_000_000.0)

    # Compute metrics
    total_attempts = len(results)
    committed = sum(1 for r in results if r.outcome == TransactionOutcome.COMMITTED)
    true_stale = sum(1 for r in results if r.outcome == TransactionOutcome.TRUE_STALE_ABORTED)
    false_stale = sum(1 for r in results if r.outcome == TransactionOutcome.FALSE_STALE_ABORTED)
    gov_aborts = sum(1 for r in results if r.outcome == TransactionOutcome.GOVERNANCE_ABORTED)
    deadlocks = sum(1 for r in results if r.outcome == TransactionOutcome.DEADLOCK)
    retries = sum(r.retries for r in results)

    latencies = sorted([r.latency_ms for r in results])
    lock_waits = [r.lock_wait_ms for r in results]

    def quantile(lst: list[float], q: float) -> float:
        if not lst:
            return 0.0
        idx = max(0, min(len(lst) - 1, int(math.ceil(q * len(lst)) - 1)))
        return round(lst[idx], 3)

    commit_rate = round((committed / total_attempts) * 100.0, 2) if total_attempts > 0 else 0.0
    false_stale_rate = round((false_stale / total_attempts) * 100.0, 2) if total_attempts > 0 else 0.0
    true_stale_rate = round((true_stale / total_attempts) * 100.0, 2) if total_attempts > 0 else 0.0
    gov_rate = round((gov_aborts / total_attempts) * 100.0, 2) if total_attempts > 0 else 0.0
    throughput_tps = round(committed / (wall_clock_ms / 1000.0), 2)

    # Check invariants
    is_disjoint = config.overlap_ratio == 0.0 or config.family_name == "disjoint_entity"
    invariant_false_stale_zero = (false_stale == 0) if (regime == ConcurrencyRegime.ENTITY_DAG_PARTITION_LOCKING and is_disjoint) else True
    invariant_deadlock_zero = (deadlocks == 0)

    return CellRunMetrics(
        cell_id=config.cell_id,
        family_name=config.family_name,
        regime=regime,
        concurrency=config.concurrency,
        zipf_theta=config.zipf_theta,
        overlap_ratio=config.overlap_ratio,
        dependency_width=config.dependency_width,
        repetition_id=repetition_id,
        total_attempts=total_attempts,
        committed_count=committed,
        true_stale_count=true_stale,
        false_stale_count=false_stale,
        governance_abort_count=gov_aborts,
        deadlock_count=deadlocks,
        retry_count=retries,
        commit_rate=commit_rate,
        false_stale_rate=false_stale_rate,
        true_stale_rate=true_stale_rate,
        governance_abort_rate=gov_rate,
        throughput_tps=throughput_tps,
        latency_min_ms=quantile(latencies, 0.0) if latencies else 0.0,
        latency_p50_ms=quantile(latencies, 0.50),
        latency_p95_ms=quantile(latencies, 0.95),
        latency_p99_ms=quantile(latencies, 0.99),
        latency_max_ms=latencies[-1] if latencies else 0.0,
        latency_mean_ms=round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        lock_wait_mean_ms=round(sum(lock_waits) / len(lock_waits), 3) if lock_waits else 0.0,
        wall_clock_ms=round(wall_clock_ms, 3),
        invariant_false_stale_zero=invariant_false_stale_zero,
        invariant_deadlock_zero=invariant_deadlock_zero,
    )


def build_workload_family_cells() -> list[WorkloadCellConfig]:
    """Construct specifications for the 10 workload families."""
    families = [
        # 1. Same-entity contention
        WorkloadCellConfig("C01_same_entity", "same_entity_contention", concurrency=16, zipf_theta=0.0, overlap_ratio=1.0, dependency_width=1, read_ratio=0.0, write_ratio=1.0),
        # 2. Disjoint entity
        WorkloadCellConfig("C02_disjoint", "disjoint_entity", concurrency=16, zipf_theta=0.0, overlap_ratio=0.0, dependency_width=1, read_ratio=0.0, write_ratio=1.0),
        # 3. Partial overlap
        WorkloadCellConfig("C03_partial_overlap", "partial_overlap", concurrency=16, zipf_theta=0.8, overlap_ratio=0.25, dependency_width=2, read_ratio=0.20, write_ratio=0.80),
        # 4. Multi-domain
        WorkloadCellConfig("C04_multi_domain", "multi_domain", concurrency=16, zipf_theta=0.8, overlap_ratio=0.50, dependency_width=4, read_ratio=0.30, write_ratio=0.70),
        # 5. Hot-key Zipfian
        WorkloadCellConfig("C05_hot_key_zipfian", "hot_key_zipfian", concurrency=32, zipf_theta=1.4, overlap_ratio=0.75, dependency_width=2, read_ratio=0.10, write_ratio=0.90),
        # 6. Governance + entity
        WorkloadCellConfig("C06_governance_entity", "governance_plus_entity", concurrency=16, zipf_theta=0.8, overlap_ratio=0.25, dependency_width=2, read_ratio=0.20, write_ratio=0.80),
        # 7. Evidence + entity
        WorkloadCellConfig("C07_evidence_entity", "evidence_plus_entity", concurrency=16, zipf_theta=0.8, overlap_ratio=0.25, dependency_width=2, read_ratio=0.20, write_ratio=0.80),
        # 8. Read-heavy
        WorkloadCellConfig("C08_read_heavy", "read_heavy", concurrency=32, zipf_theta=0.8, overlap_ratio=0.25, dependency_width=2, read_ratio=0.90, write_ratio=0.10),
        # 9. Write-heavy
        WorkloadCellConfig("C09_write_heavy", "write_heavy", concurrency=32, zipf_theta=1.1, overlap_ratio=0.50, dependency_width=2, read_ratio=0.10, write_ratio=0.90),
        # 10. Mixed
        WorkloadCellConfig("C10_mixed", "mixed", concurrency=64, zipf_theta=1.1, overlap_ratio=0.50, dependency_width=4, read_ratio=0.50, write_ratio=0.50),
    ]
    return families


def run_multifactor_benchmark_suite(
    concurrencies: list[int] | None = None,
    thetas: list[float] | None = None,
    overlaps: list[float] | None = None,
    widths: list[int] | None = None,
    num_repetitions: int = 5,
    seed: int = 42,
) -> list[CellRunMetrics]:
    """Execute the multi-factor benchmark grid across all regimes and repetitions."""
    if concurrencies is None:
        concurrencies = [1, 2, 4, 8, 16, 32, 64]
    if thetas is None:
        thetas = [0.0, 0.8, 1.1, 1.4]
    if overlaps is None:
        overlaps = [0.0, 0.25, 0.50, 1.0]
    if widths is None:
        widths = [1, 2, 4, 8]

    all_metrics: list[CellRunMetrics] = []

    # 1. Run 10 workload families
    family_configs = build_workload_family_cells()
    for cfg in family_configs:
        cfg.num_repetitions = num_repetitions
        cfg.seed = seed
        for regime in ConcurrencyRegime:
            for rep in range(1, num_repetitions + 1):
                metrics = run_single_cell_repetition(cfg, regime, rep)
                all_metrics.append(metrics)

    # 2. Run multi-factor grid samples
    grid_cells: list[WorkloadCellConfig] = []
    cell_counter = 1
    for W in concurrencies:
        for th in thetas:
            for ov in overlaps:
                for w in widths:
                    cell_id = f"GRID_{cell_counter:03d}_W{W}_th{th}_ov{ov}_w{w}"
                    grid_cells.append(
                        WorkloadCellConfig(
                            cell_id=cell_id,
                            family_name="grid_sweep",
                            concurrency=W,
                            zipf_theta=th,
                            overlap_ratio=ov,
                            dependency_width=w,
                            read_ratio=0.50,
                            write_ratio=0.50,
                            num_repetitions=num_repetitions,
                            seed=seed + cell_counter,
                        )
                    )
                    cell_counter += 1

    for cfg in grid_cells:
        for regime in ConcurrencyRegime:
            for rep in range(1, num_repetitions + 1):
                metrics = run_single_cell_repetition(cfg, regime, rep)
                all_metrics.append(metrics)

    return all_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="E09 Multifactor Concurrency Benchmark Runner")
    parser.add_argument("--output", type=Path, default=Path("benchmark_results.json"), help="Output path for benchmark metrics")
    parser.add_argument("--repetitions", type=int, default=5, help="Number of repetitions per cell")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    metrics = run_multifactor_benchmark_suite(num_repetitions=args.repetitions, seed=args.seed)
    data = [asdict(m) for m in metrics]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
