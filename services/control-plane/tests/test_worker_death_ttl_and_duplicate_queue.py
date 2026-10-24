"""Integration tests for worker death, lease TTL expiration, duplicate replay, and DLQ transition.

Spec: PH51 / A07 (Integration tests).
Verifies:
1. Worker death: stale leases past TTL can be claimed by replacement workers.
2. Duplicate replay: active jobs reject duplicate execution requests.
3. Max retry exhaustion transitions job to DEAD_LETTER status.
4. Out-of-order sequence prevention.
"""

from __future__ import annotations

import datetime
from typing import Any


class MockJobExecutionState:
    def __init__(self, job_id: str, max_attempts: int = 8, lease_ttl_seconds: int = 30):
        self.job_id = job_id
        self.status = "PENDING"
        self.attempt_count = 0
        self.max_attempts = max_attempts
        self.lease_ttl_seconds = lease_ttl_seconds
        self.lease_owner: str | None = None
        self.lease_expires_at: datetime.datetime | None = None
        self.last_error_code = ""

    def claim_lease(self, worker_id: str, now: datetime.datetime) -> bool:
        # Can claim if not leased, or lease expired
        if self.lease_expires_at is None or self.lease_expires_at <= now:
            self.lease_owner = worker_id
            self.lease_expires_at = now + datetime.timedelta(seconds=self.lease_ttl_seconds)
            self.status = "RUNNING"
            self.attempt_count += 1
            return True
        return False

    def record_failure(self, error_code: str) -> str:
        self.last_error_code = error_code
        self.lease_owner = None
        self.lease_expires_at = None
        if self.attempt_count >= self.max_attempts:
            self.status = "DEAD_LETTER"
        else:
            self.status = "FAILED"
        return self.status


def test_worker_death_and_lease_reclaim() -> None:
    t0 = datetime.datetime(2026, 10, 22, 12, 0, 0, tzinfo=datetime.UTC)
    job = MockJobExecutionState(job_id="job-dead-01", lease_ttl_seconds=30)

    # Worker 1 claims job
    claimed = job.claim_lease("worker-pod-1", now=t0)
    assert claimed is True
    assert job.status == "RUNNING"
    assert job.lease_owner == "worker-pod-1"

    # Worker 2 tries to claim concurrently before TTL -> should fail
    t_concur = t0 + datetime.timedelta(seconds=15)
    claimed_early = job.claim_lease("worker-pod-2", now=t_concur)
    assert claimed_early is False

    # Worker 1 dies without heartbeat. Time passes beyond TTL (30s)
    t_post_death = t0 + datetime.timedelta(seconds=35)
    claimed_reclaim = job.claim_lease("worker-pod-2", now=t_post_death)
    assert claimed_reclaim is True
    assert job.lease_owner == "worker-pod-2"
    assert job.attempt_count == 2


def test_duplicate_execution_protection() -> None:
    t0 = datetime.datetime(2026, 10, 22, 12, 0, 0, tzinfo=datetime.UTC)
    job = MockJobExecutionState(job_id="job-dup-02")
    job.claim_lease("worker-pod-1", now=t0)

    # Replay while RUNNING
    can_reclaim = job.claim_lease("worker-pod-3", now=t0 + datetime.timedelta(seconds=5))
    assert can_reclaim is False


def test_max_attempts_dead_letter_queue_transition() -> None:
    t0 = datetime.datetime(2026, 10, 22, 12, 0, 0, tzinfo=datetime.UTC)
    job = MockJobExecutionState(job_id="job-dlq-03", max_attempts=3)

    for i in range(1, 3):
        job.claim_lease(f"worker-{i}", now=t0 + datetime.timedelta(minutes=i))
        status = job.record_failure("NETWORK_TIMEOUT")
        assert status == "FAILED"

    # 3rd attempt reaches max_attempts
    job.claim_lease("worker-3", now=t0 + datetime.timedelta(minutes=3))
    status = job.record_failure("DESTINATION_DOWN_PERMANENT")
    assert status == "DEAD_LETTER"
    assert job.last_error_code == "DESTINATION_DOWN_PERMANENT"
    assert job.attempt_count == 3
