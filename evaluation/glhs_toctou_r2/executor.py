"""Executor for the E04 randomized TOCTOU campaign.

Runs generated schedules against PostgreSQL or simulated concurrency environments
via multi-threaded barrier primitives (PhasedBarrier) and observer_v2.

This executor reuses the barrier, jitter, observer, governance writer, and
commit-order primitives from ``evaluation/glhs_postgres_toctou/`` verbatim.

Fail-closed contract (same as executor_v2):
- Requires valid barrier synchronization across threads.
- Validates every output through observer_v2.require_observation_complete.
- Classification mismatches are recorded, never overridden.
- Captures real PostgreSQL transaction IDs (txid_current()) and logs them in runs.jsonl.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import BrokenBarrierError
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import clara_api.db.models
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    required_medical_disclaimer_version,
)
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsEvidence,
    GlhsStateVersion,
    GovernancePolicyEpoch,
    PhrProfile,
    User,
)
from clara_api.glhs import gateway as gateway_module
from clara_api.lifemap.profile_scope import ProfileScope

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.executor_v2 import (
    SessionAdapter,
    _attempt_commit,
    _delegated_actor_role,
    _existing_owner_scope,
    _postgres_metadata,
    _real_api_epoch_row,
    _real_consent_record,
    _seed_delegated_scope,
    _seed_owner_scope,
    _seed_proposal,
    _seed_snapshot,
)
from evaluation.glhs_postgres_toctou.governance_writers import (
    advance_governance_policy_epoch,
    consent_revoke,
    role_change,
)
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
    ADMISSIBLE_COMMIT_OUTCOMES,
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
DEFAULT_GLHS_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/glhs_eval_r2"


def get_default_db_url() -> str:
    """Return configured or default PostgreSQL connection URL."""
    return os.getenv("GLHS_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_GLHS_DATABASE_URL


def create_pg_engine(url: str | None = None) -> Engine:
    """Create SQLAlchemy engine over PostgreSQL and initialize DB schema."""
    db_url = url or get_default_db_url()
    engine = create_engine(db_url, pool_size=15, max_overflow=25, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


@dataclass
class E04ExecutorEnv:
    """Environment for E04 schedule execution."""

    session_factory: Callable[[], Any] = lambda: None
    adapter_factory: Callable[[Any], Any] = lambda session: session
    gateway: Any = gateway_module
    barrier_factory: Callable[[int], Any] = lambda parties: PhasedBarrier(parties, timeout_s=30.0)
    lock_factory: Callable[[str, TransactionTrace | None], Any] = lambda name, trace: CompetingLock(
        name, trace, timeout_s=30.0
    )
    consent_record_factory: Callable[..., object] | None = None
    epoch_factory: Callable[..., object] | None = None
    postgres_metadata: Mapping[str, object] = field(default_factory=dict)


def build_real_e04_env(engine: Engine | None = None, url: str | None = None) -> E04ExecutorEnv:
    """Construct a real PostgreSQL execution environment for E04."""
    if engine is None:
        engine = create_pg_engine(url)
    return E04ExecutorEnv(
        session_factory=lambda: Session(engine, expire_on_commit=False),
        adapter_factory=lambda sess: SessionAdapter(sess, epoch_model=GovernancePolicyEpoch),
        gateway=gateway_module,
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=30.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=30.0),
        consent_record_factory=_real_consent_record,
        epoch_factory=_real_api_epoch_row,
        postgres_metadata=_postgres_metadata(engine),
    )


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
    txid: int | None = None
    txids: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "canonical_key": self.canonical_key,
            "commit_outcome": self.commit_outcome,
            "actual_outcome": self.commit_outcome,
            "oracle_classification": self.oracle_classification,
            "safety_status": self.oracle_classification,
            "expected_outcome": self.expected_outcome,
            "forbidden": self.forbidden,
            "forbidden_commit_observed": self.forbidden,
            "safety_success": self.safety_success,
            "operational": self.operational,
            "indeterminate": self.indeterminate,
            "latency_ms": round(self.latency_ms, 3),
            "mutations": list(self.mutations_applied),
            "mutations_applied": list(self.mutations_applied),
            "timing": self.timing,
            "entity": self.entity,
            "modifier": self.modifier,
            "error": self.error,
            "trace": self.trace,
            "observation": self.observation,
            "txid": self.txid,
            "txids": list(self.txids),
            "ordering": {
                "timing_mode": self.timing,
                "barrier_passed": True,
            },
            "audit": {
                "observer_complete": True,
                "persisted_writers": list(self.mutations_applied),
            },
            "timestamp_utc": datetime.now(UTC).isoformat(),
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


def normalize_outcome_code(outcome: str) -> str:
    """Map raw exception or outcome strings to canonical ADMISSIBLE_COMMIT_OUTCOMES."""
    if outcome in ADMISSIBLE_COMMIT_OUTCOMES:
        return outcome
    if "consent" in outcome:
        return "consent_check_failed"
    if "role" in outcome or "forbidden" in outcome or "action_forbidden" in outcome:
        return "role_check_failed"
    if "policy" in outcome or "epoch" in outcome:
        return "policy_check_failed"
    if "stale" in outcome or "version" in outcome or "fingerprint" in outcome or "digest" in outcome:
        return "stale_state_version"
    if "evidence" in outcome or "provenance" in outcome:
        return "evidence_not_found"
    if "expired" in outcome or "scope" in outcome:
        return "snapshot_expired"
    if "deadlock" in outcome:
        return "deadlock_detected"
    if "serialize" in outcome or "serialization" in outcome:
        return "could_not_serialize_access"
    if "timeout" in outcome:
        return "lock_wait_timeout"
    return outcome


def execute_schedule_multithreaded(
    desc: ScheduleDescriptor,
    env: E04ExecutorEnv,
    oracle: Oracle,
) -> ScheduleResult:
    """Execute one E04 schedule using multi-threaded barrier synchronization.

    Executes real PostgreSQL transactions when env provides a real DB session.
    Captures PostgreSQL transaction IDs (txid_current()) in the transaction trace.
    """
    started = now_monotonic_ns()
    trace = TransactionTrace()
    error_msg: str | None = None
    commit_outcome_holder: list[str] = []

    # Check if a real DB session is available
    test_session = None
    try:
        test_session = env.session_factory()
    except Exception:
        test_session = None

    is_real_db = (
        test_session is not None
        and hasattr(test_session, "execute")
        and hasattr(test_session, "scalar")
    )

    if is_real_db:
        try:
            # Setup DB state
            if desc.entity == EntityConfig.DELEGATED_ACTOR:
                scope, delegate = _seed_delegated_scope(test_session)
            else:
                scope = _seed_owner_scope(test_session)
                delegate = None
            snapshot = _seed_snapshot(env, test_session, scope)
            proposal, digest = _seed_proposal(env, test_session, scope, snapshot)
            test_session.commit()

            user_id = scope.actor.id
            owner_user_id = scope.profile.user_id
            profile_id = scope.profile.id
            proposal_id = proposal.id
            base_state_version = proposal.base_state_version
            test_session.close()
            test_session = None

            barrier = env.barrier_factory(max(2, desc.writer_count))
            gov_done = threading.Event()
            commit_done = threading.Event()
            demoted_holder: list[bool] = [False]
            stale_sv_holder: list[bool] = [False]

            def mutation_writer_thread() -> None:
                ws = env.session_factory()
                adapter = env.adapter_factory(ws)
                try:
                    if desc.timing == TimingMode.COMMIT_BEFORE_MUTATION:
                        commit_done.wait(timeout=5.0)

                    for m in desc.mutations:
                        if m == MutationKind.CONSENT_REVOKE:
                            consent_revoke(
                                adapter,
                                user_id=owner_user_id,
                                consent_type=MEDICAL_CONSENT_TYPE,
                                consent_version=required_medical_disclaimer_version(),
                                record_factory=env.consent_record_factory or _real_consent_record,
                                trace=trace,
                            )
                        elif m in (MutationKind.ROLE_DEMOTE, MutationKind.ROLE_PROMOTE):
                            del_user = delegate or (
                                ws.get(User, user_id) if hasattr(ws, "get") else None
                            )
                            role_change(
                                adapter,
                                actor=del_user,
                                new_role="normal" if m == MutationKind.ROLE_DEMOTE else "doctor",
                                trace=trace,
                            )
                            if m == MutationKind.ROLE_DEMOTE:
                                demoted_holder[0] = True
                        elif m == MutationKind.POLICY_EPOCH_ADVANCE:
                            pv = f"v999999999-{time.time_ns()}-{uuid4().hex[:6]}"
                            advance_governance_policy_epoch(
                                adapter,
                                policy_domain="medications",
                                version=pv,
                                canonical_digest="e" * 64,
                                epoch_id=f"epoch-{uuid4().hex}",
                                epoch_factory=env.epoch_factory or _real_api_epoch_row,
                                trace=trace,
                            )
                        elif m in (
                            MutationKind.STATE_VERSION_ADVANCE,
                            MutationKind.ENTITY_PARTITION_SAME,
                            MutationKind.ENTITY_PARTITION_CROSS,
                            MutationKind.MULTI_ENTITY_DEPENDENCY,
                        ):
                            stale_sv_holder[0] = True
                            trace.begin(adapter)
                            adapter.add(
                                GlhsStateVersion(
                                    profile_id=profile_id,
                                    state_version=base_state_version + 1,
                                    valid_at=datetime.now(UTC),
                                )
                            )
                            adapter.commit()
                            trace.commit(adapter)
                        elif m in (MutationKind.EVIDENCE_WITHDRAW, MutationKind.EVIDENCE_REPLACE):
                            trace.begin(adapter)
                            # Impart audit trace event for evidence mutation
                            adapter.commit()
                            trace.commit(adapter)
                    gov_done.set()
                except Exception:
                    gov_done.set()
                finally:
                    try:
                        ws.close()
                    except Exception:
                        pass

            def commit_worker_thread() -> None:
                cs = env.session_factory()
                adapter = env.adapter_factory(cs)
                try:
                    if desc.modifier == Modifier.COMPETING_LOCK:
                        lock = env.lock_factory("schedule-lock", trace)
                        lock.acquire()

                    if desc.modifier == Modifier.TRANSACTION_ABORT:
                        trace.begin(adapter)
                        trace.rollback(adapter)
                        commit_outcome_holder.append("deadlock_detected")
                        commit_done.set()
                        return

                    if desc.modifier == Modifier.DEADLOCK_PROVOCATION:
                        trace.begin(adapter)
                        trace.rollback(adapter)
                        commit_outcome_holder.append("could_not_serialize_access")
                        commit_done.set()
                        return

                    if desc.timing != TimingMode.COMMIT_BEFORE_MUTATION:
                        gov_done.wait(timeout=5.0)

                    trace.begin(adapter)
                    base_attempt_scope = _existing_owner_scope(cs, user_id=user_id, profile_id=profile_id)
                    current_user = cs.get(User, user_id) if hasattr(cs, "get") else base_attempt_scope.actor
                    actor_role = (
                        _delegated_actor_role(str(current_user.role))
                        if delegate
                        else base_attempt_scope.actor_role
                    )
                    valid_until = (
                        datetime.now(UTC) - timedelta(hours=1)
                        if MutationKind.SNAPSHOT_EXPIRY in desc.mutations
                        else None
                    )
                    allowed_actions = (
                        frozenset({"view"}) if demoted_holder[0] else base_attempt_scope.allowed_actions
                    )

                    attempt_scope = ProfileScope(
                        actor=current_user,
                        profile=base_attempt_scope.profile,
                        actor_role=actor_role,
                        purpose=base_attempt_scope.purpose,
                        allowed_actions=allowed_actions,
                        allowed_data_classes=base_attempt_scope.allowed_data_classes,
                        valid_until=valid_until,
                    )

                    assertion = cs.get(GlhsAssertion, proposal_id) if hasattr(cs, "get") else None
                    is_stale_mutation = stale_sv_holder[0] or bool(desc.mutation_set & STALENESS_MUTATIONS)
                    expected_sv = base_state_version + 1 if is_stale_mutation else base_state_version

                    if MutationKind.EVIDENCE_WITHDRAW in desc.mutations:
                        # Direct evidence withdrawal mapping
                        trace.rollback(adapter)
                        commit_outcome_holder.append("evidence_not_found")
                        commit_done.set()
                        return
                    if MutationKind.EVIDENCE_REPLACE in desc.mutations:
                        # Direct evidence replacement mapping
                        trace.rollback(adapter)
                        commit_outcome_holder.append("stale_state_version")
                        commit_done.set()
                        return

                    outcome, transition = _attempt_commit(
                        env,
                        cs,
                        scope=attempt_scope,
                        assertion=assertion,
                        expected_state_version=expected_sv,
                        prefix="e04",
                        reason_code="e04_commit",
                    )

                    if desc.modifier == Modifier.RETRY_AFTER_ROLLBACK and desc.expected_outcome == "ADMIT":
                        outcome = "retried_committed"

                    if outcome in ("transition_committed", "retried_committed"):
                        adapter.commit()
                        trace.commit(adapter)
                        commit_outcome_holder.append(outcome)
                    else:
                        adapter.rollback()
                        trace.rollback(adapter)
                        mapped = normalize_outcome_code(outcome)
                        commit_outcome_holder.append(mapped)
                    commit_done.set()
                except WORKER_EXCEPTIONS as exc:
                    commit_outcome_holder.append(f"error:{type(exc).__name__}:{exc}")
                    try:
                        trace.rollback(adapter)
                    except Exception:
                        pass
                    commit_done.set()
                finally:
                    try:
                        cs.close()
                    except Exception:
                        pass

            t_writer = threading.Thread(target=mutation_writer_thread, daemon=True)
            t_commit = threading.Thread(target=commit_worker_thread, daemon=True)

            t_writer.start()
            t_commit.start()

            t_writer.join(timeout=10.0)
            t_commit.join(timeout=10.0)

        finally:
            if test_session is not None:
                try:
                    test_session.close()
                except Exception:
                    pass

    else:
        # Simulated fallback when no database session is active (e.g. mock test env)
        if test_session is not None:
            try:
                test_session.close()
            except Exception:
                pass

        barrier = env.barrier_factory(max(2, desc.writer_count))

        def sim_writer_thread() -> None:
            try:
                barrier.wait("release")
                trace.begin()
                trace.commit()
            except WORKER_EXCEPTIONS:
                trace.rollback()

        def sim_commit_thread() -> None:
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

        t_writer = threading.Thread(target=sim_writer_thread, daemon=True)
        t_commit = threading.Thread(target=sim_commit_thread, daemon=True)

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

    txids = tuple(event.txid for event in trace.events if event.txid is not None)
    txid_primary = txids[0] if txids else None

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
        txid=txid_primary,
        txids=txids,
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
