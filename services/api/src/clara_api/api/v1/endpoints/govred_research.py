"""Synthetic GovRed HTTP probes, mounted only in an isolated RIVF process.

This route deliberately never exists in a normal API process.  It accepts no
clinical payload and creates only a fresh synthetic sentinel source/evidence
chain before exercising the ordinary profile-scope and GST admission path.
It is a development adapter primitive, not a benchmark executor or result.

Two-phase schedules: the create phase persists a synthetic proposal (and a
short-lived snapshot for snapshot-binding arms) and returns its coordinates;
the commit phase loads the same proposal and applies the ordinary admission
path.  This lets the driver place real time passage or a deployment-level
policy update between disclosure and commit without touching any admission
check.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    ensure_medical_disclaimer_consent,
    required_medical_disclaimer_version,
)
from clara_api.core.govred_research import GovredResearchArm, isolated_govred_arm
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    FamilyAccessGrant,
    GlhsAssertion,
    GlhsSnapshotManifest,
    GlhsTransitionItem,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import get_db
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SyntheticCommitProbeRequest(_Strict):
    """One deliberately narrow mutation for isolated development probes."""

    mutation: Literal[
        "none",
        "consent_revoke",
        "state_advance",
        "policy_version_change",
        "subject_cross_replay",
        "snapshot_digest_invalid",
        "snapshot_expired",
        "actor_switch_replay",
        "concurrent_governance_writer",
    ]
    sentinel_id: str = Field(min_length=8, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    phase: Literal["full", "create", "commit"] = "full"
    probe_id: str | None = None
    snapshot_expires_in_seconds: int = Field(default=300, ge=1, le=86400)
    concurrent_revoke_delay_ms: int = Field(default=5, ge=0, le=1000)


@router.get("/arm")
def synthetic_arm_report(
    token: TokenPayload = USER,
) -> dict[str, object]:
    """Report the selected isolated arm semantics for adapter verification."""

    arm = isolated_govred_arm()
    if arm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    return {
        "arm": arm.name,
        "bind_snapshot": arm.bind_snapshot,
        "revalidate_state": arm.revalidate_state,
        "revalidate_governance": arm.revalidate_governance,
    }


def _require_research_arm():
    arm = isolated_govred_arm()
    if arm is None:
        # The router normally is not mounted in this state.  Retain this guard
        # for direct invocation and any future router-composition change.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    return arm


def _raise_invariant(exc: GlhsInvariantError) -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": str(exc)}) from exc


def _scope(db: Session, token: TokenPayload) -> ProfileScope:
    return resolve_profile_scope(
        db,
        token,
        requested_profile=None,
        action="create",
        data_class="medications",
        purpose="self_care",
    )


def _proposal_semantic_key(*, sentinel_id: str, probe_id: str, label: str) -> str:
    return f"medication:govred-sentinel:{sentinel_id}:{probe_id}:{label}"


@dataclass(frozen=True)
class _MutationContext:
    commit_scope: ProfileScope
    concurrent_revoke: dict[str, object] | None


def _build_proposal(
    db: Session,
    *,
    scope: ProfileScope,
    arm: GovredResearchArm,
    sentinel_id: str,
    probe_id: str,
    label: str,
    snapshot_expires_in_seconds: int,
) -> tuple[GlhsAssertion, GlhsSnapshotManifest | None]:
    """Create one synthetic sentinel proposal through the ordinary gateway."""

    now = datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="govred-isolated-synthetic",
        source_identity=f"sentinel:{sentinel_id}:{probe_id}:{label}",
        checksum=f"sentinel:{sentinel_id}:{probe_id}:{label}",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="govred-isolated-synthetic",
            artifact_type="synthetic_sentinel",
            artifact_public_id=f"sentinel:{sentinel_id}:{probe_id}:{label}",
            fingerprint=f"sentinel:{sentinel_id}:{probe_id}:{label}",
            valid_from=now,
        ),
    )
    snapshot_id = None
    snapshot_digest = None
    snapshot_row = None
    if arm.bind_snapshot:
        snapshot = compile_thss(
            db,
            scope=scope,
            task="govred-isolated-synthetic-probe",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
            expires_in=timedelta(seconds=snapshot_expires_in_seconds),
        )
        snapshot_id = snapshot.snapshot_id
        snapshot_digest = snapshot.manifest_digest
        snapshot_row = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.profile_id == scope.profile.id,
                GlhsSnapshotManifest.public_id == snapshot.snapshot_id,
            )
        ).scalar_one()
    proposal = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=_proposal_semantic_key(
                sentinel_id=sentinel_id, probe_id=probe_id, label=label
            ),
            assertion_type="medications",
            predicate="synthetic_probe",
            value={"sentinel_id": sentinel_id, "synthetic": True, "label": label},
            epistemic_state="reported",
            valid_from=now,
            source_snapshot_id=snapshot_id,
            source_snapshot_digest=snapshot_digest,
            proposal_consumed_thss=arm.bind_snapshot,
        ),
        evidence=((evidence, "supports"),),
    )
    return proposal, snapshot_row


def _apply_mutations(
    db: Session,
    *,
    scope: ProfileScope,
    arm: GovredResearchArm,
    request: SyntheticCommitProbeRequest,
    proposal,
    probe_id: str,
) -> _MutationContext:
    """Apply the prespecified synthetic governance mutations before admission.

    Only synthetic rows created by this route are touched.  Direct SQL is used
    solely to *attempt* canonical-row corruption; the database immutability
    trigger is expected to reject it, which is itself the observed invariant
    for the digest-tampering family.
    """

    if request.mutation == "state_advance":
        advancing_proposal, _ = _build_proposal(
            db,
            scope=scope,
            arm=arm,
            sentinel_id=request.sentinel_id,
            probe_id=probe_id,
            label="advance",
            snapshot_expires_in_seconds=300,
        )
        try:
            apply_transition(
                db,
                scope=scope,
                assertion=advancing_proposal,
                action="activate",
                expected_state_version=advancing_proposal.base_state_version,
                idempotency_key=f"govred-synthetic:{request.sentinel_id}:{probe_id}:advance",
                transition_kind="govred_isolated_synthetic",
                reason_code="state_advance_precondition",
            )
            # Persist the preceding transition independently.  A rejection of
            # the target must not erase the state change it is testing.
            db.commit()
        except GlhsInvariantError as exc:
            db.rollback()
            _raise_invariant(exc)
    if request.mutation == "consent_revoke":
        db.add(UserConsent(
            user_id=scope.profile.user_id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            revoked_at=datetime.now(UTC),
        ))
        db.flush()
    if request.mutation == "snapshot_digest_invalid":
        if not arm.bind_snapshot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "mutation_not_applicable_to_arm"},
            )
        snapshot_row = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.profile_id == scope.profile.id,
                GlhsSnapshotManifest.public_id == proposal.source_snapshot_id,
            )
        ).scalar_one()
        try:
            with db.begin_nested():
                db.execute(
                    text(
                        "UPDATE glhs_snapshot_manifests SET manifest_digest = :digest "
                        "WHERE id = :row_id"
                    ),
                    {"digest": "0" * 64, "row_id": snapshot_row.id},
                )
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "ledger_tampering_rejected"},
            ) from exc
        db.expire(snapshot_row)
    if request.mutation == "snapshot_expired":
        if request.phase == "full":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "mutation_requires_two_phase"},
            )
        if not arm.bind_snapshot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "mutation_not_applicable_to_arm"},
            )
        if request.phase == "commit":
            snapshot_row = db.execute(
                select(GlhsSnapshotManifest).where(
                    GlhsSnapshotManifest.profile_id == scope.profile.id,
                    GlhsSnapshotManifest.public_id == proposal.source_snapshot_id,
                )
            ).scalar_one()
            if snapshot_row.expires_at and _as_utc(snapshot_row.expires_at) > datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "snapshot_not_yet_expired"},
                )
    if request.mutation == "policy_version_change" and request.phase == "full":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "mutation_requires_two_phase"},
        )
    commit_scope = scope
    if request.mutation == "subject_cross_replay":
        cross_user = User(
            email=f"govred-cross-{probe_id}@example.test",
            hashed_password="synthetic",
            role="normal",
        )
        db.add(cross_user)
        db.flush()
        cross_profile = PhrProfile(user_id=cross_user.id)
        db.add(cross_profile)
        db.flush()
        commit_scope = resolve_profile_scope(
            db,
            TokenPayload({"sub": cross_user.email, "role": "normal"}),
            requested_profile=str(cross_profile.public_id),
            action="create",
            data_class="medications",
            purpose="self_care",
        )
    if request.mutation == "actor_switch_replay":
        delegate = User(
            email=f"govred-delegate-{probe_id}@example.test",
            hashed_password="synthetic",
            role="normal",
        )
        db.add(delegate)
        db.flush()
        db.add(FamilyAccessGrant(
            profile_id=scope.profile.id,
            grantor_user_id=scope.profile.user_id,
            grantee_user_id=delegate.id,
            object_type="profile",
            object_id="*",
            purpose="self_care",
            status="active",
            starts_at=datetime.now(UTC) - timedelta(minutes=1),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            allowed_actions_json=["view", "create"],
            data_classes_json=["medications"],
        ))
        db.flush()
        commit_scope = resolve_profile_scope(
            db,
            TokenPayload({"sub": delegate.email, "role": "normal"}),
            requested_profile=str(scope.profile.public_id),
            action="create",
            data_class="medications",
            purpose="self_care",
        )
    concurrent_revoke = None
    if request.mutation == "concurrent_governance_writer":
        if db.get_bind().dialect.name != "postgresql":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "mutation_requires_postgres"},
            )
        revoke_state: dict[str, object] = {}
        # Capture the coordinate before the thread starts: the main session may
        # expire attributes at its own commit boundaries and must never be
        # touched from the writer thread.
        revoke_owner_user_id = scope.profile.user_id
        revoke_consent_version = required_medical_disclaimer_version()

        def _revoke_writer() -> None:
            time.sleep(request.concurrent_revoke_delay_ms / 1000)
            from clara_api.db.session import SessionLocal

            session = SessionLocal()
            try:
                session.add(UserConsent(
                    user_id=revoke_owner_user_id,
                    consent_type=MEDICAL_CONSENT_TYPE,
                    consent_version=revoke_consent_version,
                    revoked_at=datetime.now(UTC),
                ))
                session.commit()
                revoke_state["monotonic"] = time.monotonic()
            finally:
                session.close()

        writer = threading.Thread(target=_revoke_writer)
        writer.start()
        concurrent_revoke = revoke_state
    return _MutationContext(
        commit_scope=commit_scope,
        concurrent_revoke=concurrent_revoke,
    )


def _commit(
    db: Session,
    *,
    commit_scope: ProfileScope,
    proposal,
    request: SyntheticCommitProbeRequest,
    probe_id: str,
    concurrent_revoke: dict[str, object] | None,
) -> dict[str, object]:
    try:
        transition = apply_transition(
            db,
            scope=commit_scope,
            assertion=proposal,
            action="activate",
            expected_state_version=proposal.base_state_version,
            idempotency_key=f"govred-synthetic:{request.sentinel_id}:{probe_id}",
            transition_kind="govred_isolated_synthetic",
            reason_code=request.mutation,
        )
        db.commit()
    except GlhsInvariantError as exc:
        db.rollback()
        _raise_invariant(exc)
    if concurrent_revoke is not None:
        # The writer thread has either committed by now or is imminent; join
        # with a bounded wait so the observation records its outcome without
        # extending the admission transaction itself.
        for _ in range(200):
            if "monotonic" in concurrent_revoke:
                break
            time.sleep(0.01)
    transition_items = 0
    snapshot_linked = False
    if transition is not None and transition.id is not None:
        transition_items = len(
            list(
                db.execute(
                    select(GlhsTransitionItem.id).where(
                        GlhsTransitionItem.transition_id == transition.id
                    )
                ).scalars()
            )
        )
        snapshot_linked = transition.source_snapshot_id is not None
    outcome = "transition_committed"
    if request.mutation == "concurrent_governance_writer" and "monotonic" in (
        concurrent_revoke or {}
    ):
        outcome = "indeterminate_ordering_transition_committed"
    return {
        "outcome": outcome,
        "transition_id": transition.public_id,
        "resulting_state_version": transition.resulting_state_version,
        "audit_observation": {
            "transition_items": transition_items,
            "snapshot_linked": snapshot_linked,
            "governance_writer_committed": bool(
                concurrent_revoke is not None and "monotonic" in concurrent_revoke
            ),
        },
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.post("/synthetic-commit-probe", status_code=status.HTTP_201_CREATED)
def synthetic_commit_probe(
    request: SyntheticCommitProbeRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    """Exercise authenticated synthetic disclosure → mutation → GST commit.

    This does not expose a generic assertion-write API: all generated values
    are fixed synthetic metadata and only the prespecified mutation modes and
    phases are accepted.  ``create`` persists a synthetic proposal (and a
    short-lived snapshot for binding arms); ``commit`` loads the same proposal
    and runs the ordinary admission path, so the driver can schedule real time
    passage or a deployment-level policy update between the two.
    ``state_advance`` commits a separate synthetic transition before the target
    so it exercises a real stale-state check.  ``snapshot_digest_invalid``
    attempts direct-SQL corruption of a synthetic snapshot manifest; the
    persistence layer's immutability trigger is the invariant under test.
    """

    arm = _require_research_arm()
    scope = _scope(db, token)
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    probe_id = request.probe_id or uuid4().hex
    if request.phase == "create":
        proposal, snapshot_row = _build_proposal(
            db,
            scope=scope,
            arm=arm,
            sentinel_id=request.sentinel_id,
            probe_id=probe_id,
            label="target",
            snapshot_expires_in_seconds=request.snapshot_expires_in_seconds,
        )
        db.commit()
        return {
            "arm": arm.name,
            "phase": "create",
            "probe_id": probe_id,
            "proposal_public_id": proposal.public_id,
            "semantic_key": _proposal_semantic_key(
                sentinel_id=request.sentinel_id, probe_id=probe_id, label="target"
            ),
            "snapshot_public_id": snapshot_row.public_id if snapshot_row else None,
            "snapshot_expires_at": (
                snapshot_row.expires_at.isoformat() if snapshot_row else None
            ),
            "snapshot_expires_in_seconds": request.snapshot_expires_in_seconds,
        }

    semantic_key = _proposal_semantic_key(
        sentinel_id=request.sentinel_id, probe_id=probe_id, label="target"
    )
    if request.phase == "commit":
        existing_proposal = db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.semantic_key == semantic_key,
            )
        ).scalar_one_or_none()
        if existing_proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "proposal_not_found"},
            )
        proposal = existing_proposal
    else:
        proposal, _ = _build_proposal(
            db,
            scope=scope,
            arm=arm,
            sentinel_id=request.sentinel_id,
            probe_id=probe_id,
            label="target",
            snapshot_expires_in_seconds=request.snapshot_expires_in_seconds,
        )
    mutated = _apply_mutations(
        db, scope=scope, arm=arm, request=request, proposal=proposal, probe_id=probe_id
    )
    committed = _commit(
        db,
        commit_scope=mutated.commit_scope,
        proposal=proposal,
        request=request,
        probe_id=probe_id,
        concurrent_revoke=mutated.concurrent_revoke,
    )
    return {
        "arm": arm.name,
        "phase": request.phase,
        "probe_id": probe_id,
        **committed,
    }
