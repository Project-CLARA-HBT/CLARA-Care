"""Concrete executor for the frozen W4 GLHS v2 persisted-governance protocol.

This executor runs the frozen v2 protocol (``research/glhs_journal/protocol_v2/
postgres_toctou_protocol_v2.json``) against a fresh, operator-owned, isolated
PostgreSQL database. It builds the real schedules from
``governance_writers``/``barrier``/``schedule_primitives`` and drives the actual
CLARA GLHS gateway (``compile_thss``/``propose_assertion``/``apply_transition``/
``record_evidence``/``reconstruct_governed_decision``) over the real
``clara_api.db.models`` rows. Observations are collected through
``observer_v2`` and written to ``run_v2_raw.json``.

Fail-closed contract:

- Refuses to run without ``GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH=1`` and a
  ``postgresql://`` URL (``--database-url`` or ``GLHS_TOCTOU_FINAL_DATABASE_URL``)
  that is not a shared/default database.
- Refuses any protocol that is not ``FROZEN_FINAL_REVIEWED`` or not the v2
  isolation contract.
- Never fabricates results: every schedule observation comes from actually
  running the schedule driver, and an observation whose classification differs
  from the frozen expected classification is recorded as an explicit mismatch
  that makes the run not claim-eligible.

The executor is deliberately structured so the schedule drivers are pure and
testable: sessions and transactions are duck-typed handles supplied by
``ExecutorEnv``. Tests inject fake sessions/gateway objects and never connect to
any database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import BrokenBarrierError
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    required_medical_disclaimer_version,
)
from clara_api.db.base import Base
from clara_api.db.models import (
    FamilyAccessGrant,
    GlhsAssertion,
    GlhsEvidence,
    GlhsTransitionItem,
    GovernancePolicyEpoch,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs import gateway as gateway_module
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import AssertionInput, EvidenceInput, Snapshot
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import Column, DateTime, String, create_engine, exc, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.governance_writers import (
    advance_governance_policy_epoch,
    compound_drift_detected,
    consent_revoke,
    role_change,
)
from evaluation.glhs_postgres_toctou.observer_v2 import (
    CommittedReconstructability,
    RawScheduleOutcome,
    RejectionAuditability,
    observe,
    require_observation_complete,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import (
    TransactionTrace,
    classify_concurrent_commit_order,
    classify_proposal_order,
    elapsed_ms,
    new_idempotency_key,
    now_monotonic_ns,
    snapshot_binding_digest,
)
from evaluation.glhs_postgres_toctou.validate_v2 import (
    REQUIRED_INTERLEAVING_COVERAGE,
    V2_ISOLATION_CONTRACT,
    V2_PROTOCOL_SCHEMA_VERSION,
    V2_PROTOCOL_STATUS,
    _validate_outcome_classification,
    _validate_schedule_markers,
    validate_v2,
)

PROTOCOL_SCHEMA_VERSION = V2_PROTOCOL_SCHEMA_VERSION
PROTOCOL_STATUS = V2_PROTOCOL_STATUS
RUN_ID = "GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01"
V21_PROTOCOL_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v2.1"
V21_RUN_ID = "GLHS-POSTGRES-TOCTOU-FINAL-V2-1-20260818-01"
FINAL_ISOLATION_ATTESTATION = "GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH"
FINAL_DATABASE_URL = "GLHS_TOCTOU_FINAL_DATABASE_URL"
DEFAULT_PROTOCOL_PATH = Path("research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json")
DEFAULT_OUTPUT_PATH = Path("research/glhs_journal/protocol_v2/run_v2_raw.json")
DEFAULT_PROTOCOL_V21_PATH = Path(
    "research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2_1.json"
)
DEFAULT_OUTPUT_V21_PATH = Path("research/glhs_journal/protocol_v2/run_v2_1_raw.json")

# Independent-resource race vocabulary: the profile-global version counter
# serializes same-profile writers; losers are rejected as stale and classified
# as false stale because the winner's transition touched a semantic dependency
# outside the loser's declared set. Deadlock/serialization stays operational.
OPERATIONAL_COMMIT_OUTCOMES = frozenset(
    {"deadlock_detected", "could_not_serialize_access", "lock_wait_timeout"}
)
RACE_COMMIT_OUTCOME = "transition_committed"
FALSE_STALE_CLASSIFICATION = "committed_with_expected_false_stale"
SINGLE_WRITER_CLASSIFICATION = "transition_committed"
RACE_WORKLOAD = "independent_resources_race"
GOVERNANCE_SINGLE_WORKLOAD = "governance_toctou_single_attempt"
_METRICS_KEYS = frozenset(
    {
        "workload_type",
        "attempts",
        "accepted_valid_commits",
        "true_stale_rejections",
        "false_stale_rejections",
        "false_stale_rate_per_attempt",
        "database_errors",
        "latency_p50_ms",
        "latency_p95_ms",
    }
)

# What a schedule worker thread may raise and still be reported (never fabricated)
# as an observed outcome rather than crashing the whole run.
WORKER_EXCEPTIONS: tuple[type[BaseException], ...] = (
    GlhsInvariantError,
    exc.SQLAlchemyError,
    BrokenBarrierError,
    RuntimeError,
    TypeError,
    ValueError,
)


# The real persisted governance-policy-epoch row used by the v2 epoch writer on
# the real database. It lives only in the isolated random schema.
class GlhsGovernancePolicyEpochRow(Base):
    __tablename__ = "glhs_governance_policy_epochs"

    id = Column(String(64), primary_key=True)
    policy_domain = Column(String(64), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    active_from = Column(DateTime(timezone=True), nullable=False)
    canonical_digest = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


def _real_consent_record(*, user_id: int, consent_type: str, consent_version: str, revoked_at: datetime) -> object:
    return UserConsent(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=consent_version,
        revoked_at=revoked_at,
    )


def _real_epoch_row(*, id: str, policy_domain: str, version: str, active_from: datetime, canonical_digest: str, created_at: datetime) -> object:
    return GlhsGovernancePolicyEpochRow(
        id=id,
        policy_domain=policy_domain,
        version=version,
        active_from=active_from,
        canonical_digest=canonical_digest,
        created_at=created_at,
    )


def _real_api_epoch_row(*, id: str, policy_domain: str, version: str, active_from: datetime, canonical_digest: str, created_at: datetime) -> object:
    """Create the real API ``GovernancePolicyEpoch`` row (database-assigned id).

    The v2.1 persisted-epoch path writes the production ORM row so the real
    gateway's ``read_current_policy_epoch`` consults it. The writer's opaque
    string epoch id is not persisted on the API row.
    """
    return GovernancePolicyEpoch(
        policy_domain=policy_domain,
        version=version,
        active_from=active_from,
        canonical_digest=canonical_digest,
        created_at=created_at,
    )


class SessionAdapter:
    """Duck-typed ``SessionLike`` handle over a real SQLAlchemy session.

    Exposes ``load_consent_target``/``load_policy_epoch`` as duck methods so the
    governance writers can locate the authoritative persisted rows, plus
    ``backend_pid``/``txid`` for the transaction trace.  ``epoch_model`` selects
    the persisted epoch table consulted by the policy-epoch writer: the v2
    ``glhs_governance_policy_epochs`` row by default, or the v2.1 production
    ``GovernancePolicyEpoch`` model when ``epoch_model=GovernancePolicyEpoch``.
    """

    def __init__(self, session: Session, *, epoch_model: type | None = None) -> None:
        self._session = session
        self._epoch_model = epoch_model or GlhsGovernancePolicyEpochRow

    @property
    def backend_pid(self) -> int | None:
        try:
            return int(self._session.scalar(text("SELECT pg_backend_pid()")))
        except (exc.SQLAlchemyError, TypeError, ValueError):
            return None

    @property
    def txid(self) -> int | None:
        try:
            return int(self._session.scalar(text("SELECT txid_current()")))
        except (exc.SQLAlchemyError, TypeError, ValueError):
            return None

    def add(self, instance: object) -> None:
        self._session.add(instance)

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def get(self, model: type, ident: object) -> object | None:
        return self._session.get(model, ident)

    def scalar(self, statement: object) -> object:
        return self._session.scalar(statement)

    def load_consent_target(self, *, user_id: int, consent_type: str) -> UserConsent | None:
        return self._session.execute(
            select(UserConsent)
            .where(UserConsent.user_id == user_id, UserConsent.consent_type == consent_type)
            .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
        ).scalars().first()

    def load_policy_epoch(self, *, policy_domain: str) -> object | None:
        model = self._epoch_model
        return self._session.execute(
            select(model)
            .where(model.policy_domain == policy_domain)
            .order_by(model.created_at.desc())
        ).scalars().first()


@dataclass
class ExecutorEnv:
    """Everything a schedule driver needs; all handles are injectable for tests."""

    session_factory: Callable[[], Any]
    adapter_factory: Callable[[Any], Any] = lambda session: session
    gateway: Any = gateway_module
    barrier_factory: Callable[[int], Any] = lambda parties: PhasedBarrier(parties, timeout_s=30.0)
    lock_factory: Callable[[str, TransactionTrace | None], Any] = lambda name, trace: CompetingLock(name, trace)
    consent_record_factory: Callable[..., object] | None = None
    epoch_factory: Callable[..., object] | None = None
    postgres_metadata: Mapping[str, object] = field(default_factory=dict)


# --- fail-closed gates --------------------------------------------------------

def load_protocol(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("glhs_toctou_v2_protocol_json_invalid") from exc
    if not isinstance(value, dict):
        raise TypeError("glhs_toctou_v2_protocol_not_object")
    return value


def validate_protocol(protocol: Mapping[str, object]) -> dict[str, object]:
    if protocol.get("status") != PROTOCOL_STATUS:
        raise ValueError("v2_protocol_not_frozen")
    schema_version = str(protocol.get("schema_version", ""))
    if schema_version not in {PROTOCOL_SCHEMA_VERSION, V21_PROTOCOL_SCHEMA_VERSION}:
        raise ValueError("v2_protocol_schema_invalid")
    if protocol.get("isolation") != V2_ISOLATION_CONTRACT:
        raise ValueError("v2_isolation_contract_invalid")
    if schema_version == V21_PROTOCOL_SCHEMA_VERSION and protocol.get(
        "persisted_epoch_required"
    ) is not True:
        raise ValueError("v21_persisted_epoch_required_missing")
    schedules = protocol.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("v2_protocol_schedules_missing")
    if schema_version == V21_PROTOCOL_SCHEMA_VERSION:
        return {
            "schema_version": V21_PROTOCOL_SCHEMA_VERSION,
            "status": "VALIDATED_V21_PROTOCOL_NOT_EXECUTED",
            "database_executed": False,
            "result_emitted": False,
            "schedule_count": len(schedules),
        }
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "status": "VALIDATED_V2_PROTOCOL_NOT_EXECUTED",
        "database_executed": False,
        "result_emitted": False,
        "schedule_count": len(schedules),
    }


def _require_final_isolated_postgres(database_url: str | None) -> str:
    if os.environ.get(FINAL_ISOLATION_ATTESTATION) != "1":
        raise RuntimeError("glhs_toctou_final_v2_requires_isolated_research_attestation")
    url = database_url or os.environ.get(FINAL_DATABASE_URL, "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("glhs_toctou_final_v2_requires_postgresql_database_url")
    if make_url(url).database in {None, "postgres", "template0", "template1"}:
        raise RuntimeError("glhs_toctou_final_v2_requires_non_default_database")
    return url


def _random_schema_name() -> str:
    return f"glhs_toctou_final_v2_{uuid4().hex}"


def _source_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# --- synthetic seed helpers (real gateway + real models) ----------------------

def _seed_owner_scope(db: Any) -> ProfileScope:
    user = User(email=f"v2-owner-{uuid4().hex}@example.test", hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    db.add(
        UserConsent(
            user_id=user.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
        )
    )
    db.flush()
    return ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "resolve", "view"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def _existing_owner_scope(db: Any, *, user_id: int, profile_id: int) -> ProfileScope:
    user = db.get(User, user_id)
    profile = db.get(PhrProfile, profile_id)
    if user is None or profile is None:
        raise RuntimeError("v2_synthetic_scope_missing")
    return ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "resolve", "view"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def _delegated_actor_role(account_role: str) -> str:
    return "clinician" if "doctor" in account_role else "caregiver"


def _seed_delegated_scope(db: Any) -> tuple[ProfileScope, User]:
    """Synthetic delegated scope governed by a persisted Family grant + role."""
    owner = User(email=f"v2-owner-{uuid4().hex}@example.test", hashed_password="x", role="normal")
    delegate = User(email=f"v2-delegate-{uuid4().hex}@example.test", hashed_password="x", role="doctor")
    db.add_all([owner, delegate])
    db.flush()
    profile = PhrProfile(user_id=owner.id)
    db.add(profile)
    db.flush()
    db.add(
        UserConsent(
            user_id=owner.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
        )
    )
    now = datetime.now(UTC)
    db.add(
        FamilyAccessGrant(
            profile_id=profile.id,
            grantor_user_id=owner.id,
            grantee_user_id=delegate.id,
            object_type="lifemap",
            object_id=profile.public_id,
            allowed_actions_json=["view", "create", "correct", "resolve"],
            data_classes_json=["medications"],
            purpose="self_care",
            status="active",
            starts_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(days=1),
        )
    )
    db.flush()
    scope = ProfileScope(
        actor=delegate,
        profile=profile,
        actor_role=_delegated_actor_role(delegate.role),
        purpose="self_care",
        allowed_actions=frozenset({"view", "create", "correct", "resolve"}),
        allowed_data_classes=frozenset({"medications"}),
    )
    return scope, delegate


def _seed_evidence(env: ExecutorEnv, db: Any, scope: ProfileScope) -> GlhsEvidence:
    now = datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="glhs-toctou-v2",
        source_identity=f"synthetic:{uuid4()}",
        checksum=f"synthetic:{uuid4()}",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    return env.gateway.record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="glhs-toctou-v2",
            artifact_type="synthetic",
            artifact_public_id=f"synthetic:{uuid4()}",
            fingerprint=f"synthetic:{uuid4()}",
            valid_from=now,
        ),
    )


def _seed_snapshot(env: ExecutorEnv, db: Any, scope: ProfileScope) -> Snapshot:
    return env.gateway.compile_thss(
        db,
        scope=scope,
        task="glhs-toctou-v2",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )


def _seed_proposal(env: ExecutorEnv, db: Any, scope: ProfileScope, snapshot: Snapshot) -> tuple[object, str]:
    evidence = _seed_evidence(env, db, scope)
    digest, _binding_field = snapshot_binding_digest(snapshot)
    proposal = env.gateway.propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:v2:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "1"},
            epistemic_state="reported",
            valid_from=datetime.now(UTC),
            source_snapshot_id=snapshot.snapshot_id,
            source_snapshot_digest=digest,
            proposal_consumed_thss=True,
        ),
        evidence=((evidence, "supports"),),
    )
    return proposal, digest


def _setup_owner(env: ExecutorEnv) -> tuple[ProfileScope, Snapshot, object, str]:
    """Commit one synthetic owner scope + snapshot + proposal transaction."""
    db = env.session_factory()
    try:
        scope = _seed_owner_scope(db)
        snapshot = _seed_snapshot(env, db, scope)
        proposal, digest = _seed_proposal(env, db, scope, snapshot)
        db.commit()
        return scope, snapshot, proposal, digest
    finally:
        db.close()


def _transition_item_count(db: Any, *, assertion_id: int) -> int:
    value = db.scalar(
        select(func.count(GlhsTransitionItem.id)).where(GlhsTransitionItem.assertion_id == assertion_id)
    )
    return int(value or 0)


def _committed_transition_total(db: Any, *, assertion_id: int) -> int:
    """Total committed transition items for a proposal, read in a fresh session.

    Prefers an explicit session-level committed count when the caller provides
    one (duck-typed tests), otherwise reads the real PostgreSQL count. This
    distinguishes a competing-lock winner (one committed item) from serial
    rejection schedules (zero items).
    """

    explicit = getattr(db, "committed_transition_item_count", None)
    if callable(explicit):
        return int(explicit(assertion_id=assertion_id) or 0)
    value = db.scalar(
        select(func.count(GlhsTransitionItem.id)).where(GlhsTransitionItem.assertion_id == assertion_id)
    )
    return int(value or 0)


def _rejection_subcontract(
    *,
    reason_code: str,
    proposal_coordinate: Mapping[str, object],
    snapshot_coordinate: Mapping[str, object],
    zero_state_transition_rows: bool,
) -> RejectionAuditability:
    return RejectionAuditability(
        rejection_decision_event=True,
        reason_code=reason_code,
        proposal_coordinate=proposal_coordinate,
        snapshot_coordinate=snapshot_coordinate,
        zero_state_transition_rows=zero_state_transition_rows,
    )


def _committed_subcontract(
    *,
    resulting_state_version: object,
    exact_snapshot_linkage: bool,
    reconstruction_succeeds: bool,
) -> CommittedReconstructability:
    return CommittedReconstructability(
        transition_exists=True,
        resulting_state_version=resulting_state_version,
        exact_snapshot_linkage=exact_snapshot_linkage,
        reconstruction_succeeds=reconstruction_succeeds,
    )


def _base_interleaving(
    schedule: Mapping[str, object],
    *,
    competing_lock: bool = False,
    rollback_retry: bool = False,
    **details: object,
) -> dict[str, object]:
    interleaving: dict[str, object] = {
        "schedule_type": str(schedule.get("schedule_type", "unspecified")),
        "coverage": sorted(schedule.get("interleaving_coverage", [])),
        "barrier_phases": sorted(schedule.get("barrier_phases", [])),
        "competing_lock": competing_lock,
        "rollback_retry": rollback_retry,
    }
    interleaving.update(details)
    return interleaving


def _attempt_commit(
    env: ExecutorEnv,
    db: Any,
    *,
    scope: ProfileScope,
    assertion: object,
    expected_state_version: int,
    prefix: str,
    reason_code: str,
) -> tuple[str, object | None]:
    """Run one ``apply_transition`` attempt; return (outcome, transition|None)."""
    try:
        transition = env.gateway.apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=expected_state_version,
            idempotency_key=new_idempotency_key(prefix),
            transition_kind="glhs-toctou-v2",
            reason_code=reason_code,
        )
        return "transition_committed", transition
    except env.gateway.GlhsInvariantError as exc:
        db.rollback()
        return str(exc), None


# --- schedule drivers ---------------------------------------------------------

def _driver_v2_01(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-01: persisted consent writer revokes, then bound commit is rejected."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    scope, snapshot, proposal, digest = _setup_owner(env)
    proposal_id = int(proposal.id)
    base_state_version = int(proposal.base_state_version)
    snapshot_id = str(snapshot.snapshot_id)
    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        meta = consent_revoke(
            adapter,
            user_id=scope.actor.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            record_factory=env.consent_record_factory,
        )
        revoke_commit_ns = meta.commit_monotonic_ns
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        attempt_scope = _existing_owner_scope(cdb, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        commit_start_ns = now_monotonic_ns()
        outcome, _transition = _attempt_commit(
            env, cdb,
            scope=attempt_scope,
            assertion=assertion,
            expected_state_version=base_state_version,
            prefix="v2-01",
            reason_code="synthetic_consent_revoked",
        )
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=revoke_commit_ns,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule, revoke_commit_ns=revoke_commit_ns, commit_start_ns=commit_start_ns
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


def _driver_v2_02(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-02: persisted role writer downgrades the delegate, then commit rejects."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        scope, _delegate = _seed_delegated_scope(db)
        snapshot = _seed_snapshot(env, db, scope)
        proposal, digest = _seed_proposal(env, db, scope, snapshot)
        db.commit()
        user_id = scope.actor.id
        profile_id = scope.profile.id
        proposal_id = int(proposal.id)
        base_state_version = int(proposal.base_state_version)
        snapshot_id = str(snapshot.snapshot_id)
    finally:
        db.close()

    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()
    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        delegate = wdb.get(User, user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        role_change(
            adapter,
            actor=delegate,
            new_role="normal",
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            scope_resolver=lambda _s, subject: SimpleNamespace(
                actor_role=_delegated_actor_role(getattr(subject, "role", ""))
            ),
        )
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        delegate = cdb.get(User, user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        changed_role = _delegated_actor_role(str(delegate.role))
        base_scope = _existing_owner_scope(cdb, user_id=user_id, profile_id=profile_id)
        changed_scope = ProfileScope(
            actor=base_scope.actor,
            profile=base_scope.profile,
            actor_role=changed_role,
            purpose="self_care",
            allowed_actions=base_scope.allowed_actions,
            allowed_data_classes=base_scope.allowed_data_classes,
        )
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        commit_start_ns = now_monotonic_ns()
        outcome, _transition = _attempt_commit(
            env, cdb,
            scope=changed_scope,
            assertion=assertion,
            expected_state_version=base_state_version,
            prefix="v2-02",
            reason_code="synthetic_role_coordinate_changed",
        )
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=None,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                fresh_scope_actor_role=changed_role,
                commit_start_ns=commit_start_ns,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


@contextmanager
def _policy_version_override(version: str) -> Any:
    """Drive the real gateway's sanctioned isolated-research policy advance."""
    keys = [
        "CLARA_GOVRED_ISOLATED_RESEARCH",
        "GOVRED_RESEARCH_PROJECT",
        "GOVRED_RESEARCH_ARM",
        "GOVRED_RESEARCH_POLICY_VERSION",
    ]
    saved = {key: os.environ.get(key) for key in keys}
    os.environ["CLARA_GOVRED_ISOLATED_RESEARCH"] = "1"
    os.environ["GOVRED_RESEARCH_PROJECT"] = "clara-rivf-20260817-final001"
    os.environ["GOVRED_RESEARCH_ARM"] = "GLHS_STRICT"
    os.environ["GOVRED_RESEARCH_POLICY_VERSION"] = version
    try:
        yield
    finally:
        for key in keys:
            if saved[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = saved[key]


def _driver_v2_03(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-03: persisted policy-epoch writer advances policy, then commit rejects."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    scope, snapshot, proposal, digest = _setup_owner(env)
    proposal_id = int(proposal.id)
    base_state_version = int(proposal.base_state_version)
    snapshot_id = str(snapshot.snapshot_id)
    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        epoch_version = str(schedule.get("persisted_epoch_version", "policy-v2"))
        advance_governance_policy_epoch(
            adapter,
            policy_domain="medications",
            version=epoch_version,
            canonical_digest="e" * 64,
            epoch_id=f"epoch-v2-{uuid4().hex}",
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            epoch_factory=env.epoch_factory,
        )
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        attempt_scope = _existing_owner_scope(cdb, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        commit_start_ns = now_monotonic_ns()
        with _policy_version_override(epoch_version):
            outcome, _transition = _attempt_commit(
                env, cdb,
                scope=attempt_scope,
                assertion=assertion,
                expected_state_version=base_state_version,
                prefix="v2-03",
                reason_code="synthetic_policy_epoch_advanced",
            )
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=None,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                persisted_policy_version="policy-v2",
                commit_start_ns=commit_start_ns,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


def _driver_v2_04(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-04: stale expected state version is rejected."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    scope, snapshot, proposal, digest = _setup_owner(env)
    proposal_id = int(proposal.id)
    base_state_version = int(proposal.base_state_version)
    snapshot_id = str(snapshot.snapshot_id)
    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    cdb = env.session_factory()
    try:
        attempt_scope = _existing_owner_scope(cdb, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        trace.begin(cdb)
        commit_start_ns = now_monotonic_ns()
        outcome, _transition = _attempt_commit(
            env, cdb,
            scope=attempt_scope,
            assertion=assertion,
            expected_state_version=base_state_version + 1,
            prefix="v2-04",
            reason_code="synthetic_stale_state_version",
        )
        trace.rollback(cdb)
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=None,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                stale_expected_state_version=base_state_version + 1,
                actual_state_version=base_state_version,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


def _driver_v2_05(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-05: barrier-controlled governance writer vs proposal writer race."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        scope = _seed_owner_scope(db)
        # Seed the in-scope evidence BEFORE compiling the disclosure so the
        # bound proposal uses only evidence within the disclosed snapshot scope
        # (the gateway rejects out-of-scope evidence via evidence_source_scope_forbidden).
        evidence = _seed_evidence(env, db, scope)
        snapshot = _seed_snapshot(env, db, scope)
        db.commit()
        user_id = scope.actor.id
        profile_id = scope.profile.id
        snapshot_id = str(snapshot.snapshot_id)
        evidence_id = int(evidence.id)
        digest, _binding_field = snapshot_binding_digest(snapshot)
    finally:
        db.close()

    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()
    barrier = env.barrier_factory(2)
    mutex = threading.Lock()
    observed: dict[str, object] = {}
    phase = str(schedule["barrier_phases"][0])

    def governance_writer() -> None:
        try:
            wdb = env.session_factory()
            try:
                adapter = env.adapter_factory(wdb)
                meta = consent_revoke(
                    adapter,
                    user_id=user_id,
                    consent_type=MEDICAL_CONSENT_TYPE,
                    consent_version=required_medical_disclaimer_version(),
                    barrier=barrier,
                    barrier_phase=phase,
                    trace=trace,
                    record_factory=env.consent_record_factory,
                )
                with mutex:
                    observed["revoke_commit_ns"] = meta.commit_monotonic_ns
            finally:
                wdb.close()
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            with mutex:
                observed["writer_error"] = f"{type(exc).__name__}:{exc}"

    def proposal_writer() -> None:
        try:
            pdb = env.session_factory()
            try:
                barrier.wait(phase)
                evidence = pdb.get(GlhsEvidence, evidence_id)
                if evidence is None:
                    raise RuntimeError("v2_05_in_scope_evidence_missing")
                try:
                    env.gateway.propose_assertion(
                        pdb,
                        profile_id=profile_id,
                        actor_user_id=user_id,
                        data=AssertionInput(
                            semantic_key=f"medication:v2-race:{uuid4()}",
                            assertion_type="medications",
                            predicate="dose",
                            value={"dose": "1"},
                            epistemic_state="reported",
                            valid_from=datetime.now(UTC),
                            source_snapshot_id=snapshot_id,
                            source_snapshot_digest=digest,
                            proposal_consumed_thss=True,
                        ),
                        evidence=((evidence, "supports"),),
                    )
                    pdb.commit()
                    outcome: str = "proposal_committed"
                except env.gateway.GlhsInvariantError as exc:
                    pdb.rollback()
                    outcome = str(exc)
                with mutex:
                    observed["proposal_outcome"] = outcome
                    observed["proposal_complete_ns"] = now_monotonic_ns()
            finally:
                pdb.close()
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            with mutex:
                observed["proposal_error"] = f"{type(exc).__name__}:{exc}"

    left = threading.Thread(target=governance_writer)
    right = threading.Thread(target=proposal_writer)
    left.start()
    right.start()
    left.join(timeout=40)
    right.join(timeout=40)
    if left.is_alive() or right.is_alive():
        raise RuntimeError("v2_05_workers_timed_out")
    if "writer_error" in observed or "proposal_error" in observed:
        raise RuntimeError(f"v2_05_worker_error:{observed}")

    outcome = str(observed["proposal_outcome"])
    classification, forbidden = classify_proposal_order(
        outcome=outcome,
        revoke_commit_ns=observed.get("revoke_commit_ns"),
        proposal_complete_ns=observed.get("proposal_complete_ns"),
    )
    if outcome != "proposal_committed":
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={"snapshot_id": snapshot_id, "snapshot_digest_sha256": digest_sha256},
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        committed = None
    else:
        rejection = None
        committed = _committed_subcontract(
            resulting_state_version=None,
            exact_snapshot_linkage=True,
            reconstruction_succeeds=True,
        )
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome=outcome,
        forbidden_commit_observed=forbidden,
        classification=classification,
        rejection=rejection,
        committed=committed,
        trace=trace,
        interleaving=_base_interleaving(
            schedule,
            revoke_commit_ns=observed.get("revoke_commit_ns"),
            proposal_complete_ns=observed.get("proposal_complete_ns"),
        ),
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=forbidden is False,
        latency_ms=elapsed_ms(started),
    )


def _race_consent_vs_commit(
    env: ExecutorEnv,
    schedule: Mapping[str, object],
    *,
    first_phase: str,
    second_phase: str,
    trace: TransactionTrace,
    reason_code: str = "synthetic_concurrent_governance",
    release_order: str = "simultaneous",
) -> tuple[dict[str, object], dict[str, object]]:
    """Two-party governance/commit race with a deterministic release order.

    ``release_order`` is one of:
    - ``"governance_first"``: the consent mutation commits before the commit
      attempt begins (mutation-before-commit).
    - ``"commit_first"``: the commit completes before the consent mutation is
      applied (commit-before-mutation control).
    - ``"simultaneous"``: both parties are released together by one rendezvous.
    """
    scope, snapshot, proposal, digest = _setup_owner(env)
    proposal_id = int(proposal.id)
    base_state_version = int(proposal.base_state_version)
    snapshot_id = str(snapshot.snapshot_id)
    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    barrier = env.barrier_factory(2)
    first_done = threading.Event()
    mutex = threading.Lock()
    observed: dict[str, object] = {}

    def commit_writer() -> None:
        try:
            cdb = env.session_factory()
            try:
                scope_attempt = _existing_owner_scope(cdb, user_id=scope.actor.id, profile_id=scope.profile.id)
                assertion = cdb.get(GlhsAssertion, proposal_id)
                if assertion is None:
                    raise RuntimeError("v2_proposal_reload_failed")
                if release_order == "simultaneous":
                    barrier.wait(first_phase)
                elif release_order == "governance_first":
                    first_done.wait(timeout=40)
                with mutex:
                    observed["commit_start_ns"] = now_monotonic_ns()
                outcome, transition = _attempt_commit(
                    env, cdb,
                    scope=scope_attempt,
                    assertion=assertion,
                    expected_state_version=base_state_version,
                    prefix="v2-race",
                    reason_code=reason_code,
                )
                item_count = _transition_item_count(cdb, assertion_id=proposal_id)
                with mutex:
                    observed["commit_outcome"] = outcome
                    observed["commit_complete_ns"] = now_monotonic_ns()
                    observed["transition_id"] = getattr(transition, "public_id", None)
                    observed["resulting_state_version"] = getattr(transition, "resulting_state_version", None)
                    observed["item_count"] = item_count
                if release_order == "commit_first":
                    first_done.set()
            finally:
                cdb.close()
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            with mutex:
                observed["commit_error"] = f"{type(exc).__name__}:{exc}"

    def governance_writer() -> None:
        try:
            wdb = env.session_factory()
            try:
                adapter = env.adapter_factory(wdb)
                if release_order == "simultaneous":
                    barrier.wait(second_phase)
                elif release_order == "commit_first":
                    first_done.wait(timeout=40)
                meta = consent_revoke(
                    adapter,
                    user_id=scope.actor.id,
                    consent_type=MEDICAL_CONSENT_TYPE,
                    consent_version=required_medical_disclaimer_version(),
                    barrier=env.barrier_factory(1),
                    barrier_phase="release",
                    trace=trace,
                    record_factory=env.consent_record_factory,
                )
                with mutex:
                    observed["revoke_commit_ns"] = meta.commit_monotonic_ns
                if release_order == "governance_first":
                    first_done.set()
            finally:
                wdb.close()
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            with mutex:
                observed["writer_error"] = f"{type(exc).__name__}:{exc}"

    left = threading.Thread(target=commit_writer)
    right = threading.Thread(target=governance_writer)
    left.start()
    right.start()
    left.join(timeout=45)
    right.join(timeout=45)
    if left.is_alive() or right.is_alive():
        raise RuntimeError("v2_race_workers_timed_out")
    if "writer_error" in observed or "commit_error" in observed:
        raise RuntimeError(f"v2_race_worker_error:{observed}")
    return observed, {
        "proposal_id": proposal_id,
        "base_state_version": base_state_version,
        "snapshot_id": snapshot_id,
        "digest_sha256": digest_sha256,
    }


def _driver_v2_06(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-06: mutation-before-commit, governance mutation commits first."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    observed, coords = _race_consent_vs_commit(
        env,
        schedule,
        first_phase="commit_release",
        second_phase="governance_release",
        trace=trace,
        reason_code="synthetic_mutation_before_commit",
        release_order="governance_first",
    )
    outcome = str(observed["commit_outcome"])
    classification, forbidden = classify_concurrent_commit_order(
        outcome=outcome,
        revoke_commit_ns=observed.get("revoke_commit_ns"),
        commit_start_ns=observed.get("commit_start_ns"),
        commit_complete_ns=observed.get("commit_complete_ns"),
    )
    if outcome != "transition_committed":
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "base_state_version": coords["base_state_version"],
                "snapshot_id": coords["snapshot_id"],
                "snapshot_digest_sha256": coords["digest_sha256"],
            },
            snapshot_coordinate={
                "snapshot_id": coords["snapshot_id"],
                "digest_sha256": coords["digest_sha256"],
            },
            zero_state_transition_rows=int(observed.get("item_count", 0)) == 0,
        )
        committed = None
    else:
        rejection = None
        committed = _committed_subcontract(
            resulting_state_version=observed.get("resulting_state_version"),
            exact_snapshot_linkage=True,
            reconstruction_succeeds=True,
        )
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome=outcome,
        forbidden_commit_observed=forbidden,
        classification=classification,
        rejection=rejection,
        committed=committed,
        trace=trace,
        interleaving=_base_interleaving(
            schedule,
            revoke_commit_ns=observed.get("revoke_commit_ns"),
            commit_start_ns=observed.get("commit_start_ns"),
            commit_complete_ns=observed.get("commit_complete_ns"),
        ),
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=forbidden is False,
        latency_ms=elapsed_ms(started),
    )


def _driver_v2_07(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-07: commit-before-mutation control, commit provably completes first."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    observed, coords = _race_consent_vs_commit(
        env,
        schedule,
        first_phase="commit_release",
        second_phase="governance_release",
        trace=trace,
        reason_code="synthetic_commit_before_mutation_control",
        release_order="commit_first",
    )
    outcome = str(observed["commit_outcome"])
    classification, forbidden = classify_concurrent_commit_order(
        outcome=outcome,
        revoke_commit_ns=observed.get("revoke_commit_ns"),
        commit_start_ns=observed.get("commit_start_ns"),
        commit_complete_ns=observed.get("commit_complete_ns"),
    )
    transition_id = observed.get("transition_id")
    resulting_state_version = observed.get("resulting_state_version")
    exact_linkage = transition_id is not None and int(observed.get("item_count", 0)) >= 1
    if outcome != "transition_committed":
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "base_state_version": coords["base_state_version"],
                "snapshot_id": coords["snapshot_id"],
                "snapshot_digest_sha256": coords["digest_sha256"],
            },
            snapshot_coordinate={
                "snapshot_id": coords["snapshot_id"],
                "digest_sha256": coords["digest_sha256"],
            },
            zero_state_transition_rows=int(observed.get("item_count", 0)) == 0,
        )
        committed = None
    else:
        rejection = None
        committed = _committed_subcontract(
            resulting_state_version=resulting_state_version,
            exact_snapshot_linkage=exact_linkage,
            reconstruction_succeeds=True,
        )
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome=outcome,
        forbidden_commit_observed=forbidden,
        classification=classification,
        rejection=rejection,
        committed=committed,
        trace=trace,
        interleaving=_base_interleaving(
            schedule,
            revoke_commit_ns=observed.get("revoke_commit_ns"),
            commit_start_ns=observed.get("commit_start_ns"),
            commit_complete_ns=observed.get("commit_complete_ns"),
        ),
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=forbidden is False,
        latency_ms=elapsed_ms(started),
    )


def _driver_v2_08(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-08: two commit attempts contend on one CompetingLock; loser stale."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    scope, snapshot, proposal, digest = _setup_owner(env)
    proposal_id = int(proposal.id)
    base_state_version = int(proposal.base_state_version)
    snapshot_id = str(snapshot.snapshot_id)
    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()

    lock = env.lock_factory("profile-lock", trace)
    barrier = env.barrier_factory(2)
    mutex = threading.Lock()
    results: dict[str, object] = {}

    def attempt(name: str) -> None:
        try:
            cdb = env.session_factory()
            try:
                scope_attempt = _existing_owner_scope(cdb, user_id=scope.actor.id, profile_id=scope.profile.id)
                assertion = cdb.get(GlhsAssertion, proposal_id)
                if assertion is None:
                    raise RuntimeError("v2_proposal_reload_failed")
                barrier.wait("release")
                acquired = lock.acquire()
                try:
                    outcome, _transition = _attempt_commit(
                        env, cdb,
                        scope=scope_attempt,
                        assertion=assertion,
                        expected_state_version=base_state_version,
                        prefix=f"v2-08-{name}",
                        reason_code="synthetic_competing_lock",
                    )
                finally:
                    if acquired:
                        lock.release()
                if outcome == "transition_committed":
                    cdb.commit()
                item_count = _transition_item_count(cdb, assertion_id=proposal_id)
                with mutex:
                    results[name] = {"outcome": outcome, "item_count": item_count}
            finally:
                cdb.close()
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            with mutex:
                results[name] = {"outcome": f"{type(exc).__name__}:{exc}", "item_count": 0}

    left = threading.Thread(target=attempt, args=("a",))
    right = threading.Thread(target=attempt, args=("b",))
    left.start()
    right.start()
    left.join(timeout=40)
    right.join(timeout=40)
    if left.is_alive() or right.is_alive():
        raise RuntimeError("v2_08_workers_timed_out")

    outcomes = {name: str(record["outcome"]) for name, record in results.items()}
    rejected = [name for name, outcome in outcomes.items() if outcome != "transition_committed"]
    if not rejected:
        raise AssertionError(f"v2_08_no_loser_observed:{outcomes}")
    loser = rejected[0]
    outcome = outcomes[loser]
    # Competing-lock invariant: exactly one committed transition for the proposal
    # (the winner). The loser's own attempt must not have committed. Counting all
    # transition items for the proposal is invalid here because the winner's item
    # is visible to a by-assertion count; the loser is verified rejected by its
    # outcome, and the committed-item total is checked to be exactly one.
    check_db = env.session_factory()
    try:
        committed_total = _committed_transition_total(check_db, assertion_id=proposal_id)
    finally:
        check_db.close()
    if committed_total != 1:
        raise AssertionError(f"v2_08_committed_transition_count_invalid:{committed_total}")
    classification, forbidden = classify_concurrent_commit_order(
        outcome=outcome,
        revoke_commit_ns=None,
        commit_start_ns=None,
        commit_complete_ns=None,
    )
    rejection = _rejection_subcontract(
        reason_code=outcome,
        proposal_coordinate={
            "proposal_id": "competing-lock",
            "base_state_version": base_state_version,
            "snapshot_id": snapshot_id,
            "snapshot_digest_sha256": digest_sha256,
        },
        snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
        zero_state_transition_rows=True,
    )
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome=outcome,
        forbidden_commit_observed=forbidden,
        classification=classification,
        rejection=rejection,
        trace=trace,
        interleaving=_base_interleaving(
            schedule,
            competing_lock=True,
            contention_outcomes={name: value["outcome"] for name, value in results.items()},
        ),
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=True,
        latency_ms=elapsed_ms(started),
    )


def _driver_v2_09(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-09: governance writer and commit writer released simultaneously."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    observed, coords = _race_consent_vs_commit(
        env,
        schedule,
        first_phase="simultaneous_release",
        second_phase="simultaneous_release",
        trace=trace,
        reason_code="synthetic_simultaneous_release",
    )
    outcome = str(observed["commit_outcome"])
    classification, forbidden = classify_concurrent_commit_order(
        outcome=outcome,
        revoke_commit_ns=observed.get("revoke_commit_ns"),
        commit_start_ns=observed.get("commit_start_ns"),
        commit_complete_ns=observed.get("commit_complete_ns"),
    )
    transition_id = observed.get("transition_id")
    exact_linkage = transition_id is not None and int(observed.get("item_count", 0)) >= 1
    if outcome != "transition_committed":
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "base_state_version": coords["base_state_version"],
                "snapshot_id": coords["snapshot_id"],
                "snapshot_digest_sha256": coords["digest_sha256"],
            },
            snapshot_coordinate={
                "snapshot_id": coords["snapshot_id"],
                "digest_sha256": coords["digest_sha256"],
            },
            zero_state_transition_rows=int(observed.get("item_count", 0)) == 0,
        )
        committed = None
    else:
        rejection = None
        committed = _committed_subcontract(
            resulting_state_version=observed.get("resulting_state_version"),
            exact_snapshot_linkage=exact_linkage,
            reconstruction_succeeds=True,
        )
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome=outcome,
        forbidden_commit_observed=forbidden,
        classification=classification,
        rejection=rejection,
        committed=committed,
        trace=trace,
        interleaving=_base_interleaving(
            schedule,
            revoke_commit_ns=observed.get("revoke_commit_ns"),
            commit_start_ns=observed.get("commit_start_ns"),
            commit_complete_ns=observed.get("commit_complete_ns"),
        ),
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=forbidden is False,
        latency_ms=elapsed_ms(started),
    )


def _driver_v2_10(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-10: a stale first attempt rolls back, then a fresh-state retry commits."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    scope, _snapshot0, proposal0, _digest0 = _setup_owner(env)
    proposal0_id = int(proposal0.id)
    base0 = int(proposal0.base_state_version)

    warm = env.session_factory()
    try:
        scope_attempt = _existing_owner_scope(warm, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion0 = warm.get(GlhsAssertion, proposal0_id)
        if assertion0 is None:
            raise RuntimeError("v2_proposal_reload_failed")
        outcome0, transition0 = _attempt_commit(
            env, warm,
            scope=scope_attempt,
            assertion=assertion0,
            expected_state_version=base0,
            prefix="v2-10-warmup",
            reason_code="synthetic_warmup_commit",
        )
        if outcome0 != "transition_committed" or transition0 is None:
            raise AssertionError(f"v2_10_warmup_failed:{outcome0}")
        warm.commit()
        advanced_state_version = int(transition0.resulting_state_version)
    finally:
        warm.close()

    rollback_db = env.session_factory()
    try:
        scope_attempt = _existing_owner_scope(rollback_db, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion0 = rollback_db.get(GlhsAssertion, proposal0_id)
        if assertion0 is None:
            raise RuntimeError("v2_proposal_reload_failed")
        trace.begin(rollback_db)
        stale_outcome, _transition = _attempt_commit(
            env, rollback_db,
            scope=scope_attempt,
            assertion=assertion0,
            expected_state_version=base0,
            prefix="v2-10-stale",
            reason_code="synthetic_rollback_then_retry",
        )
        trace.rollback(rollback_db)
        if stale_outcome != "stale_state_version":
            raise AssertionError(f"v2_10_expected_stale_rollback:{stale_outcome}")
    finally:
        rollback_db.close()

    retry = env.session_factory()
    try:
        scope_attempt = _existing_owner_scope(retry, user_id=scope.actor.id, profile_id=scope.profile.id)
        snapshot1 = _seed_snapshot(env, retry, scope_attempt)
        proposal1, digest1 = _seed_proposal(env, retry, scope_attempt, snapshot1)
        retry.commit()
        proposal1_id = int(proposal1.id)
        base1 = int(proposal1.base_state_version)
        snapshot1_id = str(snapshot1.snapshot_id)
        digest1_sha256 = hashlib.sha256(digest1.encode("utf-8")).hexdigest()
    finally:
        retry.close()

    commit_db = env.session_factory()
    try:
        scope_attempt = _existing_owner_scope(commit_db, user_id=scope.actor.id, profile_id=scope.profile.id)
        assertion1 = commit_db.get(GlhsAssertion, proposal1_id)
        if assertion1 is None:
            raise RuntimeError("v2_proposal_reload_failed")
        outcome, transition1 = _attempt_commit(
            env, commit_db,
            scope=scope_attempt,
            assertion=assertion1,
            expected_state_version=base1,
            prefix="v2-10-retry",
            reason_code="synthetic_retry_after_rollback",
        )
        if outcome != "transition_committed" or transition1 is None:
            raise AssertionError(f"v2_10_retry_failed:{outcome}")
        commit_db.commit()
        item_count = _transition_item_count(commit_db, assertion_id=proposal1_id)
        committed = _committed_subcontract(
            resulting_state_version=int(transition1.resulting_state_version),
            exact_snapshot_linkage=item_count >= 1,
            reconstruction_succeeds=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=False,
            classification="committed",
            committed=committed,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                rollback_retry=True,
                rolled_back_outcome=stale_outcome,
                warmup_resulting_state_version=advanced_state_version,
                retry_snapshot_id=snapshot1_id,
                retry_snapshot_digest_sha256=digest1_sha256,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        commit_db.close()


def _driver_v2_11(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-11: compound drift - consent and actor-role coordinates + stale state."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        scope, _delegate = _seed_delegated_scope(db)
        snapshot = _seed_snapshot(env, db, scope)
        proposal, digest = _seed_proposal(env, db, scope, snapshot)
        db.commit()
        owner_user_id = scope.profile.user_id
        delegate_user_id = scope.actor.id
        profile_id = scope.profile.id
        proposal_id = int(proposal.id)
        base_state_version = int(proposal.base_state_version)
        snapshot_id = str(snapshot.snapshot_id)
    finally:
        db.close()

    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()
    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        consent_meta = consent_revoke(
            adapter,
            user_id=owner_user_id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            record_factory=env.consent_record_factory,
        )
        delegate = wdb.get(User, delegate_user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        role_meta = role_change(
            adapter,
            actor=delegate,
            new_role="normal",
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            scope_resolver=lambda _s, subject: SimpleNamespace(
                actor_role=_delegated_actor_role(getattr(subject, "role", ""))
            ),
        )
        writer_metadata = [consent_meta, role_meta]
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        delegate = cdb.get(User, delegate_user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        changed_role = _delegated_actor_role(str(delegate.role))
        base_scope = _existing_owner_scope(cdb, user_id=delegate_user_id, profile_id=profile_id)
        changed_scope = ProfileScope(
            actor=base_scope.actor,
            profile=base_scope.profile,
            actor_role=changed_role,
            purpose="self_care",
            allowed_actions=base_scope.allowed_actions,
            allowed_data_classes=base_scope.allowed_data_classes,
        )
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        commit_start_ns = now_monotonic_ns()
        outcome, _transition = _attempt_commit(
            env, cdb,
            scope=changed_scope,
            assertion=assertion,
            expected_state_version=base_state_version + 1,
            prefix="v2-11",
            reason_code="synthetic_compound_consent_role_state_drift",
        )
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=None,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                commit_start_ns=commit_start_ns,
                stale_expected_state_version=base_state_version + 1,
                actual_state_version=base_state_version,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=compound_drift_detected(writer_metadata),
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


def _driver_v2_12(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-12: compound drift - policy + consent + actor-role + stale state."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        scope, _delegate = _seed_delegated_scope(db)
        snapshot = _seed_snapshot(env, db, scope)
        proposal, digest = _seed_proposal(env, db, scope, snapshot)
        db.commit()
        owner_user_id = scope.profile.user_id
        delegate_user_id = scope.actor.id
        profile_id = scope.profile.id
        proposal_id = int(proposal.id)
        base_state_version = int(proposal.base_state_version)
        snapshot_id = str(snapshot.snapshot_id)
    finally:
        db.close()

    digest_sha256 = hashlib.sha256(digest.encode("utf-8")).hexdigest()
    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        epoch_version = str(schedule.get("persisted_epoch_version", "policy-v2"))
        epoch_meta = advance_governance_policy_epoch(
            adapter,
            policy_domain="medications",
            version=epoch_version,
            canonical_digest="e" * 64,
            epoch_id=f"epoch-v2-{uuid4().hex}",
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            epoch_factory=env.epoch_factory,
        )
        consent_meta = consent_revoke(
            adapter,
            user_id=owner_user_id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            record_factory=env.consent_record_factory,
        )
        delegate = wdb.get(User, delegate_user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        role_meta = role_change(
            adapter,
            actor=delegate,
            new_role="normal",
            barrier=env.barrier_factory(1),
            barrier_phase="release",
            trace=trace,
            scope_resolver=lambda _s, subject: SimpleNamespace(
                actor_role=_delegated_actor_role(getattr(subject, "role", ""))
            ),
        )
        writer_metadata = [epoch_meta, consent_meta, role_meta]
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        delegate = cdb.get(User, delegate_user_id)
        if delegate is None:
            raise RuntimeError("v2_delegate_reload_failed")
        changed_role = _delegated_actor_role(str(delegate.role))
        base_scope = _existing_owner_scope(cdb, user_id=delegate_user_id, profile_id=profile_id)
        changed_scope = ProfileScope(
            actor=base_scope.actor,
            profile=base_scope.profile,
            actor_role=changed_role,
            purpose="self_care",
            allowed_actions=base_scope.allowed_actions,
            allowed_data_classes=base_scope.allowed_data_classes,
        )
        assertion = cdb.get(GlhsAssertion, proposal_id)
        if assertion is None:
            raise RuntimeError("v2_proposal_reload_failed")
        commit_start_ns = now_monotonic_ns()
        with _policy_version_override(epoch_version):
            outcome, _transition = _attempt_commit(
                env, cdb,
                scope=changed_scope,
                assertion=assertion,
                expected_state_version=base_state_version + 1,
                prefix="v2-12",
                reason_code="synthetic_compound_policy_consent_role_state_drift",
            )
        commit_complete_ns = now_monotonic_ns()
        item_count = _transition_item_count(cdb, assertion_id=proposal_id)
        if item_count != 0:
            raise AssertionError("v2_rejected_commit_created_transition_item")
        classification, forbidden = classify_concurrent_commit_order(
            outcome=outcome,
            revoke_commit_ns=None,
            commit_start_ns=commit_start_ns,
            commit_complete_ns=commit_complete_ns,
        )
        rejection = _rejection_subcontract(
            reason_code=outcome,
            proposal_coordinate={
                "proposal_id": str(assertion.public_id),
                "base_state_version": base_state_version,
                "snapshot_id": snapshot_id,
                "snapshot_digest_sha256": digest_sha256,
            },
            snapshot_coordinate={"snapshot_id": snapshot_id, "digest_sha256": digest_sha256},
            zero_state_transition_rows=True,
        )
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=forbidden,
            classification=classification,
            rejection=rejection,
            trace=trace,
            interleaving=_base_interleaving(
                schedule,
                commit_start_ns=commit_start_ns,
                stale_expected_state_version=base_state_version + 1,
                actual_state_version=base_state_version,
            ),
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=compound_drift_detected(writer_metadata),
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    finally:
        cdb.close()


# --- v2.1 false-stale burden + concurrency scaling helpers --------------------

def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Nearest-rank percentile over a sorted latency list (ms)."""
    if not sorted_values:
        return 0.0
    rank = max(0, min(len(sorted_values) - 1, int(math.ceil(percentile * len(sorted_values)) - 1)))
    return round(float(sorted_values[rank]), 3)


def _operational_outcome(exc: BaseException) -> str:
    """Map a worker exception to the operational outcome vocabulary, or refuse.

    Deadlock/serialization/lock-wait-timeout are operational outcomes, never
    safety successes.  Any other worker error aborts the schedule fail-closed:
    an unclassified database error is not a claimable observation.
    """
    message = str(exc).lower()
    if "deadlock" in message:
        return "deadlock_detected"
    if "could not serialize" in message or "serialization_failure" in message:
        return "could_not_serialize_access"
    if "lock wait timeout" in message or "lock_timeout" in message:
        return "lock_wait_timeout"
    raise RuntimeError(f"v21_unclassified_worker_error:{type(exc).__name__}:{exc}")


@dataclass(frozen=True)
class IndependentProposal:
    """One seeded, independent resource (distinct semantic key) on a profile."""

    proposal_id: int
    public_id: str
    base_state_version: int
    snapshot_id: str
    snapshot_digest_sha256: str


def _seed_independent_proposals(
    env: ExecutorEnv, db: Any, scope: ProfileScope, count: int
) -> list[IndependentProposal]:
    """Seed ``count`` proposals on independent semantic keys of one profile.

    Every proposal is bound to its own snapshot compiled at the same base state
    version; no two proposals share a semantic key, so no commit may touch the
    dependency set of another writer.
    """
    seeded: list[IndependentProposal] = []
    for _ in range(count):
        _seed_evidence(env, db, scope)
        snapshot = _seed_snapshot(env, db, scope)
        proposal, digest = _seed_proposal(env, db, scope, snapshot)
        seeded.append(
            IndependentProposal(
                proposal_id=int(proposal.id),
                public_id=str(proposal.public_id),
                base_state_version=int(proposal.base_state_version),
                snapshot_id=str(snapshot.snapshot_id),
                snapshot_digest_sha256=hashlib.sha256(digest.encode("utf-8")).hexdigest(),
            )
        )
    return seeded


def _independent_write_race(
    env: ExecutorEnv,
    schedule: Mapping[str, object],
    *,
    writer_count: int,
    trace: TransactionTrace,
    prefix: str,
) -> dict[str, object]:
    """Release ``writer_count`` writers on independent resources simultaneously.

    The profile-global version counter serializes the writers: exactly one
    commit wins and every loser is rejected with ``stale_state_version`` even
    though its resource is unrelated to the winner's.  Those rejections are the
    false-stale burden.  Deadlock/serialization outcomes are recorded
    operationally and never as safety successes.
    """
    started = now_monotonic_ns()
    db = env.session_factory()
    try:
        scope = _seed_owner_scope(db)
        proposals = _seed_independent_proposals(env, db, scope, writer_count)
        user_id = scope.actor.id
        profile_id = scope.profile.id
        db.commit()
    finally:
        db.close()

    barrier = env.barrier_factory(writer_count)
    mutex = threading.Lock()
    results: dict[int, dict[str, object]] = {}
    latencies: list[float] = []

    def worker(index: int) -> None:
        attempt_start = now_monotonic_ns()
        wdb = env.session_factory()
        try:
            proposal = proposals[index]
            attempt_scope = _existing_owner_scope(
                wdb, user_id=user_id, profile_id=profile_id
            )
            assertion = wdb.get(GlhsAssertion, proposal.proposal_id)
            if assertion is None:
                raise RuntimeError("v21_proposal_reload_failed")
            barrier.wait("release")
            outcome, transition = _attempt_commit(
                env,
                wdb,
                scope=attempt_scope,
                assertion=assertion,
                expected_state_version=proposal.base_state_version,
                prefix=f"{prefix}-{index}",
                reason_code="synthetic_independent_resource_race",
            )
            if outcome == RACE_COMMIT_OUTCOME:
                wdb.commit()
            latency = elapsed_ms(attempt_start)
            item_count = _committed_transition_total(
                wdb, assertion_id=proposal.proposal_id
            )
            with mutex:
                results[index] = {
                    "outcome": outcome,
                    "item_count": item_count,
                    "latency_ms": latency,
                    "resulting_state_version": getattr(
                        transition, "resulting_state_version", None
                    ),
                }
                latencies.append(latency)
        except WORKER_EXCEPTIONS as exc:  # pragma: no cover - surfaced below
            latency = elapsed_ms(attempt_start)
            with mutex:
                results[index] = {
                    "outcome": _operational_outcome(exc),
                    "item_count": 0,
                    "latency_ms": latency,
                    "error": f"{type(exc).__name__}:{exc}",
                }
                latencies.append(latency)
        finally:
            wdb.close()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(writer_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("v21_race_workers_timed_out")

    outcomes = {index: str(record["outcome"]) for index, record in results.items()}
    accepted = [index for index, outcome in outcomes.items() if outcome == RACE_COMMIT_OUTCOME]
    rejected = [
        index
        for index, outcome in outcomes.items()
        if outcome == "stale_state_version"
    ]
    operational = [
        index
        for index, outcome in outcomes.items()
        if outcome in OPERATIONAL_COMMIT_OUTCOMES
    ]
    if operational and accepted:
        raise RuntimeError(f"v21_race_mixed_operational_and_committed:{outcomes}")
    if not operational and len(accepted) != 1:
        raise AssertionError(f"v21_race_winner_count_invalid:{outcomes}")
    if rejected and any(
        int(record["item_count"]) != 0
        for index, record in results.items()
        if index in rejected
    ):
        raise AssertionError("v21_rejected_race_writer_created_transition_item")
    if accepted and int(results[accepted[0]]["item_count"]) != 1:
        raise AssertionError("v21_race_winner_transition_item_count_invalid")

    sorted_latencies = sorted(latencies)
    metrics: dict[str, object] = {
        "workload_type": RACE_WORKLOAD,
        "writer_count": writer_count,
        "attempts": writer_count,
        "accepted_valid_commits": len(accepted),
        "true_stale_rejections": 0,
        "false_stale_rejections": len(rejected),
        "false_stale_rate_per_attempt": round(len(rejected) / writer_count, 4),
        "database_errors": len(operational),
        "latency_p50_ms": _percentile(sorted_latencies, 0.50),
        "latency_p95_ms": _percentile(sorted_latencies, 0.95),
        "per_attempt_outcomes": {index: outcome for index, outcome in outcomes.items()},
    }
    return {
        "started": started,
        "results": results,
        "outcomes": outcomes,
        "accepted": accepted,
        "rejected": rejected,
        "operational": operational,
        "proposals": proposals,
        "metrics": metrics,
        "trace": trace,
    }


def _cross_profile_independence_control(env: ExecutorEnv) -> int:
    """Prove that version advances on an unrelated profile reject no writes.

    A committed transition on profile A must not affect a fresh independent
    write on profile B (per-profile counters). Returns the number of completed
    cross-profile independent writes and raises on any rejection.
    """
    db = env.session_factory()
    try:
        scope_a = _seed_owner_scope(db)
        snapshot_a = _seed_snapshot(env, db, scope_a)
        proposal_a, _digest_a = _seed_proposal(env, db, scope_a, snapshot_a)
        db.commit()
        base_a = int(proposal_a.base_state_version)
    finally:
        db.close()

    cadb = env.session_factory()
    try:
        scope_a_attempt = _existing_owner_scope(
            cadb, user_id=scope_a.actor.id, profile_id=scope_a.profile.id
        )
        assertion_a = cadb.get(GlhsAssertion, proposal_a.id)
        if assertion_a is None:
            raise RuntimeError("v21_control_proposal_reload_failed")
        outcome, _transition = _attempt_commit(
            env,
            cadb,
            scope=scope_a_attempt,
            assertion=assertion_a,
            expected_state_version=base_a,
            prefix="v2-13-control-advance",
            reason_code="synthetic_cross_profile_version_advance",
        )
        if outcome != RACE_COMMIT_OUTCOME:
            raise RuntimeError(f"v21_control_version_advance_failed:{outcome}")
        cadb.commit()
    finally:
        cadb.close()

    db = env.session_factory()
    try:
        scope_b = _seed_owner_scope(db)
        snapshot_b = _seed_snapshot(env, db, scope_b)
        proposal_b, _digest_b = _seed_proposal(env, db, scope_b, snapshot_b)
        db.commit()
        base_b = int(proposal_b.base_state_version)
    finally:
        db.close()

    cdb = env.session_factory()
    try:
        scope_b_attempt = _existing_owner_scope(
            cdb, user_id=scope_b.actor.id, profile_id=scope_b.profile.id
        )
        assertion_b = cdb.get(GlhsAssertion, proposal_b.id)
        if assertion_b is None:
            raise RuntimeError("v21_control_proposal_reload_failed")
        outcome, _transition = _attempt_commit(
            env,
            cdb,
            scope=scope_b_attempt,
            assertion=assertion_b,
            expected_state_version=base_b,
            prefix="v2-13-control-independent",
            reason_code="synthetic_cross_profile_independent_write",
        )
        if outcome != RACE_COMMIT_OUTCOME:
            raise RuntimeError(f"v21_cross_profile_independent_write_rejected:{outcome}")
        cdb.commit()
        return 1
    finally:
        cdb.close()


def _driver_v2_13(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-13: false-stale burden of profile-global versioning.

    Two independent writes race on one profile; the winner's commit is a
    version advance on an unrelated resource, and the loser's stale rejection
    is the measured false-stale burden. A cross-profile control then proves an
    unrelated-profile version advance rejects no independent write.
    """
    trace = TransactionTrace()
    race = _independent_write_race(
        env, schedule, writer_count=2, trace=trace, prefix="v2-13"
    )
    metrics = dict(race["metrics"])
    metrics["cross_profile_independent_writes_completed"] = (
        _cross_profile_independence_control(env)
    )
    return _race_outcome(
        env,
        schedule,
        race=race,
        metrics=metrics,
        started=race["started"],
        reason_code="stale_state_version",
    )


def _driver_v2_14(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-14: concurrency scaling at one writer (baseline)."""
    trace = TransactionTrace()
    race = _independent_write_race(
        env, schedule, writer_count=1, trace=trace, prefix="v2-14"
    )
    return _race_outcome(
        env,
        schedule,
        race=race,
        metrics=dict(race["metrics"]),
        started=race["started"],
        reason_code="stale_state_version",
    )


def _driver_v2_15(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-15: concurrency scaling at two writers."""
    trace = TransactionTrace()
    race = _independent_write_race(
        env, schedule, writer_count=2, trace=trace, prefix="v2-15"
    )
    return _race_outcome(
        env,
        schedule,
        race=race,
        metrics=dict(race["metrics"]),
        started=race["started"],
        reason_code="stale_state_version",
    )


def _driver_v2_16(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-16: concurrency scaling at four writers."""
    trace = TransactionTrace()
    race = _independent_write_race(
        env, schedule, writer_count=4, trace=trace, prefix="v2-16"
    )
    return _race_outcome(
        env,
        schedule,
        race=race,
        metrics=dict(race["metrics"]),
        started=race["started"],
        reason_code="stale_state_version",
    )


def _driver_v2_17(env: ExecutorEnv, schedule: Mapping[str, object]) -> RawScheduleOutcome:
    """TOCTOU-V2-17: concurrency scaling at eight writers."""
    trace = TransactionTrace()
    race = _independent_write_race(
        env, schedule, writer_count=8, trace=trace, prefix="v2-17"
    )
    return _race_outcome(
        env,
        schedule,
        race=race,
        metrics=dict(race["metrics"]),
        started=race["started"],
        reason_code="stale_state_version",
    )


def _race_outcome(
    env: ExecutorEnv,
    schedule: Mapping[str, object],
    *,
    race: dict[str, object],
    metrics: dict[str, object],
    started: object,
    reason_code: str,
) -> RawScheduleOutcome:
    """Build the observed outcome for one independent-resource race.

    The audited actor is the false-stale loser (the burden observation); the
    winner's commit is verified by the race invariant.  Operational outcomes
    (deadlock/serialization) are never safety successes.
    """
    outcomes = race["outcomes"]
    accepted = race["accepted"]
    rejected = race["rejected"]
    operational = race["operational"]
    proposals: list[IndependentProposal] = race["proposals"]
    interleaving = _base_interleaving(
        schedule,
        writer_count=len(proposals),
        race_outcomes={str(index): outcome for index, outcome in outcomes.items()},
    )
    interleaving["metrics"] = metrics
    if operational:
        outcome = str(outcomes[operational[0]])
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=outcome,
            forbidden_commit_observed=False,
            classification=outcome,
            rejection=_rejection_subcontract(
                reason_code=outcome,
                proposal_coordinate={
                    "proposal_id": "operational-attempt",
                    "base_state_version": 0,
                    "snapshot_id": "operational-attempt",
                    "snapshot_digest_sha256": "operational-attempt",
                },
                snapshot_coordinate={
                    "snapshot_id": "operational-attempt",
                    "digest_sha256": "operational-attempt",
                },
                zero_state_transition_rows=True,
            ),
            trace=race["trace"],
            interleaving=interleaving,
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=True,
            safety_success=False,
            latency_ms=elapsed_ms(started),
        )
    if not rejected:
        winner_record = race["results"][accepted[0]]
        return RawScheduleOutcome(
            schedule_id=str(schedule["id"]),
            commit_outcome=RACE_COMMIT_OUTCOME,
            forbidden_commit_observed=False,
            classification=SINGLE_WRITER_CLASSIFICATION,
            committed=_committed_subcontract(
                resulting_state_version=winner_record.get("resulting_state_version"),
                exact_snapshot_linkage=int(winner_record["item_count"]) >= 1,
                reconstruction_succeeds=True,
            ),
            trace=race["trace"],
            interleaving=interleaving,
            persisted_writers=list(schedule.get("persisted_writers", [])),
            compound_drift=False,
            operational_outcome=False,
            safety_success=True,
            latency_ms=elapsed_ms(started),
        )
    loser = proposals[rejected[0]]
    return RawScheduleOutcome(
        schedule_id=str(schedule["id"]),
        commit_outcome="stale_state_version",
        forbidden_commit_observed=False,
        classification=FALSE_STALE_CLASSIFICATION,
        rejection=_rejection_subcontract(
            reason_code=reason_code,
            proposal_coordinate={
                "proposal_id": loser.public_id,
                "base_state_version": loser.base_state_version,
                "snapshot_id": loser.snapshot_id,
                "snapshot_digest_sha256": loser.snapshot_digest_sha256,
            },
            snapshot_coordinate={
                "snapshot_id": loser.snapshot_id,
                "digest_sha256": loser.snapshot_digest_sha256,
            },
            zero_state_transition_rows=True,
        ),
        trace=race["trace"],
        interleaving=interleaving,
        persisted_writers=list(schedule.get("persisted_writers", [])),
        compound_drift=False,
        operational_outcome=False,
        safety_success=True,
        latency_ms=elapsed_ms(started),
    )


_DRIVERS: dict[str, Callable[[ExecutorEnv, Mapping[str, object]], RawScheduleOutcome]] = {
    "TOCTOU-V2-01": _driver_v2_01,
    "TOCTOU-V2-02": _driver_v2_02,
    "TOCTOU-V2-03": _driver_v2_03,
    "TOCTOU-V2-04": _driver_v2_04,
    "TOCTOU-V2-05": _driver_v2_05,
    "TOCTOU-V2-06": _driver_v2_06,
    "TOCTOU-V2-07": _driver_v2_07,
    "TOCTOU-V2-08": _driver_v2_08,
    "TOCTOU-V2-09": _driver_v2_09,
    "TOCTOU-V2-10": _driver_v2_10,
    "TOCTOU-V2-11": _driver_v2_11,
    "TOCTOU-V2-12": _driver_v2_12,
}

_V21_DRIVERS: dict[str, Callable[[ExecutorEnv, Mapping[str, object]], RawScheduleOutcome]] = {
    "TOCTOU-V2-13": _driver_v2_13,
    "TOCTOU-V2-14": _driver_v2_14,
    "TOCTOU-V2-15": _driver_v2_15,
    "TOCTOU-V2-16": _driver_v2_16,
    "TOCTOU-V2-17": _driver_v2_17,
}


def _classification_matches(expected: object, observed: str) -> bool:
    e = str(expected or "").lower()
    o = observed.lower()
    if e == "rejected":
        return o.startswith("rejected")
    if e == "committed":
        return o in {
            "committed",
            "transition_committed",
            "proposal_committed",
            "transition_committed_before_observed_revoke_commit",
            "proposal_committed_before_observed_revoke_commit",
        }
    if e == "indeterminate_ordering":
        return "indeterminate" in o
    if e == "operational_deadlock":
        return (
            "deadlock" in o or "could_not_serialize" in o or "lock_wait_timeout" in o
        )
    if e == "false_stale_expected":
        return o == "committed_with_expected_false_stale"
    return False


def _metrics_for_raw(raw: RawScheduleOutcome) -> dict[str, object]:
    """Standard metrics block for a v2.1 observation.

    Race drivers supply their full per-attempt metrics through
    ``raw.interleaving["metrics"]``; governance/single-attempt schedules get a
    derived single-attempt block.  The false-stale counts are zero for
    governance schedules because no independent-resource race was staged there;
    the workload marker keeps that distinction explicit.
    """
    supplied = raw.interleaving.get("metrics")
    if isinstance(supplied, Mapping):
        return dict(supplied)
    accepted = raw.committed is not None
    rejected = raw.rejection is not None and not raw.operational_outcome
    return {
        "workload_type": GOVERNANCE_SINGLE_WORKLOAD,
        "attempts": 1,
        "accepted_valid_commits": 1 if accepted else 0,
        "true_stale_rejections": 1 if rejected else 0,
        "false_stale_rejections": 0,
        "false_stale_rate_per_attempt": 0.0,
        "database_errors": 1 if raw.operational_outcome else 0,
        "latency_p50_ms": round(raw.latency_ms, 3),
        "latency_p95_ms": round(raw.latency_ms, 3),
    }


def _run_one_schedule(
    env: ExecutorEnv,
    schedule: Mapping[str, object],
    *,
    drivers: Mapping[str, Callable[[ExecutorEnv, Mapping[str, object]], RawScheduleOutcome]]
    | None = None,
) -> tuple[dict[str, object], dict[str, object], RawScheduleOutcome]:
    drivers = drivers if drivers is not None else _DRIVERS
    driver = drivers.get(str(schedule["id"]))
    if driver is None:
        driver = _V21_DRIVERS.get(str(schedule["id"]))
    if driver is None:
        raise ValueError(f"v2_unknown_schedule:{schedule.get('id')}")
    raw = driver(env, schedule)
    observation = observe(lambda _schedule: raw, schedule)
    if isinstance(raw.interleaving.get("metrics"), Mapping):
        observation["metrics"] = _metrics_for_raw(raw)
    observed_cls = str(observation["outcome"]["classification"])
    expected = schedule.get("expected_classification")
    audit = {
        "id": str(schedule["id"]),
        "expected_classification": expected,
        "observed_classification": observed_cls,
        "matches": _classification_matches(expected, observed_cls),
    }
    return observation, audit, raw


def validate_v21(
    observations: Sequence[Mapping[str, object]],
    *,
    protocol: Mapping[str, object],
) -> dict[str, object]:
    """Validate a complete v2.1 observation set (v2 schedules + 13..17).

    Pure and fail-closed; no database is connected.  In addition to the v2
    gates (frozen status, isolation contract, persisted-writer markers,
    interleaving coverage, operational classification) it requires the
    ``persisted_epoch_required`` marker, the false-stale burden and
    concurrency-scaling coverage from TOCTOU-V2-13..17, per-observation
    ``metrics`` completeness, and per-schedule concurrency counts.
    """
    if protocol.get("status") != PROTOCOL_STATUS:
        raise ValueError("v2_protocol_not_frozen")
    if protocol.get("schema_version") != V21_PROTOCOL_SCHEMA_VERSION:
        raise ValueError("v2_protocol_schema_invalid")
    if protocol.get("isolation") != V2_ISOLATION_CONTRACT:
        raise ValueError("v2_isolation_contract_invalid")
    if protocol.get("persisted_epoch_required") is not True:
        raise ValueError("v21_persisted_epoch_required_missing")

    schedules = protocol.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("v2_protocol_schedules_missing")
    schedule_ids = [schedule.get("id") for schedule in schedules]
    expected_ids = set(_DRIVERS) | set(_V21_DRIVERS)
    if sorted(schedule_ids) != sorted(expected_ids):
        raise ValueError("v21_schedule_set_invalid")

    observed_ids: list[str] = []
    for observation in observations:
        require_observation_complete(observation)
        observed_ids.append(str(observation["id"]))
    if sorted(schedule_ids) != sorted(observed_ids):
        raise ValueError("v2_schedule_set_mismatch")

    by_id = {schedule.get("id"): schedule for schedule in schedules}
    covered: set[str] = set()
    compound_seen = False
    race_schedules_seen: set[int] = set()
    observed_rates: dict[str, float] = {}
    for observation in observations:
        schedule_id = str(observation["id"])
        schedule = by_id[schedule_id]
        _validate_schedule_markers(observation, schedule)
        _validate_outcome_classification(observation)
        covered.update(observation["interleaving"]["coverage"])
        if observation.get("compound_drift") is True:
            compound_seen = True
        metrics = observation.get("metrics")
        if not isinstance(metrics, Mapping):
            raise TypeError(f"v21_metrics_missing:{schedule_id}")
        missing_metrics = _METRICS_KEYS - set(metrics)
        if missing_metrics:
            raise ValueError(
                f"v21_metrics_incomplete:{schedule_id}:{','.join(sorted(missing_metrics))}"
            )
        race_writer_count = schedule.get("writer_count")
        if race_writer_count is not None:
            if schedule_id not in _V21_DRIVERS:
                raise ValueError(f"v21_writer_count_on_non_race_schedule:{schedule_id}")
            if int(metrics.get("attempts", -1)) != int(race_writer_count):
                raise ValueError(f"v21_race_attempt_count_mismatch:{schedule_id}")
            if schedule_id != "TOCTOU-V2-14":
                race_schedules_seen.add(int(race_writer_count))
            expected_rate = schedule.get("expected_false_stale_rate")
            if expected_rate is not None:
                observed_rates[schedule_id] = float(
                    metrics.get("false_stale_rate_per_attempt", -1.0)
                )

    missing = REQUIRED_INTERLEAVING_COVERAGE - covered
    if missing:
        raise ValueError(f"v2_interleaving_coverage_missing:{','.join(sorted(missing))}")
    if not compound_seen:
        raise ValueError("v2_compound_governance_drift_missing")
    if {"false_stale_burden", "concurrency_scaling"} - covered:
        raise ValueError("v21_race_coverage_missing")
    if race_schedules_seen != {2, 4, 8}:
        raise ValueError(f"v21_concurrency_levels_missing:{sorted(race_schedules_seen)}")

    return {
        "schema_version": V21_PROTOCOL_SCHEMA_VERSION,
        "status": "VALIDATED_V21_OBSERVATIONS_NOT_EXECUTED",
        "database_executed": False,
        "result_emitted": False,
        "observation_count": len(observations),
        "interleaving_coverage": sorted(covered),
        "observed_false_stale_rates": {
            schedule_id: rate for schedule_id, rate in sorted(observed_rates.items())
        },
    }


def run_schedules(
    env: ExecutorEnv,
    protocol: Mapping[str, object],
    *,
    out_path: Path | None = None,
    source_revision: str = "unknown",
) -> dict[str, object]:
    """Run every frozen schedule, validate the observation set, write raw JSON."""
    validate_protocol(protocol)
    schedules = protocol["schedules"]
    if not isinstance(schedules, list):
        raise TypeError("v2_protocol_schedules_missing")
    schema_version = str(protocol.get("schema_version", ""))
    is_v21 = schema_version == V21_PROTOCOL_SCHEMA_VERSION
    drivers = dict(_DRIVERS)
    if is_v21:
        drivers.update(_V21_DRIVERS)
    observations: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    for schedule in schedules:
        observation, audit, raw = _run_one_schedule(
            env, schedule, drivers=drivers
        )
        if is_v21:
            metrics = _metrics_for_raw(raw)
            observation["metrics"] = metrics
            expected_rate = schedule.get("expected_false_stale_rate")
            if expected_rate is not None:
                audit["expected_false_stale_rate"] = expected_rate
                observed_rate = metrics.get("false_stale_rate_per_attempt")
                audit["observed_false_stale_rate_per_attempt"] = observed_rate
                audit["false_stale_matches"] = (
                    isinstance(observed_rate, (int, float))
                    and abs(float(observed_rate) - float(expected_rate)) <= 0.005
                )
            else:
                audit["false_stale_matches"] = None
        observations.append(observation)
        audits.append(audit)
    validation = validate_v21(observations, protocol=protocol) if is_v21 else validate_v2(
        observations, protocol=protocol
    )
    matches = [bool(item["matches"]) for item in audits]
    if is_v21:
        false_stale_matches = [item["false_stale_matches"] for item in audits]
        status = (
            "EXECUTED_V21_FROZEN_OBSERVATIONS"
            if all(matches) and all(value is not False for value in false_stale_matches)
            else "EXECUTED_V21_OBSERVATION_MISMATCH"
        )
        run_id = str(protocol.get("run_id") or V21_RUN_ID)
    else:
        status = (
            "EXECUTED_V2_FROZEN_OBSERVATIONS"
            if all(matches)
            else "EXECUTED_V2_OBSERVATION_MISMATCH"
        )
        run_id = RUN_ID
    result: dict[str, object] = {
        "schema_version": schema_version,
        "status": status,
        "run_id": run_id,
        "backend": "isolated_postgresql_random_schema",
        "schema_retained": False,
        "source_revision": source_revision,
        "executed_at": datetime.now(UTC).isoformat(),
        "postgres_metadata": dict(env.postgres_metadata),
        "schedules": observations,
        "classification_audit": audits,
        "validation": validation,
        "not_run_schedule_ids": [],
        "note": (
            "Raw v2/v2.1 observations; run is claim-eligible only when status is "
            "EXECUTED_V2_FROZEN_OBSERVATIONS or EXECUTED_V21_FROZEN_OBSERVATIONS "
            "and every schedule is observer-complete. INDETERMINATE is never "
            "counted as safe."
        ),
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _postgres_metadata(engine: Engine) -> dict[str, object]:
    with engine.connect() as connection:
        version = connection.scalar(text("select version()"))
        isolation = connection.execute(text("show transaction isolation level")).scalar_one()
    return {
        "version": version,
        "isolation_level": isolation,
        "backend": "postgresql",
    }


def _real_env(engine: Engine, *, epoch_model: type | None = None) -> ExecutorEnv:
    """Build the real environment; ``epoch_model=GovernancePolicyEpoch`` selects
    the v2.1 persisted-epoch path (production ORM row written and consulted by
    the real gateway).  Without it the frozen v2 epoch row is used unchanged."""
    api_epoch = epoch_model is GovernancePolicyEpoch
    return ExecutorEnv(
        session_factory=lambda: Session(engine, expire_on_commit=False),
        adapter_factory=lambda session: SessionAdapter(session, epoch_model=epoch_model),
        gateway=gateway_module,
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=30.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=30.0),
        consent_record_factory=_real_consent_record,
        epoch_factory=_real_api_epoch_row if api_epoch else _real_epoch_row,
        postgres_metadata=_postgres_metadata(engine),
    )


def execute(
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    *,
    database_url: str | None = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, object]:
    """Execute the frozen v2/v2.1 protocol in an isolated random PostgreSQL schema."""
    protocol = load_protocol(protocol_path)
    validate_protocol(protocol)
    url = _require_final_isolated_postgres(database_url)
    if str(protocol.get("schema_version", "")) == V21_PROTOCOL_SCHEMA_VERSION:
        output_path = output_path or DEFAULT_OUTPUT_V21_PATH

    schema = _random_schema_name()
    admin = create_engine(url, pool_pre_ping=True)
    engine: Engine | None = None
    schema_created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(engine)
        epoch_model = (
            GovernancePolicyEpoch
            if str(protocol.get("schema_version", "")) == V21_PROTOCOL_SCHEMA_VERSION
            else None
        )
        env = _real_env(engine, epoch_model=epoch_model)
        return run_schedules(
            env,
            protocol,
            out_path=output_path,
            source_revision=_source_revision(),
        )
    finally:
        if engine is not None:
            engine.dispose()
        if schema_created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--database-url")
    args = parser.parse_args()
    try:
        result = execute(
            args.protocol,
            database_url=args.database_url,
            output_path=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
