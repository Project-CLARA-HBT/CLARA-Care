"""Development-only PostgreSQL probes for GLHS disclosure-to-commit TOCTOU.

This is not a final experiment runner.  It creates a random schema on an
explicitly isolated PostgreSQL instance and reports only the schedules it
actually executes.  It refuses SQLite, shared/default execution, and any
missing isolation attestation.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock, Thread
from uuid import uuid4

import clara_api.glhs.gateway as gateway_module
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    required_medical_disclaimer_version,
)
from clara_api.core.security import TokenPayload
from clara_api.db.base import Base
from clara_api.db.models import (
    FamilyAccessGrant,
    GlhsAssertion,
    GlhsTransitionItem,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    reconstruct_governed_decision,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def _require_isolated_postgres() -> str:
    if os.environ.get("GLHS_TOCTOU_ISOLATED_RESEARCH") != "1":
        raise RuntimeError("glhs_toctou_requires_isolated_research_attestation")
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("glhs_toctou_requires_postgresql_database_url")
    return url


def _schema_name() -> str:
    return f"glhs_toctou_dev_{uuid4().hex}"


def _engine(url: str, schema: str) -> Engine:
    return create_engine(url, connect_args={"options": f"-csearch_path={schema}"})


def _scope(db: Session) -> ProfileScope:
    user = User(email=f"glhs-toctou-{uuid4().hex}@example.test", hashed_password="x", role="normal")
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


def _existing_scope(db: Session, *, user_id: int, profile_id: int) -> ProfileScope:
    user = db.get(User, user_id)
    profile = db.get(PhrProfile, profile_id)
    if user is None or profile is None:
        raise RuntimeError("toctou_synthetic_scope_missing")
    return ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "resolve", "view"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def _delegated_scope_with_persisted_role(db: Session) -> tuple[ProfileScope, TokenPayload]:
    """Create a synthetic delegated scope resolved from persisted grant/role data."""

    owner = User(email=f"glhs-owner-{uuid4().hex}@example.test", hashed_password="x", role="normal")
    delegate = User(
        email=f"glhs-delegate-{uuid4().hex}@example.test", hashed_password="x", role="doctor"
    )
    db.add_all((owner, delegate))
    db.flush()
    profile = PhrProfile(user_id=owner.id)
    db.add(profile)
    # ``FamilyAccessGrant.profile_id`` is non-null.  Flush the synthetic
    # profile before constructing its persisted grant rather than relying on
    # a later unit-of-work flush to infer this scalar foreign key.
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
    token = TokenPayload(sub=delegate.email, role="normal")
    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=profile.public_id,
        action="create",
        data_class="medications",
        purpose="self_care",
    )
    if scope.actor_role != "clinician":
        raise AssertionError("toctou_synthetic_delegate_role_not_clinician")
    return scope, token


def _evidence(db: Session, scope: ProfileScope):
    now = datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="glhs-toctou-development",
        source_identity=f"synthetic:{uuid4()}",
        checksum=f"synthetic:{uuid4()}",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="glhs-toctou-development",
            artifact_type="synthetic",
            artifact_public_id=f"synthetic:{uuid4()}",
            fingerprint=f"synthetic:{uuid4()}",
            valid_from=now,
        ),
    )


def _proposal_after_snapshot(db: Session, scope: ProfileScope, snapshot_id: str, digest: str):
    evidence = _evidence(db, scope)
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:toctou:{uuid4()}",
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


def _binding_digest(snapshot: object) -> tuple[str, str]:
    """Require the reviewed manifest-digest contract, without legacy fallback."""

    manifest_digest = getattr(snapshot, "manifest_digest", None)
    if isinstance(manifest_digest, str) and manifest_digest:
        return manifest_digest, "manifest_digest"
    raise RuntimeError("snapshot_manifest_digest_contract_unavailable")


def _classify_concurrent_commit_order(
    *,
    outcome: str,
    revoke_commit_ns: object,
    commit_start_ns: object,
    commit_complete_ns: object,
) -> tuple[str, bool | None]:
    """Classify only ordering facts that the driver actually observed.

    A completed revoke observed before ``apply_transition`` starts proves the
    attempted commit is post-revocation from the driver's perspective.  A
    successful transition in that state is a forbidden development observation,
    never an indeterminate one.  Other overlapping windows retain the more
    conservative indeterminate classification.
    """

    observed_revoke_before_commit_start = (
        isinstance(revoke_commit_ns, int)
        and isinstance(commit_start_ns, int)
        and revoke_commit_ns < commit_start_ns
    )
    if outcome != "transition_committed":
        return (
            "rejected_after_observed_revoke_commit"
            if observed_revoke_before_commit_start
            else "rejected_during_or_before_governance_race",
            False,
        )
    if observed_revoke_before_commit_start:
        return "forbidden_transition_committed_after_observed_revoke", True
    if (
        isinstance(revoke_commit_ns, int)
        and isinstance(commit_complete_ns, int)
        and commit_complete_ns < revoke_commit_ns
    ):
        return "transition_committed_before_observed_revoke_commit", False
    return "indeterminate_ordering_transition_committed", None


def _sanitized_ledger_observation(
    db: Session,
    *,
    profile_id: int,
    assertion_id: int,
    snapshot_id: str,
    transition_id: str | None,
) -> dict[str, object]:
    """Observe linkage counts only, never clinical or audit payload values."""

    transition_item_count = int(
        db.scalar(
            select(func.count(GlhsTransitionItem.id)).where(
                GlhsTransitionItem.assertion_id == assertion_id
            )
        )
        or 0
    )
    if transition_id is None:
        return {
            "transition_item_count": transition_item_count,
            "reconstruction_status": "no_commit_expected",
        }
    reconstruction = reconstruct_governed_decision(
        db,
        profile_id=profile_id,
        snapshot_id=snapshot_id,
        transition_id=transition_id,
    )
    decisions = reconstruction.get("decisions")
    exact_linkage = (
        isinstance(decisions, list)
        and len(decisions) == 1
        and decisions[0].get("source_snapshot_id") == snapshot_id
        and transition_item_count >= 1
    )
    return {
        "transition_item_count": transition_item_count,
        "reconstruction_status": "exact_snapshot_linkage"
        if exact_linkage
        else "linkage_incomplete",
    }


def _consent_revoke_schedule(db: Session, scope: ProfileScope) -> dict[str, object]:
    started = time.perf_counter()
    snapshot = compile_thss(
        db,
        scope=scope,
        task="glhs-toctou-development",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    binding_digest, binding_field = _binding_digest(snapshot)
    proposal = _proposal_after_snapshot(db, scope, snapshot.snapshot_id, binding_digest)
    db.add(
        UserConsent(
            user_id=scope.actor.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            revoked_at=datetime.now(UTC),
        )
    )
    db.flush()
    try:
        apply_transition(
            db,
            scope=scope,
            assertion=proposal,
            action="activate",
            expected_state_version=proposal.base_state_version,
            idempotency_key=f"toctou-consent-revoke:{uuid4()}",
            transition_kind="glhs-toctou-development",
            reason_code="synthetic_consent_revoked",
        )
    except GlhsInvariantError as exc:
        outcome = str(exc)
    else:  # pragma: no cover - a failed safety assertion
        raise AssertionError("consent-revoked proposal unexpectedly committed")
    if outcome != "assertion_consent_mismatch":
        raise AssertionError(f"unexpected_consent_rejection:{outcome}")
    ledger_observation = _sanitized_ledger_observation(
        db,
        profile_id=scope.profile.id,
        assertion_id=proposal.id,
        snapshot_id=snapshot.snapshot_id,
        transition_id=None,
    )
    if ledger_observation["transition_item_count"] != 0:
        raise AssertionError("rejected_consent_commit_created_transition_item")
    return {
        "id": "TOCTOU-01",
        "run_status": "EXECUTED_DEVELOPMENT_ONLY",
        "commit_outcome": outcome,
        "transition_attempt": "apply_transition",
        "ledger_observation": ledger_observation,
        "forbidden_commit_observed": False,
        "snapshot_binding_field": binding_field,
        "snapshot_digest_sha256": hashlib.sha256(binding_digest.encode()).hexdigest(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _policy_change_schedule(db: Session, scope: ProfileScope) -> dict[str, object]:
    started = time.perf_counter()
    snapshot = compile_thss(
        db,
        scope=scope,
        task="glhs-toctou-development",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    binding_digest, binding_field = _binding_digest(snapshot)
    original_policy = gateway_module.POLICY_VERSION
    gateway_module.POLICY_VERSION = f"{original_policy}-development-change"
    try:
        try:
            _proposal_after_snapshot(db, scope, snapshot.snapshot_id, binding_digest)
        except GlhsInvariantError as exc:
            outcome = str(exc)
        else:  # pragma: no cover - a failed safety assertion
            raise AssertionError("policy-changed snapshot unexpectedly admitted")
    finally:
        gateway_module.POLICY_VERSION = original_policy
    if outcome != "proposal_snapshot_policy_mismatch":
        raise AssertionError(f"unexpected_policy_rejection:{outcome}")
    return {
        "id": "TOCTOU-04",
        "run_status": "EXECUTED_DEVELOPMENT_ONLY",
        "commit_outcome": outcome,
        "forbidden_commit_observed": False,
        "snapshot_binding_field": binding_field,
        "snapshot_digest_sha256": hashlib.sha256(binding_digest.encode()).hexdigest(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _role_change_schedule(db: Session) -> dict[str, object]:
    """Attempt a bound commit after an actual persisted delegate-role mutation."""

    started = time.perf_counter()
    scope, token = _delegated_scope_with_persisted_role(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="glhs-toctou-development",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    binding_digest, binding_field = _binding_digest(snapshot)
    proposal = _proposal_after_snapshot(db, scope, snapshot.snapshot_id, binding_digest)
    # This is a database mutation, followed by fresh scope resolution with a
    # refreshed normal-role token.  It is deliberately not an in-memory
    # ``ProfileScope`` replacement.
    scope.actor.role = "normal"
    db.flush()
    changed_scope = resolve_profile_scope(
        db,
        token,
        requested_profile=scope.profile.public_id,
        action="correct",
        data_class="medications",
        purpose="self_care",
    )
    if changed_scope.actor_role != "caregiver":
        raise AssertionError("toctou_persisted_role_change_not_resolved")
    try:
        apply_transition(
            db,
            scope=changed_scope,
            assertion=proposal,
            action="activate",
            expected_state_version=proposal.base_state_version,
            idempotency_key=f"toctou-role-change:{uuid4()}",
            transition_kind="glhs-toctou-development",
            reason_code="synthetic_role_coordinate_changed",
        )
    except GlhsInvariantError as exc:
        outcome = str(exc)
    else:  # pragma: no cover - a failed safety assertion
        raise AssertionError("role-changed proposal unexpectedly committed")
    if outcome != "proposal_snapshot_actor_role_mismatch":
        raise AssertionError(f"unexpected_role_rejection:{outcome}")
    ledger_observation = _sanitized_ledger_observation(
        db,
        profile_id=scope.profile.id,
        assertion_id=proposal.id,
        snapshot_id=snapshot.snapshot_id,
        transition_id=None,
    )
    if ledger_observation["transition_item_count"] != 0:
        raise AssertionError("rejected_role_commit_created_transition_item")
    return {
        "id": "TOCTOU-02",
        "run_status": "EXECUTED_DEVELOPMENT_ONLY",
        "commit_outcome": outcome,
        "forbidden_commit_observed": False,
        "governance_mutation": "persisted_delegate_account_role_doctor_to_normal",
        "coverage_note": "Persisted account-role mutation plus fresh Family-grant scope resolution; not a global policy-version writer.",
        "snapshot_binding_field": binding_field,
        "snapshot_digest_sha256": hashlib.sha256(binding_digest.encode()).hexdigest(),
        "transition_attempt": "apply_transition",
        "ledger_observation": ledger_observation,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _concurrent_consent_writer_vs_commit_schedule(engine: Engine) -> dict[str, object]:
    """Race a consent revocation with the commit of a pre-existing proposal.

    A commit whose completion order is not demonstrably before the revocation is
    classified indeterminate rather than safe. This development probe records
    no audit-completeness conclusion.
    """

    with Session(engine) as setup:
        scope = _scope(setup)
        setup.commit()
        snapshot = compile_thss(
            setup,
            scope=scope,
            task="glhs-toctou-development",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        binding_digest, binding_field = _binding_digest(snapshot)
        proposal = _proposal_after_snapshot(setup, scope, snapshot.snapshot_id, binding_digest)
        setup.commit()
        user_id, profile_id, assertion_id = scope.actor.id, scope.profile.id, proposal.id

    barrier = Barrier(2)
    mutex = Lock()
    observed: dict[str, object] = {}

    def writer() -> None:
        try:
            with Session(engine) as db:
                barrier.wait(timeout=10)
                db.add(
                    UserConsent(
                        user_id=user_id,
                        consent_type=MEDICAL_CONSENT_TYPE,
                        consent_version=required_medical_disclaimer_version(),
                        revoked_at=datetime.now(UTC),
                    )
                )
                db.commit()
                with mutex:
                    observed["revoke_commit_ns"] = time.monotonic_ns()
        except (BrokenBarrierError, RuntimeError, SQLAlchemyError) as exc:  # pragma: no cover
            with mutex:
                observed["writer_error"] = f"{type(exc).__name__}:{exc}"

    def commit_writer() -> None:
        try:
            with Session(engine) as db:
                scope = _existing_scope(db, user_id=user_id, profile_id=profile_id)
                proposal = db.get(GlhsAssertion, assertion_id)
                if proposal is None:
                    raise RuntimeError("toctou_prepared_proposal_missing")
                barrier.wait(timeout=10)
                with mutex:
                    observed["commit_start_ns"] = time.monotonic_ns()
                try:
                    transition = apply_transition(
                        db,
                        scope=scope,
                        assertion=proposal,
                        action="activate",
                        expected_state_version=proposal.base_state_version,
                        idempotency_key=f"toctou-concurrent-commit:{uuid4()}",
                        transition_kind="glhs-toctou-development",
                        reason_code="synthetic_concurrent_consent_revoke",
                    )
                    ledger_observation = _sanitized_ledger_observation(
                        db,
                        profile_id=scope.profile.id,
                        assertion_id=proposal.id,
                        snapshot_id=snapshot.snapshot_id,
                        transition_id=transition.public_id,
                    )
                    db.commit()
                    outcome = "transition_committed"
                except GlhsInvariantError as exc:
                    db.rollback()
                    outcome = str(exc)
                    ledger_observation = {"reconstruction_status": "not_committed"}
                with mutex:
                    observed["commit_outcome"] = outcome
                    observed["commit_complete_ns"] = time.monotonic_ns()
                    observed["ledger_observation"] = ledger_observation
        except (BrokenBarrierError, RuntimeError, SQLAlchemyError) as exc:  # pragma: no cover
            with mutex:
                observed["commit_error"] = f"{type(exc).__name__}:{exc}"

    started = time.perf_counter()
    left, right = Thread(target=writer), Thread(target=commit_writer)
    left.start()
    right.start()
    left.join(timeout=20)
    right.join(timeout=20)
    if left.is_alive() or right.is_alive():
        raise RuntimeError("toctou_concurrent_workers_timed_out")
    if "writer_error" in observed or "commit_error" in observed:
        raise RuntimeError(f"toctou_concurrent_worker_error:{observed}")
    outcome = observed.get("commit_outcome")
    if not isinstance(outcome, str):
        raise TypeError("toctou_concurrent_commit_outcome_missing")
    revoke_commit_ns = observed.get("revoke_commit_ns")
    commit_start_ns = observed.get("commit_start_ns")
    commit_complete_ns = observed.get("commit_complete_ns")
    classification, forbidden_commit_observed = _classify_concurrent_commit_order(
        outcome=outcome,
        revoke_commit_ns=revoke_commit_ns,
        commit_start_ns=commit_start_ns,
        commit_complete_ns=commit_complete_ns,
    )
    return {
        "id": "TOCTOU-03",
        "run_status": "EXECUTED_DEVELOPMENT_ONLY",
        "commit_outcome": outcome,
        "ordering_classification": classification,
        "forbidden_commit_observed": forbidden_commit_observed,
        "snapshot_binding_field": binding_field,
        "snapshot_digest_sha256": hashlib.sha256(binding_digest.encode()).hexdigest(),
        "revoke_commit_ns": revoke_commit_ns,
        "commit_start_ns": commit_start_ns,
        "commit_complete_ns": commit_complete_ns,
        "transition_attempt": "apply_transition",
        "ledger_observation": observed.get("ledger_observation"),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _concurrent_consent_writer_schedule(engine: Engine) -> dict[str, object]:
    """Race a consent revocation and a proposal without imposing an order.

    The result intentionally distinguishes a rejected proposal from a commit
    whose validation/commit order is not observable by this development probe.
    It does not call an indeterminate ordering safe.
    """

    with Session(engine) as setup:
        scope = _scope(setup)
        setup.commit()
        snapshot = compile_thss(
            setup,
            scope=scope,
            task="glhs-toctou-development",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        binding_digest, binding_field = _binding_digest(snapshot)
        setup.commit()
        user_id, profile_id = scope.actor.id, scope.profile.id

    barrier = Barrier(2)
    mutex = Lock()
    observed: dict[str, object] = {}

    def writer() -> None:
        try:
            with Session(engine) as db:
                barrier.wait(timeout=10)
                db.add(
                    UserConsent(
                        user_id=user_id,
                        consent_type=MEDICAL_CONSENT_TYPE,
                        consent_version=required_medical_disclaimer_version(),
                        revoked_at=datetime.now(UTC),
                    )
                )
                db.commit()
                with mutex:
                    observed["revoke_commit_ns"] = time.time_ns()
        except (BrokenBarrierError, RuntimeError, SQLAlchemyError) as exc:  # pragma: no cover
            with mutex:
                observed["writer_error"] = f"{type(exc).__name__}:{exc}"

    def proposal_writer() -> None:
        try:
            with Session(engine) as db:
                scope = _existing_scope(db, user_id=user_id, profile_id=profile_id)
                barrier.wait(timeout=10)
                try:
                    _proposal_after_snapshot(db, scope, snapshot.snapshot_id, binding_digest)
                    db.commit()
                    outcome = "proposal_committed"
                except GlhsInvariantError as exc:
                    db.rollback()
                    outcome = str(exc)
                with mutex:
                    observed["proposal_outcome"] = outcome
                    observed["proposal_complete_ns"] = time.time_ns()
        except (BrokenBarrierError, RuntimeError, SQLAlchemyError) as exc:  # pragma: no cover
            with mutex:
                observed["proposal_error"] = f"{type(exc).__name__}:{exc}"

    started = time.perf_counter()
    left, right = Thread(target=writer), Thread(target=proposal_writer)
    left.start()
    right.start()
    left.join(timeout=20)
    right.join(timeout=20)
    if left.is_alive() or right.is_alive():
        raise RuntimeError("toctou_concurrent_workers_timed_out")
    if "writer_error" in observed or "proposal_error" in observed:
        raise RuntimeError(f"toctou_concurrent_worker_error:{observed}")
    outcome = observed.get("proposal_outcome")
    if not isinstance(outcome, str):
        raise TypeError("toctou_concurrent_proposal_outcome_missing")
    revoke_commit_ns = observed.get("revoke_commit_ns")
    proposal_complete_ns = observed.get("proposal_complete_ns")
    if outcome != "proposal_committed":
        classification = "rejected_after_or_during_governance_race"
        forbidden_commit_observed: bool | None = False
    elif (
        isinstance(revoke_commit_ns, int)
        and isinstance(proposal_complete_ns, int)
        and proposal_complete_ns < revoke_commit_ns
    ):
        classification = "proposal_committed_before_observed_revoke_commit"
        forbidden_commit_observed = False
    else:
        classification = "indeterminate_ordering_proposal_committed"
        forbidden_commit_observed = None
    return {
        "id": "TOCTOU-05",
        "run_status": "EXECUTED_DEVELOPMENT_ONLY",
        "commit_outcome": outcome,
        "ordering_classification": classification,
        "forbidden_commit_observed": forbidden_commit_observed,
        "snapshot_binding_field": binding_field,
        "snapshot_digest_sha256": hashlib.sha256(binding_digest.encode()).hexdigest(),
        "revoke_commit_ns": revoke_commit_ns,
        "proposal_complete_ns": proposal_complete_ns,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run() -> dict[str, object]:
    url = _require_isolated_postgres()
    schema = _schema_name()
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = _engine(url, schema)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            scope = _scope(db)
            db.commit()
            consent = _consent_revoke_schedule(db, scope)
            db.rollback()
            # Fresh synthetic subjects prevent prior governance mutations from
            # influencing independent development schedules.
            role = _role_change_schedule(db)
            db.rollback()
            scope = _scope(db)
            db.commit()
            policy = _policy_change_schedule(db, scope)
            db.rollback()
        concurrent_commit = _concurrent_consent_writer_vs_commit_schedule(engine)
        concurrent = _concurrent_consent_writer_schedule(engine)
        return {
            "schema_version": "glhs-postgres-toctou-development-v1",
            "status": "development_probe_not_headline",
            "backend": "isolated_postgresql_random_schema",
            "schema_retained": False,
            "isolation_level": "database_default; profile lock semantics are not a final concurrency result",
            "executed_schedules": [consent, role, concurrent_commit, policy, concurrent],
            "not_run_schedule_ids": [],
            "note": "No final frozen manifest, persisted role-policy-writer schedule, audit-completeness result, or clinical claim is produced. A committed concurrent proposal is indeterminate unless a final observer establishes validation/commit ordering.",
        }
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()


def main() -> int:
    output = Path(os.environ["GLHS_TOCTOU_OUTPUT"])
    result = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
