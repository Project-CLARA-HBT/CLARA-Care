"""Synthetic GovRed HTTP probes, mounted only in an isolated RIVF process.

This route deliberately never exists in a normal API process.  It accepts no
clinical payload and creates only a fresh synthetic sentinel source/evidence
chain before exercising the ordinary profile-scope and GST admission path.
It is a development adapter primitive, not a benchmark executor or result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    ensure_medical_disclaimer_consent,
    required_medical_disclaimer_version,
)
from clara_api.core.govred_research import isolated_govred_arm
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import HealthSourceReference, UserConsent
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
from clara_api.lifemap.profile_scope import resolve_profile_scope

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SyntheticCommitProbeRequest(_Strict):
    """One deliberately narrow mutation for isolated development probes."""

    mutation: Literal["none", "consent_revoke"]
    sentinel_id: str = Field(min_length=8, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")


def _require_research_arm():
    arm = isolated_govred_arm()
    if arm is None:
        # The router normally is not mounted in this state.  Retain this guard
        # for direct invocation and any future router-composition change.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    return arm


def _raise_invariant(exc: GlhsInvariantError) -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": str(exc)}) from exc


@router.post("/synthetic-commit-probe", status_code=status.HTTP_201_CREATED)
def synthetic_commit_probe(
    request: SyntheticCommitProbeRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    """Exercise authenticated synthetic disclosure → mutation → GST commit.

    This does not expose a generic assertion-write API: all generated values
    are fixed synthetic metadata and only the two prespecified mutation modes
    are accepted.
    """

    arm = _require_research_arm()
    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=None,
        action="create",
        data_class="medications",
        purpose="self_care",
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    now = datetime.now(UTC)
    probe_id = uuid4().hex
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="govred-isolated-synthetic",
        source_identity=f"sentinel:{request.sentinel_id}:{probe_id}",
        checksum=f"sentinel:{request.sentinel_id}:{probe_id}",
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
            artifact_public_id=f"sentinel:{request.sentinel_id}:{probe_id}",
            fingerprint=f"sentinel:{request.sentinel_id}:{probe_id}",
            valid_from=now,
        ),
    )
    snapshot_id = None
    snapshot_digest = None
    if arm.bind_snapshot:
        snapshot = compile_thss(
            db,
            scope=scope,
            task="govred-isolated-synthetic-probe",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        snapshot_id = snapshot.snapshot_id
        snapshot_digest = snapshot.manifest_digest
    proposal = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:govred-sentinel:{request.sentinel_id}:{probe_id}",
            assertion_type="medications",
            predicate="synthetic_probe",
            value={"sentinel_id": request.sentinel_id, "synthetic": True},
            epistemic_state="reported",
            valid_from=now,
            source_snapshot_id=snapshot_id,
            source_snapshot_digest=snapshot_digest,
            proposal_consumed_thss=arm.bind_snapshot,
        ),
        evidence=((evidence, "supports"),),
    )
    if request.mutation == "consent_revoke":
        db.add(UserConsent(
            user_id=scope.profile.user_id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
            revoked_at=datetime.now(UTC),
        ))
        db.flush()
    try:
        transition = apply_transition(
            db,
            scope=scope,
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
    return {
        "arm": arm.name,
        "mutation": request.mutation,
        "outcome": "transition_committed",
        "transition_id": transition.public_id,
        "resulting_state_version": transition.resulting_state_version,
    }
