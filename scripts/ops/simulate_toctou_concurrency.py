#!/usr/bin/env python3
"""Randomized Concurrency & TOCTOU Race Condition Simulator.

Spec: PH08 / A08 (Security + Privacy).
Simulates:
1. 50 parallel workers attempting concurrent CAS version increments on an entity partition.
2. Asserts zero lost updates: final version must equal initial + successful commits count.
3. Time-of-check to time-of-use (TOCTOU) race conditions under simulated thread interleaving.
"""

from __future__ import annotations

import concurrent.futures
import json
import random
import sys
import threading
import time


class SimulatedPartition:
    def __init__(self, key: str, initial_version: int = 1) -> None:
        self.key = key
        self.version = initial_version
        self._lock = threading.Lock()

    def compare_and_swap(self, observed_version: int, new_data: str) -> bool:
        # Simulate slight network / processing latency
        time.sleep(random.uniform(0.001, 0.005))
        with self._lock:
            if self.version == observed_version:
                self.version += 1
                return True
            return False


def run_randomized_toctou_test(workers_count: int = 50) -> dict[str, int | bool]:
    partition = SimulatedPartition("medications:patient-1", initial_version=1)

    successful_commits = 0
    rejected_stale_writes = 0
    results_lock = threading.Lock()

    def worker_attempt() -> None:
        nonlocal successful_commits, rejected_stale_writes
        # Step 1: Read current version (Time-of-Check)
        observed = partition.version
        # Step 2: Attempt commit (Time-of-Use)
        ok = partition.compare_and_swap(observed, "new_dosage")
        with results_lock:
            if ok:
                successful_commits += 1
            else:
                rejected_stale_writes += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as executor:
        futures = [executor.submit(worker_attempt) for _ in range(workers_count)]
        concurrent.futures.wait(futures)

    # Invariant: final version must equal initial (1) + successful_commits
    expected_final = 1 + successful_commits
    linearizability_preserved = partition.version == expected_final

    return {
        "status": "passed" if linearizability_preserved else "failed",
        "workers_count": workers_count,
        "successful_commits": successful_commits,
        "rejected_stale_writes": rejected_stale_writes,
        "final_partition_version": partition.version,
        "linearizability_preserved": linearizability_preserved,
    }


if __name__ == "__main__":
    res = run_randomized_toctou_test()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["linearizability_preserved"] else 1)
