"""Unit and formal invariant tests for Wait-For Graph deadlock analyzer."""

from __future__ import annotations

from evaluation.glhs_systems_benchmark.deadlock_analyzer import (
    CanonicalLockManager,
    DynamicWaitForGraph,
    run_deadlock_analysis,
)


def test_wait_for_graph_cycle_detection() -> None:
    wfg = DynamicWaitForGraph()

    # Thread A acquires Lock 1
    wfg.register_acquired("Thread_A", "Lock_1")
    # Thread B acquires Lock 2
    wfg.register_acquired("Thread_B", "Lock_2")

    # Thread A waits for Lock 2 (held by Thread B) -> edge A -> B
    cycle1 = wfg.register_wait("Thread_A", "Lock_2")
    assert cycle1 is None  # No cycle yet

    # Thread B waits for Lock 1 (held by Thread A) -> edge B -> A -> CYCLE!
    cycle2 = wfg.register_wait("Thread_B", "Lock_1")
    assert cycle2 is not None
    assert len(cycle2) >= 2
    assert "Thread_A" in cycle2 and "Thread_B" in cycle2


def test_canonical_lock_manager_zero_deadlocks() -> None:
    wfg = DynamicWaitForGraph()
    mgr = CanonicalLockManager(wfg)

    # Acquire set 1
    ok1, acq1 = mgr.acquire_canonical_set(
        thread_id="T1",
        policy_id="glhs_policy_v1",
        profile_id="profile_001",
        partition_keys=["profile_001:medication:metformin", "profile_001:medication:lisinopril"],
    )
    assert ok1 is True
    assert len(acq1) == 4

    # Release set 1
    mgr.release_canonical_set("T1", acq1)
    assert len(wfg.held_resources["T1"]) == 0
    assert len(wfg.cycle_history) == 0


def test_deadlock_analysis_suite_run() -> None:
    results = run_deadlock_analysis(num_threads=4, num_txns=40, seed=42)

    assert "glhs_canonical_ss2pl" in results
    assert "unordered_standard_2pl" in results

    canon = results["glhs_canonical_ss2pl"]
    assert canon.deadlocks_detected == 0
    assert canon.zero_deadlock_invariant_satisfied is True

    unord = results["unordered_standard_2pl"]
    assert unord.canonical_ordering_enforced is False
