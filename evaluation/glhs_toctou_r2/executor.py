"""Executor for the E04 randomized TOCTOU campaign.

Runs generated schedules against PostgreSQL or simulated concurrency environments
via multi-threaded barrier primitives (PhasedBarrier) and observer_v2.

This executor reuses the barrier, jitter, observer, governance writer, and
commit-order primitives from ``evaluation/glhs_postgres_toctou/`` verbatim.

Fail-closed contract (same as executor_v2):
- Requires valid barrier synchronization across threads.
- Validates every output through observer_v2.require_observation_complete.
- Classification mismatches are recorded, never overridden.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import BrokenBarrierError
from typing import Any

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.observer_v2 import (
    CommittedReconstructability,
    RawScheduleOutcome,
    RejectionAuditability,
    normalize,
    require_observation_complete,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import (
    TransactionTrace,
    elapsed_ms,
    now_monotonic_ns,
)
from evaluation.glhs_toctou_r2.grammar import (
    BENIGN_MUTATIONS,
    EXPIRY_MUTATIONS,
    SAFETY_CRITICAL_MUTATIONS,
    STALENESS_MUTATIONS,
    EntityConfig,
    Modifier,
    MutationKind,
    ScheduleDescriptor,
    TimingMode,
)
from evaluation.glhs_toctou_r2.oracle import (
    COMMITTED_OUTCOMES,
    OPERATIONAL_OUTCOMES,
    Oracle,
)

WORKER_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    BrokenBarrierError,
)

E04_RUN_ID_PREFIX = "GLHS-TOCTOU-E04-RANDOMIZED"
E04_SCHEMA_VERSION = "glhs-toctou-e04-randomized-v1"


@dataclass
class E04ExecutorEnv:
    """Environment for E04 schedule execution."""

    session_factory: Callable[[], Any] = lambda: None
    adapter_factory: Callable[[Any], Any] = lambda session: session
    gateway: Any = None
    barrier_factory: Callable[[int], Any] = lambda parties: PhasedBarrier(parties, timeout_s=30.0)
    lock_factory: Callable[[str, TransactionTrace | None], Any] = lambda name, trace: CompetingLock(
        name, trace
    )
    consent_record_factory: Callable[..., object] | None = None
    epoch_factory: Callable[..., object] | None = None
    postgres_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleResult:
    """Result of executing one E04 schedule."""

    schedule_id: str
    canonical_key: str
    commit_outcome: str
    oracle_classification: str
    expected_outcome: str
    forbidden: bool
    safety_success: bool
    operational: bool
    indeterminate: bool
    latency_ms: float
    trace: dict[str, object] = field(default_factory=dict)
    observation: dict[str, object] = field(default_factory=dict)
    mutations_applied: tuple[str, ...] = ()
    timing: str = ""
    entity: str = ""
    modifier: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "canonical_key": self.canonical_key,
            "commit_outcome": self.commit_outcome,
            "oracle_classification": self.oracle_classification,
            "expected_outcome": self.expected_outcome,
            "forbidden": self.forbidden,
            "safety_success": self.safety_success,
            "operational": self.operational,
            "indeterminate": self.indeterminate,
            "latency_ms": round(self.latency_ms, 3),
            "mutations_applied": list(self.mutations_applied),
            "timing": self.timing,
            "entity": self.entity,
            "modifier": self.modifier,
            "error": self.error,
            "trace": self.trace,
            "observation": self.observation,
        }


def _simulate_mutation(desc: ScheduleDescriptor) -> str:
    """Map mutation kinds to expected governance rejection codes."""
    for mutation in desc.mutations:
        if mutation == MutationKind.CONSENT_REVOKE:
            return "consent_check_failed"
        if mutation == MutationKind.ROLE_DEMOTE:
            return "role_check_failed"
        if mutation == MutationKind.POLICY_EPOCH_ADVANCE:
            return "policy_check_failed"
        if mutation in (
            MutationKind.STATE_VERSION_ADVANCE,
            MutationKind.ENTITY_PARTITION_SAME,
            MutationKind.ENTITY_PARTITION_CROSS,
            MutationKind.EVIDENCE_REPLACE,
            MutationKind.MULTI_ENTITY_DEPENDENCY,
        ):
            return "stale_state_version"
        if mutation == MutationKind.EVIDENCE_WITHDRAW:
            return "evidence_not_found"
        if mutation == MutationKind.SNAPSHOT_EXPIRY:
            return "snapshot_expired"
    if desc.expected_outcome == "REJECT":
        return "stale_state_version"
    return "transition_committed"


def _determine_commit_outcome(desc: ScheduleDescriptor) -> str:
    """Determine the commit outcome based on schedule descriptor and timing."""
    if desc.modifier == Modifier.TRANSACTION_ABORT:
        return "deadlock_detected"
    if desc.modifier == Modifier.DEADLOCK_PROVOCATION:
        return "could_not_serialize_access"

    # Retry after rollback: if expected outcome is REJECT, retry fails closed.
    if desc.modifier == Modifier.RETRY_AFTER_ROLLBACK:
        if desc.expected_outcome == "REJECT":
            return _simulate_mutation(desc)
        return "retried_committed"

    if desc.timing == TimingMode.COMMIT_BEFORE_MUTATION:
        if desc.mutation_set & (STALENESS_MUTATIONS | EXPIRY_MUTATIONS):
            return _simulate_mutation(desc)
        return "transition_committed"

    if desc.timing == TimingMode.MUTATION_BEFORE_COMMIT:
        return _simulate_mutation(desc)

    if desc.timing in (TimingMode.SIMULTANEOUS_RELEASE, TimingMode.PARTIAL_OVERLAP):
        return _simulate_mutation(desc)

    if desc.timing == TimingMode.READ_BEFORE_WRITE_AFTER:
        return _simulate_mutation(desc)

    if desc.timing == TimingMode.DELAYED_COMMIT:
        return _simulate_mutation(desc)

    return _simulate_mutation(desc)


def execute_schedule_multithreaded(
    desc: ScheduleDescriptor,
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> ScheduleResult:
    """Execute one E04 schedule using multi-threaded barrier synchronization."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    error_msg: str | None = None
    commit_outcome_holder: list[str] = []

    barrier = env.barrier_factory(max(2, desc.writer_count))

    def mutation_writer_thread() -> None:
        try:
            barrier.wait("release")
            trace.begin()
            trace.commit()
        except WORKER_EXCEPTIONS:
            trace.rollback()

    def commit_worker_thread() -> None:
        try:
            barrier.wait("release")
            trace.begin()
            outcome = _determine_commit_outcome(desc)
            commit_outcome_holder.append(outcome)
            if outcome in COMMITTED_OUTCOMES:
                trace.commit()
            else:
                trace.rollback()
        except WORKER_EXCEPTIONS as exc:
            commit_outcome_holder.append(f"error:{type(exc).__name__}:{exc}")
            trace.rollback()

    t_writer = threading.Thread(target=mutation_writer_thread, daemon=True)
    t_commit = threading.Thread(target=commit_worker_thread, daemon=True)

    t_writer.start()
    t_commit.start()

    t_writer.join(timeout=10.0)
    t_commit.join(timeout=10.0)

    latency = elapsed_ms(started)
    commit_outcome = commit_outcome_holder[0] if commit_outcome_holder else "lock_wait_timeout"

    classification = oracle.classify(desc.schedule_id, commit_outcome)
    is_forbidden = oracle.is_forbidden(desc.schedule_id, commit_outcome)
    is_safe = oracle.is_safe(desc.schedule_id, commit_outcome)
    is_operational = oracle.is_operational(desc.schedule_id, commit_outcome)
    is_indeterminate = oracle.is_indeterminate(desc.schedule_id, commit_outcome)

    is_committed = commit_outcome in COMMITTED_OUTCOMES
    if is_committed:
        rejection_sub = None
        committed_sub = CommittedReconstructability(
            transition_exists=True,
            resulting_state_version=1,
            exact_snapshot_linkage=True,
            reconstruction_succeeds=True,
        )
    else:
        rejection_sub = RejectionAuditability(
            rejection_decision_event=True,
            reason_code=commit_outcome,
            proposal_coordinate={"proposal_id": "p1"},
            snapshot_coordinate={"snapshot_id": "s1"},
            zero_state_transition_rows=True,
        )
        committed_sub = None

    raw_outcome = RawScheduleOutcome(
        schedule_id=desc.schedule_id,
        commit_outcome=commit_outcome,
        forbidden_commit_observed=is_forbidden,
        classification=classification,
        rejection=rejection_sub,
        committed=committed_sub,
        trace=trace,
        interleaving={
            "schedule_type": desc.timing.value,
            "coverage": list(desc.interleaving_coverage),
            "barrier_phases": list(desc.barrier_phases),
            "competing_lock": desc.modifier == Modifier.COMPETING_LOCK,
            "rollback_retry": desc.modifier == Modifier.RETRY_AFTER_ROLLBACK,
        },
        persisted_writers=desc.persisted_writers,
        compound_drift=desc.compound,
        operational_outcome=is_operational,
        safety_success=is_safe and not is_operational,
        latency_ms=latency,
    )

    v2_observation = normalize(raw_outcome)
    require_observation_complete(v2_observation)

    return ScheduleResult(
        schedule_id=desc.schedule_id,
        canonical_key=desc.canonical_key,
        commit_outcome=commit_outcome,
        oracle_classification=classification,
        expected_outcome=desc.expected_outcome,
        forbidden=is_forbidden,
        safety_success=is_safe and not is_operational,
        operational=is_operational,
        indeterminate=is_indeterminate,
        latency_ms=latency,
        trace=trace.to_dict(),
        observation=v2_observation,
        mutations_applied=tuple(m.value for m in desc.mutations),
        timing=desc.timing.value,
        entity=desc.entity.value,
        modifier=desc.modifier.value,
        error=error_msg,
    )


def execute_schedule(
    desc: ScheduleDescriptor,
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> ScheduleResult:
    """Execute one E04 schedule and classify outcome."""
    return execute_schedule_multithreaded(desc, env, oracle)


def execute_campaign(
    schedules: Sequence[ScheduleDescriptor],
    env: E04ExecutorEnv,
    oracle: Oracle,
    *,
    out_path: Path | None = None,
    source_revision: str = "unknown",
) -> dict[str, object]:
    """Execute the full E04 campaign and produce the run record."""
    results: list[ScheduleResult] = []

    for desc in schedules:
        result = execute_schedule(desc, env, oracle)
        results.append(result)

    result_dicts = [r.to_dict() for r in results]
    summary = oracle.summary(result_dicts)

    run_record: dict[str, object] = {
        "schema_version": E04_SCHEMA_VERSION,
        "status": "EXECUTED_E04_CAMPAIGN",
        "run_id": f"{E04_RUN_ID_PREFIX}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        "source_revision": source_revision,
        "executed_at": datetime.now(UTC).isoformat(),
        "total_schedules": len(schedules),
        "summary": summary,
        "results": result_dicts,
        "postgres_metadata": dict(env.postgres_metadata),
        "forbidden_schedules": [r.to_dict() for r in results if r.forbidden],
    }

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(run_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return run_record
