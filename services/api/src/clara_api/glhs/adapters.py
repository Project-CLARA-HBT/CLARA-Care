"""Narrow adapters from existing health modules into the GLHS trusted ledger.

Adapters are intentionally API-owned and receive already-authorized objects.
They do not attempt to infer clinical semantics from free text, and they never
raise an existing draft to confirmed status.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsAssertion,
    GlhsAssertionEvidence,
    GlhsEvidence,
    HealthSourceReference,
    LifeMapEvent,
    LifeMapEventRevision,
    MedicationCourse,
    PhrObservation,
    User,
    VisitDocument,
    WearableObservation,
)
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    current_state_version,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rebase_same_transaction_proposal(
    db: Session, *, scope: ProfileScope, assertion: GlhsAssertion
) -> GlhsAssertion:
    """Append a replacement candidate after serialized same-transaction writes.

    The candidate was created against the state version that existed before the
    adapter retired the prior assertion(s).  Those deliberate transitions are
    part of this same trusted transaction. The original candidate remains an
    immutable rejected projection and a newly appended candidate is bound to
    the resulting version. External stale proposals remain rejected.
    """

    current = current_state_version(db, profile_id=scope.profile.id)
    if assertion.base_state_version == current:
        return assertion
    evidence = tuple(
        (row, str(relation))
        for row, relation in db.execute(
            select(GlhsEvidence, GlhsAssertionEvidence.relation)
            .join(
                GlhsAssertionEvidence,
                GlhsAssertionEvidence.evidence_id == GlhsEvidence.id,
            )
            .where(GlhsAssertionEvidence.assertion_id == assertion.id)
        ).all()
    )
    replacement = propose_assertion(
        db,
        profile_id=assertion.profile_id,
        actor_user_id=assertion.asserted_by_user_id,
        data=AssertionInput(
            semantic_key=assertion.semantic_key,
            assertion_type=assertion.assertion_type,
            predicate=assertion.predicate,
            value=assertion.value_json,
            epistemic_state=assertion.epistemic_state,
            valid_from=assertion.valid_from,
            valid_to=assertion.valid_to,
            time_precision=assertion.time_precision,
            estimated_time=assertion.estimated_time,
            subject_kind=assertion.subject_kind,
            process_kind=assertion.process_kind,
            source_snapshot_id=assertion.source_snapshot_id,
            source_snapshot_digest=assertion.source_snapshot_digest,
        ),
        evidence=evidence,
    )
    assertion.lifecycle_status = "rejected"
    db.add(assertion)
    db.flush()
    return cast(GlhsAssertion, replacement)


def _event_source(
    db: Session,
    *,
    scope: ProfileScope,
    event: LifeMapEvent,
    revision: LifeMapEventRevision,
) -> HealthSourceReference:
    # A revision may already carry a user-revocable source reference (for
    # example an imported document).  Reuse it so withdrawing that source
    # invalidates the exact evidence bound to the governed assertion.  Older
    # native events have no source reference; they retain a deterministic
    # adapter-owned reference solely for provenance.
    if revision.source_reference_id is not None:
        referenced = db.get(HealthSourceReference, revision.source_reference_id)
        if referenced is not None and referenced.profile_id == scope.profile.id:
            return cast(HealthSourceReference, referenced)
    source_identity = f"lifemap:{event.public_id}:revision:{revision.public_id}"
    existing = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(HealthSourceReference, existing)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind=event.source_kind,
        source_identity=source_identity,
        author_type=scope.actor_role,
        author_public_id=str(scope.actor.id),
        checksum=_fingerprint(
            {
                "event": event.public_id,
                "revision": revision.public_id,
                "payload": revision.payload_json,
                "occurred_at": event.occurred_at,
            }
        ),
        observed_at=event.occurred_at,
    )
    db.add(source)
    db.flush()
    return source


def retire_lifemap_source_assertions(
    db: Session,
    *,
    scope: ProfileScope,
    source_reference_id: int,
    idempotency_key: str,
) -> int:
    """Retire every active LifeMap assertion supported by a withdrawn source.

    The source-revocation record remains the immutable legal/audit event; this
    function writes the corresponding governed-state transitions.  The
    semantic-key branch covers assertions created before LifeMap reused the
    revision's source reference, while the evidence branch is the normal
    current path.  No data are deleted or rewritten.
    """

    revision_event_ids = tuple(
        db.execute(
            select(LifeMapEvent.public_id)
            .join(LifeMapEventRevision, LifeMapEventRevision.event_id == LifeMapEvent.id)
            .where(
                LifeMapEventRevision.profile_id == scope.profile.id,
                LifeMapEventRevision.source_reference_id == source_reference_id,
            )
        ).scalars()
    )
    semantic_keys = {f"lifemap_event:{event_id}" for event_id in revision_event_ids}
    evidence_assertion_ids = tuple(
        db.execute(
            select(GlhsAssertionEvidence.assertion_id)
            .join(GlhsEvidence, GlhsEvidence.id == GlhsAssertionEvidence.evidence_id)
            .where(
                GlhsEvidence.profile_id == scope.profile.id,
                GlhsEvidence.source_reference_id == source_reference_id,
            )
        ).scalars()
    )
    if not semantic_keys and not evidence_assertion_ids:
        return 0
    predicates = [GlhsAssertion.id.in_(evidence_assertion_ids)] if evidence_assertion_ids else []
    if semantic_keys:
        predicates.append(GlhsAssertion.semantic_key.in_(semantic_keys))
    active = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.lifecycle_status == "active",
                GlhsAssertion.assertion_type == "lifemap",
                *([or_(*predicates)] if predicates else []),
            )
        ).scalars()
    )
    for index, assertion in enumerate(active):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="supersede",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"glhs-lifemap-source-revoke:{idempotency_key}:{index}",
            transition_kind="lifemap_source_revoked",
            reason_code="source_revoked",
            effective_at=datetime.now(UTC),
        )
    return len(active)


def ingest_lifemap_event(
    db: Session,
    *,
    scope: ProfileScope,
    event: LifeMapEvent,
    revision: LifeMapEventRevision,
    idempotency_key: str,
) -> str:
    """Synchronize a LifeMap revision as a GLHS candidate or GST transition.

    This is a convergence adapter, not a second truth engine.  Existing event
    APIs still own their client contract.  A ``draft`` remains candidate-only;
    a user report becomes usable governed state with the same epistemic status.
    A user-facing confirmation is never silently upgraded to a clinical GLHS
    confirmation; only an authorized clinician transition receives that status.
    """

    source = _event_source(db, scope=scope, event=event, revision=revision)
    occurred_at = event.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    truth_state = revision.truth_state
    if truth_state in {"disputed", "invalidated", "entered_in_error"}:
        active_assertions = list(
            db.execute(
                select(GlhsAssertion).where(
                    GlhsAssertion.profile_id == scope.profile.id,
                    GlhsAssertion.semantic_key == f"lifemap_event:{event.public_id}",
                    GlhsAssertion.lifecycle_status == "active",
                )
            ).scalars()
        )
        if not active_assertions:
            return cast(str, revision.public_id)
        key_prefix = (
            "glhs-lifemap:"
            + hashlib.sha256(f"{idempotency_key}:{revision.public_id}".encode()).hexdigest()
        )
        last_transition_id = revision.public_id
        for index, active in enumerate(active_assertions):
            transition = apply_transition(
                db,
                scope=scope,
                assertion=active,
                action="supersede",
                expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                idempotency_key=f"{key_prefix}:retire:{index}",
                transition_kind="lifemap_truth_retired",
                reason_code=f"lifemap_{truth_state}",
                effective_at=datetime.now(UTC),
            )
            last_transition_id = transition.public_id
        return cast(str, last_transition_id)

    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="lifemap_event",
            artifact_type="lifemap_event_revision",
            artifact_public_id=revision.public_id,
            fingerprint=_fingerprint({"source": source.checksum, "revision": revision.public_id}),
            valid_from=occurred_at,
            source_timezone=scope.profile.timezone,
        ),
    )
    epistemic_state = {
        "user_reported": "reported",
        "draft": "extracted",
        "confirmed": "confirmed" if scope.actor_role == "clinician" else "documented",
    }.get(truth_state, "unknown")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            # This stable event slot prevents a report from a separate event
            # being silently conflated with another clinical fact before a
            # deterministic normalizer/reviewer establishes that relation.
            semantic_key=f"lifemap_event:{event.public_id}",
            assertion_type="lifemap",
            predicate=event.event_type,
            value={"event_type": event.event_type, "payload": revision.payload_json},
            epistemic_state=epistemic_state,
            valid_from=occurred_at,
            subject_kind="profile",
            process_kind="user" if scope.actor_role == "owner" else "clinician",
        ),
        evidence=((evidence, "supports"),),
    )
    if truth_state == "draft":
        return cast(str, assertion.public_id)
    active_assertions = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.semantic_key == assertion.semantic_key,
                GlhsAssertion.lifecycle_status == "active",
            )
        ).scalars()
    )
    key_prefix = (
        "glhs-lifemap:"
        + hashlib.sha256(f"{idempotency_key}:{revision.public_id}".encode()).hexdigest()
    )
    for index, active in enumerate(active_assertions):
        apply_transition(
            db,
            scope=scope,
            assertion=active,
            action="supersede",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"{key_prefix}:supersede:{index}",
            transition_kind="lifemap_revision_replaced",
            reason_code="lifemap_revision_replaced",
            effective_at=occurred_at,
        )
    assertion = _rebase_same_transaction_proposal(db, scope=scope, assertion=assertion)
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=current_state_version(db, profile_id=scope.profile.id),
        idempotency_key=f"{key_prefix}:activate",
        transition_kind=(
            "lifemap_revision_replaced" if active_assertions else "lifemap_user_report"
        ),
        reason_code=("lifemap_revision_replaced" if active_assertions else "lifemap_event_created"),
        allow_confirmed=epistemic_state == "confirmed" and scope.actor_role == "clinician",
    )
    return cast(str, transition.public_id)


def ingest_medication_course(
    db: Session,
    *,
    scope: ProfileScope,
    course: MedicationCourse,
    idempotency_key: str,
) -> str:
    """Synchronize an explicitly entered medication course into the ledger.

    A course without a deterministic DrugBank identity is retained as a
    provenance-bound unresolved candidate.  It is deliberately excluded from
    medication THSS and therefore cannot silently feed DDI/CareGuard as a
    guessed drug.  Corrections first supersede the active assertion for that
    *course slot*, then activate the replacement.  Ending a course only
    supersedes its active assertion; it never fabricates a new active fact.
    """

    occurred_at = course.started_at or datetime.now(UTC)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    source_identity = f"medication_course:{course.public_id}:version:{course.version_no}"
    source = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if source is None:
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="medication_course",
            source_identity=source_identity,
            author_type=scope.actor_role,
            author_public_id=str(scope.actor.id),
            checksum=_fingerprint({"course": course.public_id, "version": course.version_no}),
            observed_at=occurred_at,
        )
        db.add(source)
        db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="medication_course",
            artifact_type="medication_course",
            artifact_public_id=course.public_id,
            fingerprint=_fingerprint({"source": source.checksum, "version": course.version_no}),
            valid_from=occurred_at,
            source_timezone=scope.profile.timezone,
        ),
    )
    drugbank_id = (course.drugbank_id or "").strip()
    resolved = bool(drugbank_id)
    assertion_type = "medications" if resolved else "medications_unresolved"
    # A DrugBank identity identifies the medicinal product, not a person's
    # individual course.  Keeping the course public ID in the semantic slot
    # prevents concurrent/repeated courses of the same product from being
    # silently conflated by the state transition layer.
    semantic_key = f"medication_course:{course.public_id}"
    transition_key_prefix = (
        "glhs-med:"
        + hashlib.sha256(
            f"{idempotency_key}:{course.public_id}:{course.version_no}".encode()
        ).hexdigest()
    )

    active_assertions = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.semantic_key == semantic_key,
                GlhsAssertion.lifecycle_status == "active",
            )
        ).scalars()
    )

    if course.status == "ended":
        # The ended row and its immutable MedicationCourseChange are evidence
        # for a state transition, but not a new medication claim.  A legacy
        # pre-GLHS course can legitimately have no active assertion yet; in
        # that case the adapter remains a no-op rather than inventing history.
        if not active_assertions:
            return cast(str, course.public_id)
        effective_at = course.ended_at or datetime.now(UTC)
        if effective_at.tzinfo is None:
            effective_at = effective_at.replace(tzinfo=UTC)
        last_transition_id = course.public_id
        for index, active in enumerate(active_assertions):
            transition = apply_transition(
                db,
                scope=scope,
                assertion=active,
                action="supersede",
                expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                idempotency_key=f"{transition_key_prefix}:end:{index}",
                transition_kind="medication_course_ended",
                reason_code="explicit_medication_end",
                effective_at=effective_at,
            )
            last_transition_id = transition.public_id
        return cast(str, last_transition_id)

    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=semantic_key,
            assertion_type=assertion_type,
            predicate="medication_course",
            value={
                "course_id": course.public_id,
                "drugbank_id": drugbank_id or None,
                "medication_name": course.medication_name,
                "dose_text": course.dose_text,
                "schedule_text": course.schedule_text,
                "route_text": course.route_text,
                "form_text": course.form_text,
                "reconciliation_status": course.reconciliation_status,
            },
            epistemic_state="reported",
            valid_from=occurred_at,
            valid_to=course.ended_at,
            process_kind="user" if scope.actor_role == "owner" else "clinician",
        ),
        evidence=((evidence, "supports"),),
    )
    if not resolved:
        return cast(str, assertion.public_id)
    # Corrections are command-authorized mutations of the same course, rather
    # than competing clinical reports.  Retire its active assertion(s) before
    # activating the new evidence-bound version so THSS does not surface a
    # false conflict or retain an old dose.
    for index, active in enumerate(active_assertions):
        apply_transition(
            db,
            scope=scope,
            assertion=active,
            action="supersede",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"{transition_key_prefix}:supersede:{index}",
            transition_kind="medication_course_corrected",
            reason_code="explicit_medication_correction",
        )
    assertion = _rebase_same_transaction_proposal(db, scope=scope, assertion=assertion)
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=current_state_version(db, profile_id=scope.profile.id),
        idempotency_key=f"{transition_key_prefix}:activate",
        transition_kind=(
            "medication_course_corrected" if active_assertions else "medication_user_report"
        ),
        reason_code=(
            "explicit_medication_correction" if active_assertions else "explicit_medication_entry"
        ),
    )
    return cast(str, transition.public_id)


def ingest_connected_health_observation(
    db: Session,
    *,
    scope: ProfileScope,
    observation: WearableObservation,
    idempotency_key: str,
) -> str:
    """Mirror one consented device observation through evidence and GST.

    Connector imports remain the source-system canonical ingest path.  This
    adapter records their provenance in GLHS without treating an automatic or
    provider-asserted measurement as a clinician-confirmed fact.  A provider
    update supersedes the previous assertion for the same provider-record slot;
    a tombstone retires it while leaving immutable evidence/transition history.
    """

    if observation.profile_id != scope.profile.id:
        raise ValueError("connected_observation_scope_forbidden")
    semantic_key = (
        "connected_observation:"
        f"{observation.connector_id}:{observation.data_origin}:{observation.provider_record_id}"
    )
    active_assertions = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.semantic_key == semantic_key,
                GlhsAssertion.lifecycle_status == "active",
            )
        ).scalars()
    )
    key_prefix = "glhs-connected:" + hashlib.sha256(
        f"{idempotency_key}:{observation.id}:{observation.version_no}".encode()
    ).hexdigest()
    if not observation.is_active:
        last_id = str(observation.id)
        for index, active in enumerate(active_assertions):
            transition = apply_transition(
                db,
                scope=scope,
                assertion=active,
                action="supersede",
                expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                idempotency_key=f"{key_prefix}:tombstone:{index}",
                transition_kind="connected_observation_tombstoned",
                reason_code="connector_tombstone",
                effective_at=observation.deleted_at or datetime.now(UTC),
            )
            last_id = transition.public_id
        return last_id

    observed_at = observation.observed_start
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    source_identity = (
        "connected_observation:"
        f"{observation.connector_id}:{observation.data_origin}:"
        f"{observation.provider_record_id}:version:{observation.version_no}"
    )
    source = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if source is None:
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="connected_health",
            source_identity=source_identity,
            author_type="connector",
            author_public_id=str(observation.connector_id),
            checksum=observation.raw_hash,
            observed_at=observed_at,
        )
        db.add(source)
        db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="connected_observation",
            artifact_type="wearable_observation",
            artifact_public_id=str(observation.id),
            fingerprint=_fingerprint(
                {
                    "source": source.checksum,
                    "observation_id": observation.id,
                    "version": observation.version_no,
                }
            ),
            valid_from=observed_at,
            source_timezone=scope.profile.timezone,
        ),
    )
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=semantic_key,
            assertion_type="observations",
            predicate=f"connected_{observation.record_type}",
            value={
                "observation_id": observation.id,
                "connector_id": observation.connector_id,
                "provider": observation.provider,
                "record_type": observation.record_type,
                "value": observation.value_json,
                "observed_start": observation.observed_start.isoformat(),
                "observed_end": observation.observed_end.isoformat(),
                "recording_method": observation.recording_method,
                "quality": observation.quality_json or {},
            },
            epistemic_state="documented",
            valid_from=observed_at,
            process_kind="connector",
        ),
        evidence=((evidence, "supports"),),
    )
    for index, active in enumerate(active_assertions):
        apply_transition(
            db,
            scope=scope,
            assertion=active,
            action="supersede",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"{key_prefix}:supersede:{index}",
            transition_kind="connected_observation_updated",
            reason_code="provider_record_updated",
            effective_at=observed_at,
        )
    assertion = _rebase_same_transaction_proposal(db, scope=scope, assertion=assertion)
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=current_state_version(db, profile_id=scope.profile.id),
        idempotency_key=f"{key_prefix}:activate",
        transition_kind=(
            "connected_observation_updated"
            if active_assertions
            else "connected_observation_imported"
        ),
        reason_code=(
            "provider_record_updated" if active_assertions else "consented_connector_import"
        ),
    )
    return cast(str, transition.public_id)


def ingest_visit_document(
    db: Session,
    *,
    scope: ProfileScope,
    document: VisitDocument,
    idempotency_key: str,
) -> str:
    """Mirror a visit document into GLHS without interpreting its clinical text.

    Visit documents, including a linked signed Scribe note, are evidence
    artifacts.  Their existence and lifecycle are governed state, but their
    free text is deliberately *not* converted into diagnoses, medications, or
    instructions here.  Such extraction requires a separate grounded,
    reviewable workflow.
    """

    if document.profile_id != scope.profile.id:
        raise ValueError("visit_document_scope_forbidden")
    if document.deleted_at is not None or document.withdrawn_at is not None:
        return retire_visit_document_assertions(
            db,
            scope=scope,
            document=document,
            idempotency_key=idempotency_key,
        )

    created_at = document.created_at or datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    source_identity = (
        f"visit_document:{document.public_id}:revision:{document.revision_no}:"
        f"{document.content_digest}"
    )
    source = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if source is None:
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="visit_document",
            source_identity=source_identity,
            author_type="owner",
            author_public_id=str(scope.actor.id),
            checksum=document.content_digest,
            observed_at=created_at,
        )
        db.add(source)
        db.flush()

    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="visit_document",
            artifact_type=document.document_kind,
            artifact_public_id=document.public_id,
            fingerprint=_fingerprint(
                {
                    "document": document.public_id,
                    "revision": document.revision_no,
                    "digest": document.content_digest,
                    "status": document.status,
                }
            ),
            valid_from=created_at,
            source_timezone=scope.profile.timezone,
        ),
    )
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"visit_document:{document.public_id}",
            assertion_type="evidence",
            predicate="visit_document_available",
            value={
                "document_id": document.public_id,
                "visit_id": document.visit_id,
                "document_kind": document.document_kind,
                "status": document.status,
                "revision_no": document.revision_no,
                "content_digest": document.content_digest,
                "scribe_session_id": document.scribe_session_id,
                "contains_interpreted_clinical_facts": False,
            },
            epistemic_state="documented",
            valid_from=created_at,
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=current_state_version(db, profile_id=scope.profile.id),
        idempotency_key=f"{idempotency_key}:activate",
        transition_kind="visit_document_recorded",
        reason_code="user_linked_document",
        effective_at=created_at,
    )
    return cast(str, transition.public_id)


def retire_visit_document_assertions(
    db: Session,
    *,
    scope: ProfileScope,
    document: VisitDocument,
    idempotency_key: str,
) -> str:
    """Retire active document-availability assertions after withdrawal/deletion."""

    if document.profile_id != scope.profile.id:
        raise ValueError("visit_document_scope_forbidden")
    active = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == scope.profile.id,
                GlhsAssertion.semantic_key == f"visit_document:{document.public_id}",
                GlhsAssertion.lifecycle_status == "active",
            )
        ).scalars()
    )
    last_transition = ""
    effective_at = document.withdrawn_at or document.deleted_at or datetime.now(UTC)
    if effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=UTC)
    for index, assertion in enumerate(active):
        transition = apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="supersede",
            expected_state_version=current_state_version(db, profile_id=scope.profile.id),
            idempotency_key=f"{idempotency_key}:supersede:{index}",
            transition_kind="visit_document_withdrawn",
            reason_code=(
                "source_document_deleted"
                if document.deleted_at is not None
                else "source_document_withdrawn"
            ),
            effective_at=effective_at,
        )
        last_transition = transition.public_id
    return last_transition


def owner_profile_scope(*, profile, actor: User, purpose: str = "self_care") -> ProfileScope:
    """Construct the same owner-only scope used after PHR's direct ownership check."""

    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role="owner",
        purpose=purpose,
        allowed_actions=frozenset(
            {
                "view",
                "create",
                "confirm",
                "correct",
                "dispute",
                "invalidate",
                "resolve",
                "accept",
                "complete",
                "share",
                "export",
            }
        ),
        allowed_data_classes=frozenset(
            {
                "lifemap",
                "medications",
                "allergies",
                "conditions",
                "observations",
                "visits",
                "evidence",
            }
        ),
    )


def _record_entry_time(entry: dict[str, object]) -> datetime:
    """Use an explicitly supplied date when present; never infer clinical time."""

    for field_name in ("started_on", "diagnosed_on"):
        raw = entry.get(field_name)
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)


def _record_entry_source(
    db: Session,
    *,
    scope: ProfileScope,
    data_class: str,
    entry_id: str,
    entry: dict[str, object],
    observed_at: datetime,
) -> HealthSourceReference:
    checksum = _fingerprint(entry)
    source_identity = f"phr_record:{data_class}:{entry_id}:{checksum}"
    existing = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(HealthSourceReference, existing)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="phr_record",
        source_identity=source_identity,
        author_type="owner",
        author_public_id=str(scope.actor.id),
        checksum=checksum,
        observed_at=observed_at,
    )
    db.add(source)
    db.flush()
    return source


def ingest_phr_record_entries(
    db: Session,
    *,
    scope: ProfileScope,
    allergies: list[dict[str, object]],
    conditions: list[dict[str, object]],
    medications: list[dict[str, object]],
    idempotency_key: str,
) -> tuple[str, ...]:
    """Synchronize the PHR's structured self-declared lists to GLHS.

    Legacy PHR medication names lack deterministic DrugBank identity, so they
    are retained as provenance-bound ``medications_unresolved`` candidates and
    are intentionally absent from medication THSS/DDI.  Allergy and condition
    entries are governed reported assertions.  Removing an entry supersedes
    only that entry's semantic slot; history is never deleted.
    """

    groups = (
        ("allergies", allergies, True),
        ("conditions", conditions, True),
        ("medications_unresolved", medications, False),
    )
    transition_ids: list[str] = []
    for assertion_type, entries, activate in groups:
        present_keys: set[str] = set()
        for raw_entry in entries:
            entry = dict(raw_entry)
            entry_id = str(entry.get("id") or "").strip()
            if not entry_id:
                # Schemas require IDs; retaining this guard makes the adapter
                # fail closed when invoked by a future importer.
                continue
            semantic_key = f"phr_{assertion_type}:{entry_id}"
            present_keys.add(semantic_key)
            occurred_at = _record_entry_time(entry)
            source = _record_entry_source(
                db,
                scope=scope,
                data_class=assertion_type,
                entry_id=entry_id,
                entry=entry,
                observed_at=occurred_at,
            )
            evidence = record_evidence(
                db,
                profile_id=scope.profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="phr_record_entry",
                    artifact_type="phr_record_entry",
                    artifact_public_id=f"{assertion_type}:{entry_id}",
                    fingerprint=_fingerprint(
                        {"source": source.checksum, "type": assertion_type, "entry": entry_id}
                    ),
                    valid_from=occurred_at,
                    time_precision="day" if occurred_at.hour == 0 else "exact",
                    source_timezone=scope.profile.timezone,
                ),
            )
            active_rows = list(
                db.execute(
                    select(GlhsAssertion).where(
                        GlhsAssertion.profile_id == scope.profile.id,
                        GlhsAssertion.semantic_key == semantic_key,
                        GlhsAssertion.lifecycle_status == "active",
                    )
                ).scalars()
            )
            value_fingerprint = _fingerprint(entry)
            if any(row.value_fingerprint == value_fingerprint for row in active_rows):
                continue
            candidate_rows: list[GlhsAssertion] = []
            if not activate:
                candidate_rows = list(
                    db.execute(
                    select(GlhsAssertion).where(
                        GlhsAssertion.profile_id == scope.profile.id,
                        GlhsAssertion.semantic_key == semantic_key,
                        GlhsAssertion.lifecycle_status == "candidate",
                    )
                    ).scalars()
                )
                if any(row.value_fingerprint == value_fingerprint for row in candidate_rows):
                    continue
            assertion = propose_assertion(
                db,
                profile_id=scope.profile.id,
                actor_user_id=scope.actor.id,
                data=AssertionInput(
                    semantic_key=semantic_key,
                    assertion_type=assertion_type,
                    predicate=str(entry.get("name") or assertion_type),
                    value=entry,
                    epistemic_state="reported",
                    valid_from=occurred_at,
                    time_precision="day" if occurred_at.hour == 0 else "exact",
                    process_kind="user",
                ),
                evidence=((evidence, "supports"),),
            )
            if not activate:
                # A free-text medication is intentionally never activated,
                # but a correction still retires its previous candidate so it
                # cannot be mistaken for current unresolved input in a future
                # review queue.
                for index, candidate in enumerate(candidate_rows):
                    transition = apply_transition(
                        db,
                        scope=scope,
                        assertion=candidate,
                        action="supersede",
                        expected_state_version=current_state_version(
                            db, profile_id=scope.profile.id
                        ),
                        idempotency_key="glhs-phr:"
                        + hashlib.sha256(
                            f"{idempotency_key}:{candidate.public_id}:candidate_replaced".encode()
                        ).hexdigest()
                        + f":{index}",
                        transition_kind="phr_unresolved_medication_replaced",
                        reason_code="phr_record_entry_replaced",
                        effective_at=occurred_at,
                    )
                    transition_ids.append(transition.public_id)
                continue
            key_prefix = (
                "glhs-phr:"
                + hashlib.sha256(
                    f"{idempotency_key}:{assertion_type}:{entry_id}:{value_fingerprint}".encode()
                ).hexdigest()
            )
            for index, active_row in enumerate(active_rows):
                transition = apply_transition(
                    db,
                    scope=scope,
                    assertion=active_row,
                    action="supersede",
                    expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                    idempotency_key=f"{key_prefix}:supersede:{index}",
                    transition_kind="phr_record_entry_replaced",
                    reason_code="phr_record_entry_replaced",
                    effective_at=occurred_at,
                )
                transition_ids.append(transition.public_id)
            assertion = _rebase_same_transaction_proposal(
                db, scope=scope, assertion=assertion
            )
            transition = apply_transition(
                db,
                scope=scope,
                assertion=assertion,
                action="activate",
                expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                idempotency_key=f"{key_prefix}:activate",
                transition_kind="phr_record_entry_reported",
                reason_code="self_declared_phr_entry",
            )
            transition_ids.append(transition.public_id)

        lifecycle = "active" if activate else "candidate"
        active_rows = list(
            db.execute(
                select(GlhsAssertion).where(
                    GlhsAssertion.profile_id == scope.profile.id,
                    GlhsAssertion.assertion_type == assertion_type,
                    GlhsAssertion.lifecycle_status == lifecycle,
                )
            ).scalars()
        )
        for active_row in active_rows:
            if active_row.semantic_key in present_keys:
                continue
            transition = apply_transition(
                db,
                scope=scope,
                assertion=active_row,
                action="supersede",
                expected_state_version=current_state_version(db, profile_id=scope.profile.id),
                idempotency_key="glhs-phr:"
                + hashlib.sha256(
                    f"{idempotency_key}:{active_row.public_id}:removed".encode()
                ).hexdigest(),
                transition_kind=(
                    "phr_record_entry_removed"
                    if activate
                    else "phr_unresolved_medication_removed"
                ),
                reason_code="phr_record_entry_removed",
                effective_at=datetime.now(UTC),
            )
            transition_ids.append(transition.public_id)
    return tuple(transition_ids)


def ingest_phr_observation(
    db: Session,
    *,
    scope: ProfileScope,
    observation: PhrObservation,
) -> str:
    """Mirror a user-recorded PHR observation as governed reported state."""

    observed_at = datetime.combine(
        observation.observed_on or datetime.now(UTC).date(),
        datetime.min.time(),
        tzinfo=UTC,
    )
    source_identity = f"phr_observation:{observation.entry_id}"
    source = db.execute(
        select(HealthSourceReference).where(
            HealthSourceReference.profile_id == scope.profile.id,
            HealthSourceReference.source_identity == source_identity,
        )
    ).scalar_one_or_none()
    if source is None:
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="phr_observation",
            source_identity=source_identity,
            author_type="owner",
            author_public_id=str(scope.actor.id),
            checksum=_fingerprint(
                {
                    "entry_id": observation.entry_id,
                    "name": observation.name,
                    "value": observation.value,
                    "unit": observation.unit,
                    "observed_on": observation.observed_on,
                }
            ),
            observed_at=observed_at,
        )
        db.add(source)
        db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="phr_observation",
            artifact_type="phr_observation",
            artifact_public_id=observation.entry_id,
            fingerprint=_fingerprint({"source": source.checksum}),
            valid_from=observed_at,
            time_precision="day",
            source_timezone=scope.profile.timezone,
        ),
    )
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"observation:{observation.name}:{observation.entry_id}",
            assertion_type="observations",
            predicate=observation.name,
            value={"value": observation.value, "unit": observation.unit},
            epistemic_state="reported",
            valid_from=observed_at,
            time_precision="day",
        ),
        evidence=((evidence, "supports"),),
    )
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=current_state_version(db, profile_id=scope.profile.id),
        idempotency_key=f"phr-observation:{observation.entry_id}",
        transition_kind="phr_observation_report",
        reason_code="self_declared_observation",
    )
    return cast(str, transition.public_id)
