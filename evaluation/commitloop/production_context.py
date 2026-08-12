"""Build a benchmark context through the real API-owned commitment THSS path.

The adapter is deliberately isolated to an in-memory database.  It does not
replace production persistence or claim an HTTP end-to-end measurement; it
executes the same GST, snapshot binding, bitemporal reconstruction and THSS
compiler used by production commitment adapters.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import EvidenceInput, record_evidence
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from evaluation.commitloop.oracle import compile_construction_gold
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent


def _opaque(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def compile_production_commitment_context(
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    *,
    valid_cutoff: datetime,
    known_cutoff: datetime,
) -> dict[str, Any]:
    """Return a strict THSS payload built by production GLHS code.

    The returned value is safe to use as one comparative arm's context.  It
    carries ``production_path`` evidence so a runner can fail closed when an
    alleged GLHS+THSS arm instead receives a hand-built packet.
    """

    if case.target is None:
        raise ValueError("production_context_target_required")
    gold = compile_construction_gold(
        case, events, valid_cutoff=valid_cutoff, known_cutoff=known_cutoff
    )
    if gold.get("status") != "SCORABLE":
        raise ValueError("production_context_gold_not_scorable")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            token = _opaque(case.case_id)
            owner = User(
                email=f"glhs-bench-{token}@example.invalid",
                hashed_password="non-login-benchmark-fixture",
                role="normal",
            )
            db.add(owner)
            db.flush()
            profile = PhrProfile(user_id=owner.id)
            db.add(profile)
            db.flush()
            scope = ProfileScope(
                actor=owner,
                profile=profile,
                actor_role="owner",
                purpose="self_care",
                allowed_actions=frozenset({"create", "correct", "view"}),
                allowed_data_classes=frozenset({"observations"}),
            )
            anchor = next(
                (item for item in events if item.evidence_id == case.anchor_evidence_id),
                None,
            )
            if anchor is None or anchor.valid_at is None:
                raise ValueError("production_context_anchor_missing")
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="glhs_bench_synthetic_fixture",
                source_identity=f"case:{token}",
                checksum=f"sha256:{_opaque(case.anchor_evidence_id)}",
                observed_at=anchor.known_at,
            )
            db.add(source)
            db.flush()
            evidence = record_evidence(
                db,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="structured_fixture",
                    artifact_type="commitloop_timeline_event",
                    artifact_public_id=anchor.evidence_id,
                    fingerprint=_opaque(anchor.evidence_id),
                    valid_from=anchor.valid_at,
                ),
            )
            initial = compile_commitment_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                valid_at=valid_cutoff,
                known_at=known_cutoff,
                allowed_domains=frozenset({"observations"}),
                strict=True,
                disclosed_evidence=(evidence,),
            )
            commitment = get_or_create_commitment(
                db,
                scope=scope,
                semantic_key=f"observation:{case.target['system']}:{case.target['code']}",
                domain="observations",
                supersession_key=f"observation:{case.target['system']}:{case.target['code']}",
            )
            proposal = propose_bound_commitment_transition(
                db,
                scope=scope,
                commitment=commitment,
                observed_evidence=(evidence,),
                proposed_transition="OPEN",
                origin="user",
                observed_base_state_version=initial.state_version,
                task=initial.task,
                source_snapshot_id=initial.snapshot_id,
                source_snapshot_digest=initial.manifest_digest,
            )
            apply_commitment_transition(
                db,
                scope=scope,
                commitment=commitment,
                proposal=proposal,
                evidence=(evidence,),
                data=CommitmentVersionInput(
                    action=case.action,
                    target=case.target,
                    anchor_valid_time=case.anchor_valid_time or anchor.valid_at,
                    anchor_known_time=case.anchor_known_time,
                    # The synthetic fixture represents a structured, verified
                    # observation for policy validation; its synthetic status
                    # remains explicit in the source reference and artifact.
                    authority_class="lab_verified",
                    lifecycle_state="OPEN",
                    evidence_state="CLEAR",
                    timeliness_state="UNKNOWN",
                    earliest_valid_time=case.anchor_valid_time,
                    due_time=case.due_time,
                    grace_end=None,
                    fulfillment_predicate=case.fulfillment_predicate,
                ),
                expected_state_version=initial.state_version,
                idempotency_key=f"glhs-bench:{token}:open",
                transition_kind="commitment_opened",
                reason_code="deterministic_synthetic_anchor",
            )
            desired_lifecycle = str(gold["lifecycle_state"])
            if desired_lifecycle != "OPEN":
                current = compile_commitment_thss(
                    db,
                    scope=scope,
                    task="reconcile_future_oriented_commitment",
                    purpose=scope.purpose,
                    valid_at=valid_cutoff,
                    known_at=known_cutoff,
                    allowed_domains=frozenset({"observations"}),
                    strict=True,
                    disclosed_evidence=(evidence,),
                )
                correction = propose_bound_commitment_transition(
                    db,
                    scope=scope,
                    commitment=commitment,
                    observed_evidence=(evidence,),
                    proposed_transition=desired_lifecycle,
                    origin="user",
                    observed_base_state_version=current.state_version,
                    task=current.task,
                    source_snapshot_id=current.snapshot_id,
                    source_snapshot_digest=current.manifest_digest,
                )
                apply_commitment_transition(
                    db,
                    scope=scope,
                    commitment=commitment,
                    proposal=correction,
                    evidence=(evidence,),
                    data=CommitmentVersionInput(
                        action=case.action,
                        target=case.target,
                        anchor_valid_time=case.anchor_valid_time or anchor.valid_at,
                        anchor_known_time=case.anchor_known_time,
                        authority_class="lab_verified",
                        lifecycle_state=desired_lifecycle,
                        evidence_state=str(gold["evidence_state"]),
                        timeliness_state=str(gold["timeliness_state"]),
                        earliest_valid_time=case.anchor_valid_time,
                        due_time=case.due_time,
                        grace_end=None,
                        fulfillment_predicate=case.fulfillment_predicate,
                    ),
                    expected_state_version=current.state_version,
                    idempotency_key=f"glhs-bench:{token}:reconcile",
                    transition_kind="commitment_reconciled",
                    reason_code="deterministic_synthetic_oracle",
                )
            final = compile_commitment_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                valid_at=valid_cutoff,
                known_at=known_cutoff,
                allowed_domains=frozenset({"observations"}),
                strict=True,
                disclosed_evidence=(evidence,),
            )
            manifest = db.execute(
                select(GlhsSnapshotManifest).where(
                    GlhsSnapshotManifest.public_id == final.snapshot_id
                )
            ).scalar_one()
            payload = dict(manifest.snapshot_payload_json)
            payload["production_path"] = {
                "component": "api_owned_gst_commitment_thss",
                "snapshot_id": final.snapshot_id,
                "manifest_digest": final.manifest_digest,
                "state_version": final.state_version,
                "pipeline": [stage["name"] for stage in final.pipeline_trace],
            }
            db.rollback()
            return payload
    finally:
        engine.dispose()
