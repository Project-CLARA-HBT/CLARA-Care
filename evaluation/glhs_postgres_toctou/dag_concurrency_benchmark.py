"""DAG Concurrency Benchmark: Monolithic Profile Locking vs Entity DAG Partition Locking.

This benchmark empirically compares three optimistic concurrency control (OCC) regimes
under high contention (16 concurrent writers) against PostgreSQL:

Arm 1: Monolithic Profile Locking (16 writers on disjoint entities)
    - Architecture: Legacy profile-global version counter (single monotonic counter per patient).
    - Workload: 16 concurrent writers attempting to update 16 completely disjoint entities
      (e.g., separate medications/conditions with non-overlapping dependency graphs).
    - Behavior: All writers compete for the single profile-global lock. Exactly 1 writer wins;
      the remaining 15 writers are rejected with 'stale_state_version' because the winner
      incremented the global profile counter.
    - Expected Result: False-stale rejection rate = 15/16 = 93.75% (1 committed, 15 rejected).

Arm 2: Entity DAG Partition Locking (16 writers on disjoint entities)
    - Architecture: Entity-Partitioned DAG Versioning (fine-grained partition locks).
    - Workload: 16 concurrent writers attempting to update 16 completely disjoint entities.
    - Behavior: Writers acquire row-level locks only on their respective target partition and
      dependencies in canonical sorted order. Because partitions are disjoint, no writer blocks
      or invalidates another.
    - Expected Result: False-stale rejection rate = 0.0% (16 committed, 0 rejected).

Arm 3: Entity DAG Partition Locking (16 writers on overlapping entities)
    - Architecture: Entity-Partitioned DAG Versioning (fine-grained partition locks).
    - Workload: 16 concurrent writers attempting to update the SAME entity (or overlapping DAG node).
    - Behavior: Writers serialize on the target entity's row lock. Exactly 1 writer wins and
      advances the partition version; the subsequent 15 writers re-read the incremented partition
      version and are correctly rejected with 'stale_partition_version'.
    - Expected Result: True-stale rejection rate = 15/16 = 93.75% (1 atomic winner, 15 true-stale rejections).

Theoretical Foundation:
    - Contention Probability reduces from O(W^2) on monolithic profile to O(W^2 / M) where M is
      the number of independent entity partitions in the DAG.
    - At W=16 writers on M=16 disjoint partitions, false-stale drops from 93.75% to 0.0% while
      maintaining full atomic serializability for overlapping mutations.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import BrokenBarrierError
from typing import Any, cast
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[2]
if _REPO_ROOT.exists() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_API_SRC = _REPO_ROOT / "services" / "api" / "src"
if _API_SRC.exists() and str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

try:
    from clara_api.db.base import Base
    from clara_api.db.models import (
        GlhsEntityVersionPartition,
        GlhsStateVersion,
        PhrProfile,
        User,
    )
    from clara_api.glhs.domain import GlhsInvariantError
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
except ImportError:
    Base = None  # type: ignore
    GlhsEntityVersionPartition = None  # type: ignore
    GlhsStateVersion = None  # type: ignore
    PhrProfile = None  # type: ignore
    User = None  # type: ignore
    class GlhsInvariantError(Exception):  # type: ignore
        pass
    create_engine = None  # type: ignore
    select = None  # type: ignore
    text = None  # type: ignore
    Engine = Any  # type: ignore
    class SQLAlchemyError(Exception):  # type: ignore
        pass
    Session = Any  # type: ignore

from evaluation.glhs_postgres_toctou.barrier import PhasedBarrier
from evaluation.glhs_postgres_toctou.schedule_primitives import (
    elapsed_ms,
    now_monotonic_ns,
)

DEFAULT_WRITER_COUNT = 16
DEFAULT_BENCHMARK_DOMAIN = "medications"
DEFAULT_SHARED_SEMANTIC_KEY = "rx_metformin_500mg"

BENCHMARK_WORKER_EXCEPTIONS: tuple[type[BaseException], ...] = (
    GlhsInvariantError,
    SQLAlchemyError,
    BrokenBarrierError,
    RuntimeError,
    TypeError,
    ValueError,
    OSError,
)


class BenchmarkArmType(StrEnum):
    """The three evaluated concurrency regimes."""

    MONOLITHIC_DISJOINT = "monolithic_profile_locking_disjoint_entities"
    DAG_DISJOINT = "entity_dag_partition_locking_disjoint_entities"
    DAG_OVERLAPPING = "entity_dag_partition_locking_overlapping_entities"


class WriterOutcome(StrEnum):
    """Outcome of an individual writer transaction attempt."""

    COMMITTED = "committed"
    FALSE_STALE_REJECTED = "false_stale_rejected"
    TRUE_STALE_REJECTED = "true_stale_rejected"
    OPERATIONAL_ERROR = "operational_error"


@dataclass(frozen=True)
class PartitionKey:
    """Canonical identifier for an entity DAG partition node."""

    domain: str
    semantic_key: str

    def to_tuple(self) -> tuple[str, str]:
        return (self.domain, self.semantic_key)


@dataclass(frozen=True)
class WriterTask:
    """Input specification for a concurrent writer worker."""

    writer_id: int
    profile_id: int
    target_keys: tuple[PartitionKey, ...]
    expected_profile_version: int
    expected_partition_versions: dict[str, int]
    is_disjoint_workload: bool


@dataclass
class WriterResult:
    """Execution telemetry captured for one writer transaction."""

    writer_id: int
    outcome: WriterOutcome
    reason_code: str
    start_ns: int
    end_ns: int
    latency_ms: float
    target_keys: list[str]
    expected_version: int
    observed_version: int | None = None
    resulting_version: int | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "writer_id": self.writer_id,
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "latency_ms": self.latency_ms,
            "target_keys": self.target_keys,
            "expected_version": self.expected_version,
            "observed_version": self.observed_version,
            "resulting_version": self.resulting_version,
            "error_message": self.error_message,
        }


@dataclass
class BenchmarkArmResult:
    """Aggregated results and verification metrics for one benchmark arm."""

    arm_type: BenchmarkArmType
    title: str
    description: str
    num_writers: int
    num_entities: int
    is_disjoint: bool
    total_attempts: int
    committed_count: int
    false_stale_count: int
    true_stale_count: int
    operational_error_count: int
    false_stale_rejection_rate: float
    true_stale_rejection_rate: float
    commit_success_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_mean_ms: float
    latency_min_ms: float
    latency_max_ms: float
    wall_clock_duration_ms: float
    writer_results: list[WriterResult]
    invariant_passed: bool
    verification_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_type": self.arm_type.value,
            "title": self.title,
            "description": self.description,
            "num_writers": self.num_writers,
            "num_entities": self.num_entities,
            "is_disjoint": self.is_disjoint,
            "total_attempts": self.total_attempts,
            "committed_count": self.committed_count,
            "false_stale_count": self.false_stale_count,
            "true_stale_count": self.true_stale_count,
            "operational_error_count": self.operational_error_count,
            "false_stale_rejection_rate": self.false_stale_rejection_rate,
            "true_stale_rejection_rate": self.true_stale_rejection_rate,
            "commit_success_rate": self.commit_success_rate,
            "latency_metrics_ms": {
                "p50": self.latency_p50_ms,
                "p95": self.latency_p95_ms,
                "p99": self.latency_p99_ms,
                "mean": self.latency_mean_ms,
                "min": self.latency_min_ms,
                "max": self.latency_max_ms,
            },
            "wall_clock_duration_ms": self.wall_clock_duration_ms,
            "invariant_passed": self.invariant_passed,
            "verification_message": self.verification_message,
            "writer_results": [r.to_dict() for r in self.writer_results],
        }


@dataclass
class BenchmarkComparisonReport:
    """Full multi-arm comparison report."""

    benchmark_id: str
    timestamp_utc: str
    backend: str
    num_writers: int
    arms: dict[str, BenchmarkArmResult]
    all_invariants_passed: bool
    summary_table: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "timestamp_utc": self.timestamp_utc,
            "backend": self.backend,
            "num_writers": self.num_writers,
            "all_invariants_passed": self.all_invariants_passed,
            "arms": {k: v.to_dict() for k, v in self.arms.items()},
        }


def calculate_percentile(sorted_values: list[float], percentile: float) -> float:
    """Nearest-rank percentile over a pre-sorted list of floats."""
    if not sorted_values:
        return 0.0
    rank = max(
        0,
        min(
            len(sorted_values) - 1,
            int(math.ceil(percentile * len(sorted_values)) - 1),
        ),
    )
    return round(float(sorted_values[rank]), 3)


@dataclass
class SeededProfile:
    """Seeded test fixture for a patient profile and associated partition records."""

    user_id: int
    profile_id: int
    disjoint_partition_keys: list[PartitionKey]
    shared_partition_key: PartitionKey


def seed_benchmark_fixtures(
    session: Session,
    *,
    writer_count: int,
    domain: str = DEFAULT_BENCHMARK_DOMAIN,
) -> SeededProfile:
    """Seed user, PhrProfile, initial GlhsStateVersion and entity partitions."""
    user = User(
        email=f"dag-bench-{uuid4().hex[:12]}@example.test",
        hashed_password="hashed_pw_placeholder",
        role="normal",
    )
    session.add(user)
    session.flush()

    profile = PhrProfile(
        user_id=user.id,
        full_name=f"Benchmark Patient {uuid4().hex[:6]}",
    )
    session.add(profile)
    session.flush()

    init_state_ver = GlhsStateVersion(
        profile_id=profile.id,
        state_version=1,
        valid_at=datetime.now(UTC),
        policy_version="commitloop.v1",
    )
    session.add(init_state_ver)

    disjoint_keys: list[PartitionKey] = []
    for i in range(writer_count):
        key = PartitionKey(domain=domain, semantic_key=f"rx_entity_{i:02d}")
        disjoint_keys.append(key)
        part = GlhsEntityVersionPartition(
            profile_id=profile.id,
            domain=key.domain,
            semantic_key=key.semantic_key,
            state_version=1,
            policy_version="commitloop.v1",
            consent_version="not_required",
            updated_at=datetime.now(UTC),
        )
        session.add(part)

    shared_key = PartitionKey(domain=domain, semantic_key=DEFAULT_SHARED_SEMANTIC_KEY)
    shared_part = GlhsEntityVersionPartition(
        profile_id=profile.id,
        domain=shared_key.domain,
        semantic_key=shared_key.semantic_key,
        state_version=1,
        policy_version="commitloop.v1",
        consent_version="not_required",
        updated_at=datetime.now(UTC),
    )
    session.add(shared_part)

    session.commit()
    return SeededProfile(
        user_id=user.id,
        profile_id=profile.id,
        disjoint_partition_keys=disjoint_keys,
        shared_partition_key=shared_key,
    )


def execute_monolithic_disjoint_writer(
    session: Session,
    task: WriterTask,
    barrier: PhasedBarrier,
) -> WriterResult:
    target_key_str = f"{task.target_keys[0].domain}:{task.target_keys[0].semantic_key}"
    barrier.wait("release")
    start_ns = now_monotonic_ns()

    try:
        session.execute(
            select(PhrProfile.id).where(PhrProfile.id == task.profile_id).with_for_update()
        ).scalar_one()

        current_ver = (
            session.execute(
                select(GlhsStateVersion.state_version)
                .where(GlhsStateVersion.profile_id == task.profile_id)
                .order_by(GlhsStateVersion.state_version.desc())
                .limit(1)
            ).scalar_one_or_none()
            or 1
        )

        if current_ver != task.expected_profile_version:
            session.rollback()
            end_ns = now_monotonic_ns()
            return WriterResult(
                writer_id=task.writer_id,
                outcome=WriterOutcome.FALSE_STALE_REJECTED,
                reason_code="stale_state_version",
                start_ns=start_ns,
                end_ns=end_ns,
                latency_ms=elapsed_ms(start_ns, end_ns),
                target_keys=[target_key_str],
                expected_version=task.expected_profile_version,
                observed_version=current_ver,
                resulting_version=None,
            )

        new_version = current_ver + 1
        new_state_row = GlhsStateVersion(
            profile_id=task.profile_id,
            state_version=new_version,
            valid_at=datetime.now(UTC),
            policy_version="commitloop.v1",
        )
        session.add(new_state_row)

        for pk in task.target_keys:
            part = session.execute(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == task.profile_id,
                    GlhsEntityVersionPartition.domain == pk.domain,
                    GlhsEntityVersionPartition.semantic_key == pk.semantic_key,
                )
            ).scalar_one_or_none()
            if part:
                part.state_version = new_version
                part.updated_at = datetime.now(UTC)

        session.commit()
        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.COMMITTED,
            reason_code="transition_committed",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=[target_key_str],
            expected_version=task.expected_profile_version,
            observed_version=current_ver,
            resulting_version=new_version,
        )
    except BENCHMARK_WORKER_EXCEPTIONS as exc:
        session.rollback()
        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.OPERATIONAL_ERROR,
            reason_code="operational_database_error",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=[target_key_str],
            expected_version=task.expected_profile_version,
            error_message=f"{type(exc).__name__}: {exc}",
        )


def execute_dag_partition_writer(
    session: Session,
    task: WriterTask,
    barrier: PhasedBarrier,
) -> WriterResult:
    target_key_strs = [f"{pk.domain}:{pk.semantic_key}" for pk in task.target_keys]
    sorted_keys = sorted(task.target_keys, key=lambda k: (k.domain, k.semantic_key))

    barrier.wait("release")
    start_ns = now_monotonic_ns()

    try:
        locked_partitions: list[GlhsEntityVersionPartition] = []
        for pk in sorted_keys:
            part = session.execute(
                select(GlhsEntityVersionPartition)
                .where(
                    GlhsEntityVersionPartition.profile_id == task.profile_id,
                    GlhsEntityVersionPartition.domain == pk.domain,
                    GlhsEntityVersionPartition.semantic_key == pk.semantic_key,
                )
                .with_for_update()
            ).scalar_one()
            locked_partitions.append(part)

        for part in locked_partitions:
            part_key_str = f"{part.domain}:{part.semantic_key}"
            expected_ver = task.expected_partition_versions.get(part_key_str, 1)
            if part.state_version != expected_ver:
                session.rollback()
                end_ns = now_monotonic_ns()
                outcome = (
                    WriterOutcome.FALSE_STALE_REJECTED
                    if task.is_disjoint_workload
                    else WriterOutcome.TRUE_STALE_REJECTED
                )
                return WriterResult(
                    writer_id=task.writer_id,
                    outcome=outcome,
                    reason_code="stale_partition_version",
                    start_ns=start_ns,
                    end_ns=end_ns,
                    latency_ms=elapsed_ms(start_ns, end_ns),
                    target_keys=target_key_strs,
                    expected_version=expected_ver,
                    observed_version=part.state_version,
                    resulting_version=None,
                )

        last_version = 1
        now = datetime.now(UTC)
        for part in locked_partitions:
            part.state_version += 1
            part.updated_at = now
            last_version = part.state_version

        session.commit()
        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.COMMITTED,
            reason_code="transition_committed",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=target_key_strs,
            expected_version=task.expected_partition_versions.get(target_key_strs[0], 1),
            observed_version=last_version - 1,
            resulting_version=last_version,
        )
    except BENCHMARK_WORKER_EXCEPTIONS as exc:
        session.rollback()
        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.OPERATIONAL_ERROR,
            reason_code="operational_database_error",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=target_key_strs,
            expected_version=task.expected_partition_versions.get(target_key_strs[0], 1),
            error_message=f"{type(exc).__name__}: {exc}",
        )


class SimulatedLockCoordinator:
    """Thread-safe simulator of PostgreSQL row-level locks and version storage."""

    def __init__(self) -> None:
        self._global_profile_lock = threading.Lock()
        self._partition_locks: dict[str, threading.Lock] = {}
        self._coordinator_mutex = threading.Lock()
        self.profile_versions: dict[int, int] = {}
        self.partition_versions: dict[str, int] = {}

    def get_partition_lock(self, key: str) -> threading.Lock:
        with self._coordinator_mutex:
            if key not in self._partition_locks:
                self._partition_locks[key] = threading.Lock()
            return self._partition_locks[key]


def run_simulated_monolithic_writer(
    coordinator: SimulatedLockCoordinator,
    task: WriterTask,
    barrier: PhasedBarrier,
) -> WriterResult:
    target_key_str = f"{task.target_keys[0].domain}:{task.target_keys[0].semantic_key}"
    barrier.wait("release")
    start_ns = now_monotonic_ns()

    with coordinator._global_profile_lock:
        curr_ver = coordinator.profile_versions.get(task.profile_id, 1)
        if curr_ver != task.expected_profile_version:
            end_ns = now_monotonic_ns()
            return WriterResult(
                writer_id=task.writer_id,
                outcome=WriterOutcome.FALSE_STALE_REJECTED,
                reason_code="stale_state_version",
                start_ns=start_ns,
                end_ns=end_ns,
                latency_ms=elapsed_ms(start_ns, end_ns),
                target_keys=[target_key_str],
                expected_version=task.expected_profile_version,
                observed_version=curr_ver,
            )

        time.sleep(0.001)
        new_ver = curr_ver + 1
        coordinator.profile_versions[task.profile_id] = new_ver
        coordinator.partition_versions[target_key_str] = new_ver
        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.COMMITTED,
            reason_code="transition_committed",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=[target_key_str],
            expected_version=task.expected_profile_version,
            observed_version=curr_ver,
            resulting_version=new_ver,
        )


def run_simulated_dag_writer(
    coordinator: SimulatedLockCoordinator,
    task: WriterTask,
    barrier: PhasedBarrier,
) -> WriterResult:
    target_key_strs = [f"{pk.domain}:{pk.semantic_key}" for pk in task.target_keys]
    barrier.wait("release")
    start_ns = now_monotonic_ns()

    locks = [coordinator.get_partition_lock(k) for k in sorted(target_key_strs)]
    for lock in locks:
        lock.acquire()

    try:
        for k in target_key_strs:
            expected_ver = task.expected_partition_versions.get(k, 1)
            curr_ver = coordinator.partition_versions.get(k, 1)
            if curr_ver != expected_ver:
                end_ns = now_monotonic_ns()
                outcome = (
                    WriterOutcome.FALSE_STALE_REJECTED
                    if task.is_disjoint_workload
                    else WriterOutcome.TRUE_STALE_REJECTED
                )
                return WriterResult(
                    writer_id=task.writer_id,
                    outcome=outcome,
                    reason_code="stale_partition_version",
                    start_ns=start_ns,
                    end_ns=end_ns,
                    latency_ms=elapsed_ms(start_ns, end_ns),
                    target_keys=target_key_strs,
                    expected_version=expected_ver,
                    observed_version=curr_ver,
                )

        time.sleep(0.001)
        res_ver = 1
        for k in target_key_strs:
            res_ver = coordinator.partition_versions.get(k, 1) + 1
            coordinator.partition_versions[k] = res_ver

        end_ns = now_monotonic_ns()
        return WriterResult(
            writer_id=task.writer_id,
            outcome=WriterOutcome.COMMITTED,
            reason_code="transition_committed",
            start_ns=start_ns,
            end_ns=end_ns,
            latency_ms=elapsed_ms(start_ns, end_ns),
            target_keys=target_key_strs,
            expected_version=task.expected_partition_versions.get(target_key_strs[0], 1),
            observed_version=res_ver - 1,
            resulting_version=res_ver,
        )
    finally:
        for lock in reversed(locks):
            lock.release()


def execute_benchmark_arm(
    arm_type: BenchmarkArmType,
    *,
    writer_count: int,
    session_factory: Callable[[], Session] | None = None,
    profile_fixtures: SeededProfile | None = None,
    simulated_coordinator: SimulatedLockCoordinator | None = None,
) -> BenchmarkArmResult:
    is_simulated = session_factory is None or simulated_coordinator is not None
    barrier = PhasedBarrier(writer_count, timeout_s=30.0)
    threads: list[threading.Thread] = []
    results: list[WriterResult | None] = [None] * writer_count

    is_disjoint = arm_type != BenchmarkArmType.DAG_OVERLAPPING
    num_entities = writer_count if is_disjoint else 1

    tasks: list[WriterTask] = []
    for i in range(writer_count):
        if is_disjoint:
            target_key = PartitionKey(
                domain=DEFAULT_BENCHMARK_DOMAIN,
                semantic_key=f"rx_entity_{i:02d}",
            )
        else:
            target_key = PartitionKey(
                domain=DEFAULT_BENCHMARK_DOMAIN,
                semantic_key=DEFAULT_SHARED_SEMANTIC_KEY,
            )

        target_key_str = f"{target_key.domain}:{target_key.semantic_key}"
        task = WriterTask(
            writer_id=i,
            profile_id=profile_fixtures.profile_id if profile_fixtures else 1,
            target_keys=(target_key,),
            expected_profile_version=1,
            expected_partition_versions={target_key_str: 1},
            is_disjoint_workload=is_disjoint,
        )
        tasks.append(task)

    def worker_thread(index: int) -> None:
        if is_simulated:
            assert simulated_coordinator is not None
            if arm_type == BenchmarkArmType.MONOLITHIC_DISJOINT:
                res = run_simulated_monolithic_writer(simulated_coordinator, tasks[index], barrier)
            else:
                res = run_simulated_dag_writer(simulated_coordinator, tasks[index], barrier)
            results[index] = res
        else:
            assert session_factory is not None
            session = session_factory()
            try:
                if arm_type == BenchmarkArmType.MONOLITHIC_DISJOINT:
                    res = execute_monolithic_disjoint_writer(session, tasks[index], barrier)
                else:
                    res = execute_dag_partition_writer(session, tasks[index], barrier)
                results[index] = res
            finally:
                session.close()

    wall_start_ns = now_monotonic_ns()
    for i in range(writer_count):
        t = threading.Thread(
            target=worker_thread,
            args=(i,),
            name=f"bench-worker-{arm_type.value}-{i}",
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=45.0)

    wall_duration_ms = elapsed_ms(wall_start_ns)

    if any(r is None for r in results):
        raise RuntimeError(
            f"Benchmark arm {arm_type.value} worker thread timed out or failed to record result"
        )

    collected_results = [cast(WriterResult, r) for r in results]

    committed = sum(1 for r in collected_results if r.outcome == WriterOutcome.COMMITTED)
    false_stale = sum(
        1 for r in collected_results if r.outcome == WriterOutcome.FALSE_STALE_REJECTED
    )
    true_stale = sum(1 for r in collected_results if r.outcome == WriterOutcome.TRUE_STALE_REJECTED)
    errors = sum(1 for r in collected_results if r.outcome == WriterOutcome.OPERATIONAL_ERROR)

    total_attempts = writer_count
    false_stale_rate = round(false_stale / total_attempts, 4)
    true_stale_rate = round(true_stale / total_attempts, 4)
    success_rate = round(committed / total_attempts, 4)

    sorted_latencies = sorted(r.latency_ms for r in collected_results)
    p50 = calculate_percentile(sorted_latencies, 0.50)
    p95 = calculate_percentile(sorted_latencies, 0.95)
    p99 = calculate_percentile(sorted_latencies, 0.99)
    mean_lat = round(sum(sorted_latencies) / len(sorted_latencies), 3) if sorted_latencies else 0.0
    min_lat = round(min(sorted_latencies), 3) if sorted_latencies else 0.0
    max_lat = round(max(sorted_latencies), 3) if sorted_latencies else 0.0

    invariant_passed = False
    verification_msg = ""

    if arm_type == BenchmarkArmType.MONOLITHIC_DISJOINT:
        title = "Monolithic Profile Locking (Disjoint Entities)"
        desc = "16 writers on disjoint entities -> false-stale rejection rate (~93.75%)"
        expected_rejections = total_attempts - 1
        if committed == 1 and false_stale == expected_rejections and errors == 0:
            invariant_passed = True
            verification_msg = f"PASS: Exactly 1 winner and {expected_rejections} false-stale rejections observed ({false_stale_rate * 100:.2f}%)."
        else:
            verification_msg = f"FAIL: Expected 1 commit and {expected_rejections} false-stale rejections, got {committed} commits, {false_stale} false-stale, {errors} errors."

    elif arm_type == BenchmarkArmType.DAG_DISJOINT:
        title = "Entity DAG Partition Locking (Disjoint Entities)"
        desc = "16 writers on disjoint entities -> false-stale rejection rate (0%)"
        if committed == total_attempts and false_stale == 0 and true_stale == 0 and errors == 0:
            invariant_passed = True
            verification_msg = f"PASS: All {total_attempts} writers committed successfully with 0.00% false-stale rejection."
        else:
            verification_msg = f"FAIL: Expected {total_attempts} commits and 0 rejections, got {committed} commits, {false_stale} false-stale, {errors} errors."

    elif arm_type == BenchmarkArmType.DAG_OVERLAPPING:
        title = "Entity DAG Partition Locking (Overlapping Entities)"
        desc = "16 writers on overlapping entities -> true-stale rejection rate (atomic winner)"
        expected_rejections = total_attempts - 1
        if (
            committed == 1
            and true_stale == expected_rejections
            and false_stale == 0
            and errors == 0
        ):
            invariant_passed = True
            verification_msg = f"PASS: Exactly 1 atomic winner and {expected_rejections} true-stale rejections observed ({true_stale_rate * 100:.2f}%)."
        else:
            verification_msg = f"FAIL: Expected 1 commit and {expected_rejections} true-stale rejections, got {committed} commits, {true_stale} true-stale, {errors} errors."

    return BenchmarkArmResult(
        arm_type=arm_type,
        title=title,
        description=desc,
        num_writers=writer_count,
        num_entities=num_entities,
        is_disjoint=is_disjoint,
        total_attempts=total_attempts,
        committed_count=committed,
        false_stale_count=false_stale,
        true_stale_count=true_stale,
        operational_error_count=errors,
        false_stale_rejection_rate=false_stale_rate,
        true_stale_rejection_rate=true_stale_rate,
        commit_success_rate=success_rate,
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        latency_mean_ms=mean_lat,
        latency_min_ms=min_lat,
        latency_max_ms=max_lat,
        wall_clock_duration_ms=wall_duration_ms,
        writer_results=collected_results,
        invariant_passed=invariant_passed,
        verification_message=verification_msg,
    )


def run_dag_concurrency_benchmark(
    *,
    database_url: str | None = None,
    writer_count: int = DEFAULT_WRITER_COUNT,
    use_simulation_fallback: bool = True,
) -> BenchmarkComparisonReport:
    """Execute all three benchmark arms and produce a verified comparison report."""
    run_id = f"GLHS-DAG-BENCHMARK-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    timestamp_utc = datetime.now(UTC).isoformat()

    engine: Engine | None = None
    schema_name: str | None = None
    backend_desc = "simulated_in_memory_concurrency"

    resolved_db_url = (
        database_url or os.getenv("GLHS_TOCTOU_FINAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    if resolved_db_url and resolved_db_url.startswith("postgres"):
        if create_engine is None or Base is None:
            if not use_simulation_fallback:
                raise RuntimeError("PostgreSQL database URL provided but sqlalchemy/clara_api are not available.")
        else:
            backend_desc = "postgresql_isolated_schema"
            schema_name = f"dag_bench_{uuid4().hex[:10]}"
            admin_engine = create_engine(resolved_db_url, pool_pre_ping=True)
            with admin_engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            admin_engine.dispose()

            engine = create_engine(
                resolved_db_url,
                pool_pre_ping=True,
                connect_args={"options": f"-csearch_path={schema_name}"},
            )
            Base.metadata.create_all(engine)

    arms: dict[str, BenchmarkArmResult] = {}

    try:
        if engine is not None:

            def session_factory():
                return Session(engine, expire_on_commit=False)

            init_session = session_factory()
            try:
                fixtures_arm1 = seed_benchmark_fixtures(init_session, writer_count=writer_count)
            finally:
                init_session.close()
            arms["monolithic_disjoint"] = execute_benchmark_arm(
                BenchmarkArmType.MONOLITHIC_DISJOINT,
                writer_count=writer_count,
                session_factory=session_factory,
                profile_fixtures=fixtures_arm1,
            )

            init_session = session_factory()
            try:
                fixtures_arm2 = seed_benchmark_fixtures(init_session, writer_count=writer_count)
            finally:
                init_session.close()
            arms["dag_disjoint"] = execute_benchmark_arm(
                BenchmarkArmType.DAG_DISJOINT,
                writer_count=writer_count,
                session_factory=session_factory,
                profile_fixtures=fixtures_arm2,
            )

            init_session = session_factory()
            try:
                fixtures_arm3 = seed_benchmark_fixtures(init_session, writer_count=writer_count)
            finally:
                init_session.close()
            arms["dag_overlapping"] = execute_benchmark_arm(
                BenchmarkArmType.DAG_OVERLAPPING,
                writer_count=writer_count,
                session_factory=session_factory,
                profile_fixtures=fixtures_arm3,
            )
        else:
            if not use_simulation_fallback:
                raise RuntimeError(
                    "PostgreSQL database URL required but not provided, and simulation fallback is disabled."
                )

            sim_coord1 = SimulatedLockCoordinator()
            sim_coord1.profile_versions[1] = 1
            for i in range(writer_count):
                sim_coord1.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:rx_entity_{i:02d}"] = 1
            arms["monolithic_disjoint"] = execute_benchmark_arm(
                BenchmarkArmType.MONOLITHIC_DISJOINT,
                writer_count=writer_count,
                simulated_coordinator=sim_coord1,
            )

            sim_coord2 = SimulatedLockCoordinator()
            sim_coord2.profile_versions[1] = 1
            for i in range(writer_count):
                sim_coord2.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:rx_entity_{i:02d}"] = 1
            arms["dag_disjoint"] = execute_benchmark_arm(
                BenchmarkArmType.DAG_DISJOINT,
                writer_count=writer_count,
                simulated_coordinator=sim_coord2,
            )

            sim_coord3 = SimulatedLockCoordinator()
            sim_coord3.profile_versions[1] = 1
            sim_coord3.partition_versions[
                f"{DEFAULT_BENCHMARK_DOMAIN}:{DEFAULT_SHARED_SEMANTIC_KEY}"
            ] = 1
            arms["dag_overlapping"] = execute_benchmark_arm(
                BenchmarkArmType.DAG_OVERLAPPING,
                writer_count=writer_count,
                simulated_coordinator=sim_coord3,
            )
    finally:
        if engine is not None:
            engine.dispose()
        if schema_name is not None and resolved_db_url is not None:
            cleanup_engine = create_engine(resolved_db_url, pool_pre_ping=True)
            with cleanup_engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            cleanup_engine.dispose()

    all_passed = all(a.invariant_passed for a in arms.values())
    summary_table = render_summary_table(arms, num_writers=writer_count, backend=backend_desc)

    return BenchmarkComparisonReport(
        benchmark_id=run_id,
        timestamp_utc=timestamp_utc,
        backend=backend_desc,
        num_writers=writer_count,
        arms=arms,
        all_invariants_passed=all_passed,
        summary_table=summary_table,
    )


def render_summary_table(
    arms: dict[str, BenchmarkArmResult],
    num_writers: int,
    backend: str,
) -> str:
    """Format benchmark results into a clean ASCII table."""
    lines: list[str] = [
        "=" * 118,
        "GLHS OPTIMISTIC CONCURRENCY BENCHMARK: MONOLITHIC LOCKING VS ENTITY DAG PARTITION LOCKING",
        f"Backend: {backend} | Writers per Arm: {num_writers} | Generated at: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 118,
        f"{'Benchmark Regime':<44} | {'Attempts':>8} | {'Committed':>9} | {'False-Stale':>11} | {'True-Stale':>10} | {'False-Stale %':>13} | {'True-Stale %':>12}",
        "-" * 118,
    ]

    for arm_key, res in arms.items():
        arm_label = {
            "monolithic_disjoint": "1. Monolithic (16 Disjoint Entities)",
            "dag_disjoint": "2. Entity DAG (16 Disjoint Entities)",
            "dag_overlapping": "3. Entity DAG (16 Overlapping Entities)",
        }.get(arm_key, res.title)

        false_stale_pct = f"{res.false_stale_rejection_rate * 100:.2f}%"
        true_stale_pct = f"{res.true_stale_rejection_rate * 100:.2f}%"

        lines.append(
            f"{arm_label:<44} | {res.total_attempts:>8} | {res.committed_count:>9} | {res.false_stale_count:>11} | {res.true_stale_count:>10} | {false_stale_pct:>13} | {true_stale_pct:>12}"
        )

    lines.append("=" * 118)
    lines.append("INVARIANT VERIFICATION SUMMARY:")
    for _arm_key, res in arms.items():
        status = "PASSED" if res.invariant_passed else "FAILED"
        lines.append(f"  [{status}] {res.title}: {res.verification_message}")
    lines.append("=" * 118)

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark comparing Monolithic Profile Locking vs Entity DAG Partition Locking."
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL. If omitted, uses simulation engine.",
    )
    parser.add_argument(
        "--writers",
        type=int,
        default=DEFAULT_WRITER_COUNT,
        help=f"Number of concurrent writer threads (default: {DEFAULT_WRITER_COUNT}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write JSON benchmark report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout instead of ASCII table.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail closed if database-url is unavailable instead of using simulation.",
    )

    args = parser.parse_args(argv)

    try:
        report = run_dag_concurrency_benchmark(
            database_url=args.database_url,
            writer_count=args.writers,
            use_simulation_fallback=not args.no_fallback,
        )

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.summary_table)

        return 0 if report.all_invariants_passed else 1

    except (OSError, RuntimeError, TypeError, ValueError, SQLAlchemyError) as exc:
        print(f"ERROR: Benchmark execution failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
