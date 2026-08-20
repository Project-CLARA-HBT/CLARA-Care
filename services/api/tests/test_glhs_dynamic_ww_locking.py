"""Tests for Dynamic DAG Entity Lock Acquisition and Wound-Wait Deadlock Prevention.

Validates that:
1. Dynamic multi-hop DAG node expansion is deadlock-free under Wound-Wait priority ordering.
2. Older transactions preempt (wound) younger holders; younger transactions wait for older holders.
3. Canonical sort order is strictly preserved across coordinate resolution and batch locking.
4. Snapshot version violations and stale partition reads are detected and rejected.
5. DynamicDAGLeaseSession manages lease lifecycles cleanly.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
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
    DynamicDAGLeaseSession,
    DynamicDAGLockManager,
    DynamicLeaseContext,
    EntityDAGCoordinate,
    LeaseState,
    _resolve_dependency_partition_keys,
    acquire_dynamic_dag_lease,
    canonical_entity_sort_key,
    canonical_sort_coordinates,
    expand_dynamic_dag_lease,
    get_dag_lock_manager,
    get_or_create_entity_partition,
    increment_partition_versions,
    lock_entity_partitions,
    release_dynamic_dag_lease,
    reset_dag_lock_manager,
    resolve_coordinate,
    validate_dynamic_dag_snapshot_invariance,
)
from clara_api.glhs.domain import GlhsInvariantError


@pytest.fixture(autouse=True)
def _reset_lock_manager():
    """Ensure a clean lock manager state for every test."""
    reset_dag_lock_manager()
    yield
    reset_dag_lock_manager()


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


@pytest.fixture()
def db() -> Iterator[Session]:
    """Provide an in-memory SQLite database session with seeded user and profile."""
    engine = create_engine("sqlite://", pool_pre_ping=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            email=f"ww-test-{uuid4().hex}@example.test",
            hashed_password="test_hash_password",
            role="normal",
        )
        session.add(user)
        session.flush()
        profile = PhrProfile(user_id=user.id)
        session.add(profile)
        session.commit()
        yield session


def _seed_profile(engine: Engine) -> int:
    with Session(engine) as session:
        user = User(
            email=f"ww-seed-{uuid4().hex}@example.test",
            hashed_password="test_hash_password",
            role="normal",
        )
        session.add(user)
        session.flush()
        profile = PhrProfile(user_id=user.id)
        session.add(profile)
        session.commit()
        return profile.id


# ==============================================================================
# 1. Dynamic Node Expansion Without Deadlocks
# ==============================================================================


def test_dynamic_dag_two_agent_inverse_expansion_deadlock_free() -> None:
    """Two agents dynamically expand DAG dependencies in conflicting/inverse orders.

    Agent 1 (Older, ts=10.0): acquires Med A, then dynamically expands to Cond B.
    Agent 2 (Younger, ts=20.0): acquires Cond B, then dynamically expands to Med A.

    Without Wound-Wait, this dynamic order causes a deadlock (A -> B vs B -> A).
    With Wound-Wait:
    - Agent 2 requests Med A (held by older Agent 1) and waits.
    - Agent 1 requests Cond B (held by younger Agent 2), wounds Agent 2, preempts Cond B,
      and completes successfully.
    - Agent 2 wakes up wounded and aborts.
    Deadlock is prevented 100%.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_two_agent_inverse.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        # Seed partitions at version 1
        with Session(engine) as session:
            get_or_create_entity_partition(
                session, profile_id=profile_id, domain="medications", semantic_key="rx-A"
            )
            get_or_create_entity_partition(
                session, profile_id=profile_id, domain="conditions", semantic_key="diag-B"
            )
            session.commit()

        barrier = Barrier(2)
        results: dict[str, str] = {}

        def agent_1_older() -> None:
            """Older agent: ts=10.0"""
            with Session(engine) as session:
                try:
                    with DynamicDAGLeaseSession(
                        session,
                        profile_id=profile_id,
                        initial_partitions=[("medications", "rx-A")],
                        timestamp=10.0,
                        policy_version=COMMITMENT_POLICY_VERSION,
                    ) as lease:
                        # Synchronize so Agent 2 has acquired Cond B
                        barrier.wait(timeout=5.0)
                        time.sleep(0.05)
                        # Dynamically expand to Cond B
                        lease.expand([("conditions", "diag-B")])
                        lease.validate_snapshots()
                        # Increment partition versions to simulate commit
                        increment_partition_versions(session, partitions=lease.locked_partitions)
                        session.commit()
                        results["agent_1"] = "success"
                except Exception as exc:
                    session.rollback()
                    results["agent_1"] = f"failed:{exc}"

        def agent_2_younger() -> None:
            """Younger agent: ts=20.0"""
            with Session(engine) as session:
                try:
                    with DynamicDAGLeaseSession(
                        session,
                        profile_id=profile_id,
                        initial_partitions=[("conditions", "diag-B")],
                        timestamp=20.0,
                        policy_version=COMMITMENT_POLICY_VERSION,
                        timeout=2.0,
                    ) as lease:
                        # Synchronize so Agent 1 has acquired Med A
                        barrier.wait(timeout=5.0)
                        # Dynamically expand to Med A (held by Agent 1)
                        lease.expand([("medications", "rx-A")])
                        lease.validate_snapshots()
                        increment_partition_versions(session, partitions=lease.locked_partitions)
                        session.commit()
                        results["agent_2"] = "success"
                except GlhsInvariantError as exc:
                    session.rollback()
                    results["agent_2"] = f"wounded:{exc}"
                except Exception as exc:
                    session.rollback()
                    results["agent_2"] = f"error:{exc}"

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(agent_1_older)
            f2 = pool.submit(agent_2_younger)
            f1.result()
            f2.result()

        assert results["agent_1"] == "success"
        assert "wound_wait_preempted" in results["agent_2"] or "wounded" in results["agent_2"]
        engine.dispose()


def test_dynamic_dag_multi_agent_ring_deadlock_free() -> None:
    """4 agents dynamically expand dependencies in a circular ring (A->B, B->C, C->D, D->A).

    Agent 0 (ts=10): holds A, expands to B
    Agent 1 (ts=20): holds B, expands to C
    Agent 2 (ts=30): holds C, expands to D
    Agent 3 (ts=40): holds D, expands to A

    Wound-Wait ordering ensures all circular dependencies are resolved via preemption
    without deadlocks. Oldest agent ($ts=10$) is guaranteed to win.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_multi_agent_ring.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        nodes = ["node-0", "node-1", "node-2", "node-3"]
        with Session(engine) as session:
            for node in nodes:
                get_or_create_entity_partition(
                    session, profile_id=profile_id, domain="medications", semantic_key=node
                )
            session.commit()

        agent_count = 4
        barrier = Barrier(agent_count)
        results: dict[int, str] = {}

        def agent_task(idx: int) -> None:
            initial_node = nodes[idx]
            next_node = nodes[(idx + 1) % agent_count]
            ts = 10.0 * (idx + 1)  # 10.0, 20.0, 30.0, 40.0

            with Session(engine) as session:
                try:
                    with DynamicDAGLeaseSession(
                        session,
                        profile_id=profile_id,
                        initial_partitions=[("medications", initial_node)],
                        timestamp=ts,
                        timeout=2.0,
                    ) as lease:
                        barrier.wait(timeout=5.0)
                        time.sleep(0.02 * (agent_count - idx))
                        lease.expand([("medications", next_node)])
                        lease.validate_snapshots()
                        increment_partition_versions(session, partitions=lease.locked_partitions)
                        session.commit()
                        results[idx] = "success"
                except GlhsInvariantError as exc:
                    session.rollback()
                    results[idx] = f"preempted:{exc}"
                except Exception as exc:
                    session.rollback()
                    results[idx] = f"error:{exc}"

        with ThreadPoolExecutor(max_workers=agent_count) as pool:
            futures = [pool.submit(agent_task, i) for i in range(agent_count)]
            for f in futures:
                f.result()

        # Agent 0 (oldest, ts=10) must succeed
        assert results[0] == "success"
        # All other agents either succeeded or were cleanly preempted with 0 hangs
        for idx in range(agent_count):
            assert idx in results
            assert not results[idx].startswith("error")
        engine.dispose()


def test_dynamic_dag_multi_hop_incremental_expansion(db: Session) -> None:
    """A reasoning chain sequentially discovers 5 hops of entity dependencies."""
    profile = db.query(PhrProfile).one()
    profile_id = profile.id

    hops = [
        ("medications", "metformin-500"),
        ("conditions", "type-2-diabetes"),
        ("observations", "hba1c-lab"),
        ("allergies", "sulfa-drugs"),
        ("medications", "glipizide-5"),
    ]

    for domain, key in hops:
        get_or_create_entity_partition(
            db, profile_id=profile_id, domain=domain, semantic_key=key
        )
    db.commit()

    with DynamicDAGLeaseSession(
        db,
        profile_id=profile_id,
        initial_partitions=[hops[0]],
        timestamp=100.0,
    ) as lease:
        assert len(lease.locked_partitions) == 1
        assert lease.context is not None
        assert len(lease.context.held_coordinates) == 1

        for hop_idx, next_hop in enumerate(hops[1:], start=2):
            newly_locked = lease.expand([next_hop])
            assert len(newly_locked) == 1
            assert len(lease.locked_partitions) == hop_idx
            assert len(lease.context.held_coordinates) == hop_idx

        lease.validate_snapshots()
        increment_partition_versions(db, partitions=lease.locked_partitions)
        db.commit()

    # Verify all 5 partitions were incremented to state_version = 2
    for domain, key in hops:
        partition = db.execute(
            select(GlhsEntityVersionPartition).where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                GlhsEntityVersionPartition.domain == domain,
                GlhsEntityVersionPartition.semantic_key == key,
            )
        ).scalar_one()
        assert partition.state_version == 2


# ==============================================================================
# 2. Wound-Wait Preemption Logic
# ==============================================================================


def test_ww_older_wounds_younger_holder() -> None:
    """Older transaction (lower timestamp) wounds and preempts younger lock holder."""
    lock_mgr = get_dag_lock_manager()
    assert isinstance(lock_mgr, DynamicDAGLockManager)
    profile_id = 1
    coord = EntityDAGCoordinate(profile_id=profile_id, domain="medications", semantic_key="rx-1")

    # Younger transaction (ts=200) acquires lock first
    txn_young = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=200.0)
    assert isinstance(txn_young, DynamicLeaseContext)
    assert lock_mgr.acquire_coordinate(txn_young, coord) is True
    assert coord in txn_young.held_coordinates
    assert txn_young.is_active

    # Older transaction (ts=100) requests the same lock
    txn_old = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=100.0)
    assert lock_mgr.acquire_coordinate(txn_old, coord) is True
    assert coord in txn_old.held_coordinates
    assert coord not in txn_young.held_coordinates

    # Verify younger transaction was wounded
    assert txn_young.is_wounded
    assert txn_young.state == LeaseState.WOUNDED
    assert "preempted_by_older_txn" in (txn_young.wound_reason or "")

    # Subsequent access by younger transaction fails fast
    with pytest.raises(GlhsInvariantError, match="wound_wait_preempted"):
        txn_young.check_not_wounded()


def test_ww_younger_waits_for_older_holder_and_acquires_on_release() -> None:
    """Younger transaction waits for older holder and acquires lock after release."""
    lock_mgr = get_dag_lock_manager()
    profile_id = 1
    coord = EntityDAGCoordinate(profile_id=profile_id, domain="observations", semantic_key="bp-1")

    # Older transaction (ts=100) acquires lock
    txn_old = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=100.0)
    assert lock_mgr.acquire_coordinate(txn_old, coord) is True

    # Younger transaction (ts=200) attempts to acquire in background thread
    txn_young = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=200.0)
    young_acquired = threading.Event()

    def younger_worker() -> None:
        success = lock_mgr.acquire_coordinate(txn_young, coord, timeout=3.0)
        if success:
            young_acquired.set()

    thread = threading.Thread(target=younger_worker)
    thread.start()

    time.sleep(0.05)
    # Younger must be waiting, NOT wounded, and older still holds lock
    assert txn_young.state == LeaseState.WAITING
    assert txn_old.is_active
    assert not young_acquired.is_set()

    # Older releases transaction
    lock_mgr.release_transaction(txn_old)

    # Younger should now wake up and acquire lock
    assert young_acquired.wait(timeout=2.0) is True
    thread.join(timeout=1.0)

    assert coord in txn_young.held_coordinates
    assert txn_young.is_active


def test_ww_younger_timeout_when_older_does_not_release() -> None:
    """Younger transaction times out when waiting for an older holder that does not release."""
    lock_mgr = get_dag_lock_manager()
    profile_id = 1
    coord = EntityDAGCoordinate(profile_id=profile_id, domain="conditions", semantic_key="diag-1")

    txn_old = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=100.0)
    assert lock_mgr.acquire_coordinate(txn_old, coord) is True

    txn_young = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=200.0)
    with pytest.raises(GlhsInvariantError, match="lock_acquisition_timeout"):
        lock_mgr.acquire_coordinate(txn_young, coord, timeout=0.1)


def test_ww_reentrant_acquisition_succeeds() -> None:
    """Re-entrant lock acquisition on already-held coordinate succeeds as a no-op."""
    lock_mgr = get_dag_lock_manager()
    profile_id = 1
    coord = EntityDAGCoordinate(profile_id=profile_id, domain="medications", semantic_key="rx-1")

    txn = lock_mgr.begin_transaction(profile_id=profile_id, timestamp=100.0)
    assert lock_mgr.acquire_coordinate(txn, coord) is True
    # Re-acquire
    assert lock_mgr.acquire_coordinate(txn, coord) is True
    assert len(txn.held_coordinates) == 1


def test_ww_cross_profile_scope_rejection() -> None:
    """Attempting to acquire coordinate from a different profile is rejected."""
    lock_mgr = get_dag_lock_manager()
    txn = lock_mgr.begin_transaction(profile_id=1, timestamp=100.0)
    coord_other = EntityDAGCoordinate(profile_id=2, domain="medications", semantic_key="rx-1")

    with pytest.raises(GlhsInvariantError, match="commitment_scope_forbidden"):
        lock_mgr.acquire_coordinate(txn, coord_other)


# ==============================================================================
# 3. Canonical Sort Order Preservation
# ==============================================================================


def test_canonical_sort_order_preservation() -> None:
    """Verify deterministic canonical sort order across domain coordinates and tuples."""
    coords = [
        EntityDAGCoordinate(profile_id=1, domain="observations", semantic_key="vital-B"),
        EntityDAGCoordinate(profile_id=1, domain="medications", semantic_key="drug-A"),
        EntityDAGCoordinate(profile_id=1, domain="allergies", semantic_key="allergy-Z"),
        EntityDAGCoordinate(profile_id=1, domain="conditions", semantic_key="diag-C"),
    ]
    sorted_coords = canonical_sort_coordinates(coords)
    expected_order = ["allergies", "conditions", "medications", "observations"]
    assert [c.domain for c in sorted_coords] == expected_order

    # Verify canonical_entity_sort_key
    assert canonical_entity_sort_key(coords[0]) == (1, "observations", "vital-B")
    assert canonical_entity_sort_key(("medications", "drug-A")) == ("medications", "drug-A")
    assert canonical_entity_sort_key((1, "allergies", "allergy-Z")) == (1, "allergies", "allergy-Z")

    # Cross-profile sorting
    multi_profile = [
        EntityDAGCoordinate(profile_id=2, domain="allergies", semantic_key="a"),
        EntityDAGCoordinate(profile_id=1, domain="observations", semantic_key="z"),
    ]
    sorted_mp = canonical_sort_coordinates(multi_profile)
    assert sorted_mp[0].profile_id == 1
    assert sorted_mp[1].profile_id == 2

    # Tuple sorting
    tuples = [("observations", "k2"), ("allergies", "k1"), ("conditions", "k3")]
    sorted_tuples = canonical_sort_coordinates(tuples)
    assert sorted_tuples == [("allergies", "k1"), ("conditions", "k3"), ("observations", "k2")]


def test_domain_normalization_and_dependency_resolution() -> None:
    """Verify domain normalization mapping and dependency coordinate resolution."""
    # Prefix dependency resolution
    c1 = resolve_coordinate(profile_id=1, domain_or_dep="medication:rx-123")
    assert c1.domain == "medications"
    assert c1.semantic_key == "rx-123"

    c2 = resolve_coordinate(profile_id=1, domain_or_dep="allergy", semantic_key="peanut")
    assert c2.domain == "allergies"
    assert c2.semantic_key == "peanut"

    # Dependency partition key resolution helper
    deps = ("medication:aspirin", "condition:cad", "vital_bp")
    resolved = _resolve_dependency_partition_keys("observations", deps)
    assert ("medications", "aspirin") in resolved
    assert ("conditions", "cad") in resolved
    assert ("observations", "vital_bp") in resolved

    # Invalid domain rejection
    with pytest.raises(GlhsInvariantError, match="commitment_domain_forbidden"):
        resolve_coordinate(profile_id=1, domain_or_dep="invalid_domain", semantic_key="key")

    with pytest.raises(GlhsInvariantError, match="invalid_entity_coordinate"):
        resolve_coordinate(profile_id=1, domain_or_dep="invalid_no_colon")


def test_batch_acquisition_canonical_ordering(db: Session) -> None:
    """Batch acquisition automatically sorts unsorted coordinates in canonical order."""
    profile = db.query(PhrProfile).one()
    profile_id = profile.id

    unsorted_partitions = [
        ("observations", "pulse"),
        ("allergies", "pollen"),
        ("conditions", "asthma"),
        ("medications", "albuterol"),
    ]

    txn, locked = acquire_dynamic_dag_lease(
        db,
        profile_id=profile_id,
        partitions=unsorted_partitions,
        timestamp=50.0,
    )
    assert len(locked) == 4
    # Locked DB partitions must be canonically ordered
    assert locked[0].domain == "allergies"
    assert locked[1].domain == "conditions"
    assert locked[2].domain == "medications"
    assert locked[3].domain == "observations"

    # Verify lock_entity_partitions directly returns canonically sorted rows
    direct_locked = lock_entity_partitions(
        db,
        profile_id=profile_id,
        partitions=unsorted_partitions,
    )
    assert [r.domain for r in direct_locked] == [
        "allergies",
        "conditions",
        "medications",
        "observations",
    ]

    release_dynamic_dag_lease(txn)


# ==============================================================================
# 4. Rejection of Snapshot Violations
# ==============================================================================


def test_rejection_of_snapshot_version_violation_on_acquisition(db: Session) -> None:
    """Acquiring a partition lease with a stale expected version is rejected."""
    profile = db.query(PhrProfile).one()
    profile_id = profile.id

    # Create partition at state_version = 2
    partition = get_or_create_entity_partition(
        db, profile_id=profile_id, domain="medications", semantic_key="stale-test"
    )
    partition.state_version = 2
    db.commit()

    # Attempt to acquire with expected_version = 1
    with pytest.raises(GlhsInvariantError, match="snapshot_version_violation"):
        acquire_dynamic_dag_lease(
            db,
            profile_id=profile_id,
            partitions=[("medications", "stale-test")],
            expected_versions={("medications", "stale-test"): 1},
        )


def test_rejection_of_snapshot_version_violation_during_dynamic_expansion(db: Session) -> None:
    """Snapshot violation detected when intervening commit mutates an earlier hop."""
    profile = db.query(PhrProfile).one()
    profile_id = profile.id

    part_a = get_or_create_entity_partition(
        db, profile_id=profile_id, domain="medications", semantic_key="hop-A"
    )
    get_or_create_entity_partition(
        db, profile_id=profile_id, domain="conditions", semantic_key="hop-B"
    )
    db.commit()

    with DynamicDAGLeaseSession(
        db,
        profile_id=profile_id,
        initial_partitions=[("medications", "hop-A")],
        timestamp=100.0,
    ) as lease:
        assert lease.context is not None
        # Record snapshot version 1 for hop-A
        coord_a = EntityDAGCoordinate(
            profile_id=profile_id, domain="medications", semantic_key="hop-A"
        )
        lease.context.record_snapshot_version(coord_a, 1)

        # Intervening write mutates hop-A to state_version = 2
        part_a.state_version = 2
        db.flush()

        # Dynamically expand to hop-B using expand_dynamic_dag_lease helper
        newly_locked = expand_dynamic_dag_lease(
            db,
            txn_context=lease.context,
            additional_partitions=[("conditions", "hop-B")],
        )
        assert len(newly_locked) == 1

        # Validating snapshots must now fail because hop-A version changed from 1 to 2
        with pytest.raises(GlhsInvariantError, match="snapshot_version_violation"):
            validate_dynamic_dag_snapshot_invariance(db, txn_context=lease.context)


def test_wounded_transaction_rejected_on_subsequent_operations(db: Session) -> None:
    """A wounded transaction cannot perform subsequent expansions or snapshot validations."""
    profile = db.query(PhrProfile).one()
    profile_id = profile.id

    with DynamicDAGLeaseSession(
        db,
        profile_id=profile_id,
        initial_partitions=[("medications", "rx-w1")],
        timestamp=200.0,
    ) as lease:
        assert lease.context is not None
        # Simulate preemption by older transaction
        lease.context.mark_wounded("preempted_in_test")

        with pytest.raises(GlhsInvariantError, match="wound_wait_preempted"):
            lease.expand([("conditions", "cond-w2")])

        with pytest.raises(GlhsInvariantError, match="wound_wait_preempted"):
            lease.validate_snapshots()


# ==============================================================================
# 5. Concurrency Stress Test with 16 Concurrent Agents
# ==============================================================================


def test_concurrent_16_agents_dynamic_dag_expansion() -> None:
    """16 concurrent agents dynamically expand DAG coordinates under high contention.

    Verifies:
    - 0 unhandled exceptions or thread deadlocks / hangs.
    - All completions are either clean commits or deterministic Wound-Wait preemptions.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_16_agents_dynamic.db")
        engine = _init_sqlite_wal_engine(db_path)
        profile_id = _seed_profile(engine)

        agent_count = 16
        partition_keys = [f"entity-{i}" for i in range(8)]
        with Session(engine) as session:
            for k in partition_keys:
                get_or_create_entity_partition(
                    session, profile_id=profile_id, domain="medications", semantic_key=k
                )
            session.commit()

        barrier = Barrier(agent_count)
        results: list[dict[str, str | int]] = []
        lock = threading.Lock()

        def agent_worker(agent_id: int) -> None:
            # Each agent picks 2 partitions based on agent_id
            k1 = partition_keys[agent_id % len(partition_keys)]
            k2 = partition_keys[(agent_id + 3) % len(partition_keys)]
            ts = float(agent_id + 1) * 10.0

            # Synchronize all threads to start lease acquisition concurrently
            barrier.wait(timeout=10.0)

            with Session(engine) as session:
                try:
                    with DynamicDAGLeaseSession(
                        session,
                        profile_id=profile_id,
                        initial_partitions=[("medications", k1)],
                        timestamp=ts,
                        timeout=2.0,
                    ) as lease:
                        time.sleep(0.01)
                        lease.expand([("medications", k2)])
                        lease.validate_snapshots()
                        increment_partition_versions(session, partitions=lease.locked_partitions)
                        session.commit()
                        with lock:
                            results.append({"agent_id": agent_id, "status": "success"})
                except GlhsInvariantError as exc:
                    session.rollback()
                    with lock:
                        results.append({"agent_id": agent_id, "status": f"preempted:{exc}"})
                except Exception as exc:
                    session.rollback()
                    with lock:
                        results.append(
                            {
                                "agent_id": agent_id,
                                "status": f"error:{type(exc).__name__}:{exc}",
                            }
                        )

        with ThreadPoolExecutor(max_workers=agent_count) as pool:
            futures = [pool.submit(agent_worker, i) for i in range(agent_count)]
            for f in futures:
                f.result()

        assert len(results) == agent_count
        errors = [r for r in results if str(r["status"]).startswith("error")]
        assert len(errors) == 0, f"Unexpected errors during concurrent dynamic expansion: {errors}"

        successes = [r for r in results if r["status"] == "success"]
        # At least some agents must succeed
        assert len(successes) >= 1
        engine.dispose()
