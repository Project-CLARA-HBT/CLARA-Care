"""Concurrency verification for GLHS DAG Entity-Partitioned Versioning.

Validates that DAG entity-partitioned versioning eliminates profile-level false-stale
conflicts by isolating concurrency control to individual entity partitions
(domain, semantic_key). When 16 concurrent writers mutate independent entity
partitions of the same profile simultaneously, 100% of commits succeed with 0
false-stale conflicts.

Test scenarios:
1. 16 concurrent writers on independent entities of the same profile (0 false-stale, 100% success).
2. 16 concurrent writers on multi-domain disjoint DAG partition clusters (deadlock-free).
3. Multi-round concurrent version progression across disjoint partitions (5 rounds x 16 writers).
4. Negative control / contrast: 16 concurrent writers on the same single entity partition
   (yielding exactly 1 winner and 15 true-stale conflicts).
5. Opt-in PostgreSQL integration test on real row locks (SELECT ... FOR UPDATE).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsEntityVersionPartition,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
    get_or_create_entity_partition,
    increment_partition_versions,
    lock_entity_partitions,
)
from clara_api.glhs.domain import GlhsInvariantError

POSTGRES_URL = os.getenv("GLHS_TEST_POSTGRES_URL", "")
SAFETY_ACKNOWLEDGED = (
    os.getenv("ALLOW_GLHS_POSTGRES_CONCURRENCY_TEST", "").strip().lower() == "true"
)


@dataclass(frozen=True)
class WriterResult:
    writer_index: int
    semantic_key: str
    status: str  # "success" | "stale_conflict" | "error"
    resulting_version: int | None
    error_message: str | None


def _init_sqlite_wal_engine(db_path: str) -> Engine:
    """Create a SQLite engine configured with WAL mode and busy timeout for concurrency."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 60.0, "check_same_thread": False},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA busy_timeout=60000;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.commit()
    Base.metadata.create_all(engine)
    return engine


def _seed_profile(engine: Engine) -> int:
    """Seed a user and PHR profile, returning the profile id."""
    with Session(engine) as db:
        user = User(
            email=f"glhs-partition-{uuid4().hex}@example.test",
            hashed_password="hashed_test_password",
            role="normal",
        )
        db.add(user)
        db.flush()
        profile = PhrProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        return profile.id


def _execute_partition_write(
    engine: Engine,
    *,
    profile_id: int,
    domain: str,
    semantic_key: str,
    expected_version: int,
    barrier: Barrier,
    writer_index: int,
) -> WriterResult:
    """Simulate a single worker transaction mutating an entity partition with optimistic check."""
    # Synchronize all threads so they attempt lock acquisition and commit concurrently
    barrier.wait(timeout=30)
    with Session(engine) as session:
        try:
            with session.begin():
                # 1. Acquire canonical row lock on entity partition
                locked = lock_entity_partitions(
                    session,
                    profile_id=profile_id,
                    partitions=[(domain, semantic_key)],
                    policy_version=COMMITMENT_POLICY_VERSION,
                )
                assert len(locked) == 1
                partition = locked[0]

                # 2. Optimistic version verification on the entity partition
                if partition.state_version != expected_version:
                    err_msg = (
                        f"stale_partition_version: expected {expected_version}, "
                        f"got {partition.state_version}"
                    )
                    return WriterResult(
                        writer_index=writer_index,
                        semantic_key=semantic_key,
                        status="stale_conflict",
                        resulting_version=partition.state_version,
                        error_message=err_msg,
                    )

                # 3. Advance local entity partition state version (DAG Node)
                increment_partition_versions(
                    session,
                    partitions=locked,
                    policy_version=COMMITMENT_POLICY_VERSION,
                )
                resulting_ver = partition.state_version

            return WriterResult(
                writer_index=writer_index,
                semantic_key=semantic_key,
                status="success",
                resulting_version=resulting_ver,
                error_message=None,
            )
        except GlhsInvariantError as exc:
            session.rollback()
            return WriterResult(
                writer_index=writer_index,
                semantic_key=semantic_key,
                status="stale_conflict",
                resulting_version=None,
                error_message=str(exc),
            )
        except Exception as exc:
            session.rollback()
            return WriterResult(
                writer_index=writer_index,
                semantic_key=semantic_key,
                status="error",
                resulting_version=None,
                error_message=str(exc),
            )


# ==============================================================================
# Pytest Test Suite (SQLite WAL Concurrency)
# ==============================================================================


def test_16_concurrent_writers_disjoint_partitions_zero_false_stale() -> None:
    """Simulate 16 concurrent writers on independent entities of the same profile.

    Verifies that:
    1. 0 false-stale conflicts occur across disjoint entity partitions.
    2. 100% of commits (16/16) succeed.
    3. Each entity partition independently advances its state_version from 1 to 2.
    """
    writer_count = 16
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_16_disjoint_writers.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        # Pre-seed the 16 independent entity partitions at state_version = 1
        with Session(engine) as db:
            for idx in range(writer_count):
                get_or_create_entity_partition(
                    db,
                    profile_id=profile_id,
                    domain="medications",
                    semantic_key=f"medication:rx-{idx}",
                    policy_version=COMMITMENT_POLICY_VERSION,
                )
            db.commit()

        # Barrier to release all 16 writers simultaneously
        barrier = Barrier(writer_count)

        def worker_task(idx: int) -> WriterResult:
            return _execute_partition_write(
                engine,
                profile_id=profile_id,
                domain="medications",
                semantic_key=f"medication:rx-{idx}",
                expected_version=1,
                barrier=barrier,
                writer_index=idx,
            )

        with ThreadPoolExecutor(max_workers=writer_count) as pool:
            results = list(pool.map(worker_task, range(writer_count)))

        # Verify results
        successes = [r for r in results if r.status == "success"]
        stale_conflicts = [r for r in results if r.status == "stale_conflict"]
        errors = [r for r in results if r.status == "error"]

        assert len(errors) == 0, f"Unexpected errors during concurrent writes: {errors}"
        assert len(stale_conflicts) == 0, f"False-stale conflicts detected: {stale_conflicts}"
        assert len(successes) == writer_count, (
            f"Expected {writer_count} successes, got {len(successes)}"
        )

        # Verify DB persisted state
        with Session(engine) as db:
            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()

            assert len(partitions) == writer_count
            for partition in partitions:
                assert partition.state_version == 2, (
                    f"Partition {partition.semantic_key} has "
                    f"state_version={partition.state_version}, expected 2"
                )
        engine.dispose()


def test_16_concurrent_writers_multi_domain_dag_partitions() -> None:
    """Simulate 16 concurrent writers operating on compound disjoint DAG partition sets.

    Each writer mutates 3 distinct entity partitions across domains
    ('medications', 'observations', 'conditions').
    Canonical sorted locking in lock_entity_partitions ensures deadlock freedom.
    Verifies 100% success rate (16/16) and 48 partitions correctly versioned.
    """
    writer_count = 16
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_multi_domain_dag.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        barrier = Barrier(writer_count)

        def worker_task(idx: int) -> tuple[int, str, list[str]]:
            barrier.wait(timeout=30)
            target_partitions = [
                ("medications", f"medication:drug-{idx}"),
                ("observations", f"observation:vital-{idx}"),
                ("conditions", f"condition:diag-{idx}"),
            ]
            with Session(engine) as session:
                try:
                    locked = lock_entity_partitions(
                        session,
                        profile_id=profile_id,
                        partitions=target_partitions,
                        policy_version=COMMITMENT_POLICY_VERSION,
                    )
                    assert len(locked) == 3
                    for p in locked:
                        assert p.state_version == 1
                    increment_partition_versions(session, partitions=locked)
                    session.commit()
                    return (idx, "success", [p.semantic_key for p in locked])
                except Exception as exc:
                    session.rollback()
                    return (idx, f"failed:{exc}", [])

        with ThreadPoolExecutor(max_workers=writer_count) as pool:
            results = list(pool.map(worker_task, range(writer_count)))

        successes = [r for r in results if r[1] == "success"]
        assert len(successes) == writer_count, f"Multi-domain writes failed: {results}"

        with Session(engine) as db:
            total_partitions = db.scalar(
                select(func.count(GlhsEntityVersionPartition.id)).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            )
            assert total_partitions == writer_count * 3  # 48 partitions

            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()
            for p in partitions:
                assert p.state_version == 2
        engine.dispose()


def test_multi_round_concurrent_progression_disjoint_partitions() -> None:
    """Simulate 5 consecutive rounds of 16 concurrent writers on disjoint partitions.

    Verifies:
    1. Total 80 commits (5 rounds * 16 writers) with 100% success rate.
    2. 0 false-stale conflicts across all rounds.
    3. Final state_version = 6 for each of the 16 entity partitions.
    """
    writer_count = 16
    rounds = 5
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_multi_round_progression.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        for current_round in range(rounds):
            expected_ver = current_round + 1
            round_barrier = Barrier(writer_count)

            def make_worker(round_expected: int, sync_barrier: Barrier):
                def worker_task(idx: int) -> WriterResult:
                    return _execute_partition_write(
                        engine,
                        profile_id=profile_id,
                        domain="medications",
                        semantic_key=f"medication:rx-{idx}",
                        expected_version=round_expected,
                        barrier=sync_barrier,
                        writer_index=idx,
                    )

                return worker_task

            with ThreadPoolExecutor(max_workers=writer_count) as pool:
                task = make_worker(expected_ver, round_barrier)
                results = list(pool.map(task, range(writer_count)))

            successes = [r for r in results if r.status == "success"]
            assert len(successes) == writer_count, (
                f"Round {current_round + 1} failed: {results}"
            )

        with Session(engine) as db:
            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()

            assert len(partitions) == writer_count
            for p in partitions:
                assert p.state_version == 1 + rounds  # 1 initial + 5 rounds = 6
        engine.dispose()


def test_negative_control_single_partition_true_stale_contrast() -> None:
    """Negative control: 16 concurrent writers race on the SAME entity partition.

    Contrasts with disjoint partitions to verify that:
    1. Contention on the same partition produces 1 winner and 15 true-stale conflicts.
    2. The partition versioning mechanism accurately distinguishes true from false conflicts.
    """
    writer_count = 16
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_single_partition_race.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        shared_semantic_key = "medication:same-slot"
        with Session(engine) as db:
            get_or_create_entity_partition(
                db,
                profile_id=profile_id,
                domain="medications",
                semantic_key=shared_semantic_key,
                policy_version=COMMITMENT_POLICY_VERSION,
            )
            db.commit()

        barrier = Barrier(writer_count)

        def worker_task(idx: int) -> WriterResult:
            return _execute_partition_write(
                engine,
                profile_id=profile_id,
                domain="medications",
                semantic_key=shared_semantic_key,
                expected_version=1,
                barrier=barrier,
                writer_index=idx,
            )

        with ThreadPoolExecutor(max_workers=writer_count) as pool:
            results = list(pool.map(worker_task, range(writer_count)))

        successes = [r for r in results if r.status == "success"]
        stale_conflicts = [r for r in results if r.status == "stale_conflict"]

        # Exactly 1 winner advances state_version; the remaining 15 get genuine stale conflicts
        assert len(successes) == 1, f"Expected 1 winner, got {len(successes)}"
        assert len(stale_conflicts) == writer_count - 1, (
            f"Expected {writer_count - 1} stale conflicts, got {len(stale_conflicts)}"
        )

        with Session(engine) as db:
            partition = db.scalar(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id,
                    GlhsEntityVersionPartition.domain == "medications",
                    GlhsEntityVersionPartition.semantic_key == shared_semantic_key,
                )
            )
            assert partition is not None
            assert partition.state_version == 2
        engine.dispose()


# ==============================================================================
# Opt-in PostgreSQL Integration Test (Real Row Locking with SELECT FOR UPDATE)
# ==============================================================================


def _isolated_postgres_engines(url: str, schema: str) -> tuple[Engine, Engine]:
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    return admin, isolated


def run_postgres_16_writer_partition_concurrency(url: str) -> None:
    schema = f"glhs_entity_partition_test_{uuid4().hex}"
    admin, isolated = _isolated_postgres_engines(url, schema)
    writer_count = 16
    try:
        Base.metadata.create_all(isolated)
        profile_id = _seed_profile(isolated)

        # Pre-seed 16 partitions
        with Session(isolated) as db:
            for idx in range(writer_count):
                get_or_create_entity_partition(
                    db,
                    profile_id=profile_id,
                    domain="medications",
                    semantic_key=f"medication:pg-rx-{idx}",
                    policy_version=COMMITMENT_POLICY_VERSION,
                )
            db.commit()

        barrier = Barrier(writer_count)

        def worker_task(idx: int) -> WriterResult:
            return _execute_partition_write(
                isolated,
                profile_id=profile_id,
                domain="medications",
                semantic_key=f"medication:pg-rx-{idx}",
                expected_version=1,
                barrier=barrier,
                writer_index=idx,
            )

        with ThreadPoolExecutor(max_workers=writer_count) as pool:
            results = list(pool.map(worker_task, range(writer_count)))

        successes = [r for r in results if r.status == "success"]
        stale_conflicts = [r for r in results if r.status == "stale_conflict"]
        errors = [r for r in results if r.status == "error"]

        if (
            len(errors) > 0
            or len(stale_conflicts) > 0
            or len(successes) != writer_count
        ):
            raise AssertionError(
                f"PostgreSQL concurrency contract failed: successes={len(successes)}, "
                f"stale_conflicts={len(stale_conflicts)}, errors={errors}"
            )

        with Session(isolated) as db:
            count = db.scalar(
                select(func.count(GlhsEntityVersionPartition.id)).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            )
            if count != writer_count:
                raise AssertionError(f"Expected {writer_count} partitions, got {count}")

            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()
            for p in partitions:
                if p.state_version != 2:
                    raise AssertionError(
                        f"Partition {p.semantic_key} has "
                        f"state_version={p.state_version}, expected 2"
                    )
    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@unittest.skipUnless(
    POSTGRES_URL and SAFETY_ACKNOWLEDGED,
    "requires isolated PostgreSQL URL and explicit safety acknowledgement",
)
class GlhsEntityPartitionPostgresConcurrencyTest(unittest.TestCase):
    def test_postgres_16_concurrent_disjoint_writers(self) -> None:
        run_postgres_16_writer_partition_concurrency(POSTGRES_URL)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
