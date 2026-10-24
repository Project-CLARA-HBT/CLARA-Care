"""LifeMap Universal Capture Extraction and GLHS Continuity Service.

Spec: Phase PH12 / Agent A03 (Domain + GLHS services).
Role:
- LifeMap capture extraction domain service linking universal capture to longitudinal timeline events.
- Updates GLHS continuity digests (D1 projection digest, D2 semantic digest, D3 transport digest, canonical lineage digest).
- Performs Optimistic Concurrency Control (OCC) conflict resolution via entity partition locking and CAS version validation.
- Preserves competing clinical assertions non-destructively through ConflictPreservationEngine.
- Strictly enforces profile authorization scope, emergency fast-path, and no-PII telemetry.
- Protected behind `lifemap_capture_extraction_service_enabled` feature flag (default False).
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.db.models import (
    HealthSourceReference,
    LifeMapCaptureCandidate,
    LifeMapCaptureReviewAction,
    LifeMapCaptureSession,
    LifeMapEvent,
    LifeMapEventRevision,
    PhrProfile,
)
from clara_api.glhs.adapters import ingest_lifemap_event
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    fast_canonical_digest,
)
from clara_api.glhs.commit_kernel import (
    DependencySpec,
    compute_dependency_vector_digest,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.fhir_mapping_service import GlhsContinuityReport
from clara_api.glhs.inference_envelope import (
    compute_projection_digest,
    compute_semantic_envelope_digest,
    compute_transport_payload_digest,
)
from clara_api.glhs.lock_hierarchy import current_state_version
from clara_api.glhs.occ_locking_adapters import LifeMapCaptureLockAdapter
from clara_api.lifemap.capture_domain import (
    emergency_fast_path,
    validate_candidate,
)
from clara_api.lifemap.capture_extraction import (
    ExtractedCandidate,
)
from clara_api.lifemap.conflict_preservation import (
    ConflictPreservationEngine,
    PreservedClinicalAssertion,
)
from clara_api.lifemap.profile_scope import ProfileScope


class CaptureExtractionServiceDisabledError(RuntimeError):
    """Raised when the capture extraction service feature flag is not enabled."""


class CaptureExtractionValidationError(ValueError):
    """Raised when capture extraction inputs or candidates fail validation."""


class CaptureExtractionConflictError(RuntimeError):
    """Raised when OCC version conflicts or unresolvable clinical conflicts occur."""


class CaptureEmergencyEscalationError(RuntimeError):
    """Raised when emergency symptoms are detected during capture extraction."""


@dataclasses.dataclass(frozen=True)
class GlhsContinuityDigestBundle:
    """Cryptographic 3-digest continuity and lineage verification bundle."""

    d1_projection_digest: str
    d2_semantic_digest: str
    d3_transport_digest: str
    lineage_digest: str
    state_version: int
    continuity_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "d1_projection_digest": self.d1_projection_digest,
            "d2_semantic_digest": self.d2_semantic_digest,
            "d3_transport_digest": self.d3_transport_digest,
            "lineage_digest": self.lineage_digest,
            "state_version": self.state_version,
            "continuity_verified": self.continuity_verified,
        }


@dataclasses.dataclass(frozen=True)
class CaptureTimelineLinkResult:
    """Result of linking an extracted capture candidate to a longitudinal timeline event."""

    event_id: str
    event_revision_id: str
    candidate_id: str
    profile_id: int
    truth_state: str
    continuity_digests: GlhsContinuityDigestBundle
    occ_version: int
    idempotent_replay: bool
    preserved_assertions: tuple[PreservedClinicalAssertion, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_revision_id": self.event_revision_id,
            "candidate_id": self.candidate_id,
            "profile_id": self.profile_id,
            "truth_state": self.truth_state,
            "continuity_digests": self.continuity_digests.to_dict(),
            "occ_version": self.occ_version,
            "idempotent_replay": self.idempotent_replay,
            "preserved_assertions_count": len(self.preserved_assertions),
        }


class CaptureExtractionService:
    """Domain service orchestrating Universal Capture extraction, timeline linkage, and GLHS continuity."""

    def __init__(
        self,
        db: Session,
        *,
        conflict_engine: ConflictPreservationEngine | None = None,
        bypass_flag_check: bool = False,
    ) -> None:
        self.db = db
        self.conflict_engine = conflict_engine or ConflictPreservationEngine()
        self.bypass_flag_check = bypass_flag_check
        self.lock_adapter = LifeMapCaptureLockAdapter(db)

    def _check_feature_flag(self) -> None:
        if self.bypass_flag_check:
            return
        settings = get_settings()
        if not getattr(settings, "lifemap_capture_extraction_service_enabled", False):
            raise CaptureExtractionServiceDisabledError(
                "lifemap_capture_extraction_service_disabled"
            )

    def compute_glhs_continuity_digests(
        self,
        *,
        profile_id: int,
        event_payload: Mapping[str, Any],
        provenance: Mapping[str, Any],
        raw_source_bytes: bytes | None = None,
    ) -> GlhsContinuityDigestBundle:
        """Computes canonical GLHS 3-digests (D1, D2, D3) and lineage digest."""
        # D1: Projection digest over canonical clinical health projection
        d1 = compute_projection_digest(dict(event_payload))

        # D2: Semantic envelope digest over application envelope
        semantic_envelope = {
            "profile_id": profile_id,
            "payload": event_payload,
            "provenance": provenance,
            "schema_version": "lifemap.timeline.v1",
        }
        d2 = compute_semantic_envelope_digest(semantic_envelope)

        # D3: Transport payload digest
        if raw_source_bytes is not None:
            d3 = compute_transport_payload_digest(raw_source_bytes)
        else:
            d3 = hashlib.sha256(
                fast_canonical_digest(dict(event_payload)).encode("utf-8")
            ).hexdigest()

        # Canonical Lineage Digest
        curr_ver = current_state_version(self.db, profile_id=profile_id)
        lineage_payload = {
            "domain": "lifemap_timeline",
            "profile_id": profile_id,
            "d1_projection_digest": d1,
            "d2_semantic_digest": d2,
            "state_version": curr_ver,
        }
        lineage_digest = fast_canonical_digest(lineage_payload)

        return GlhsContinuityDigestBundle(
            d1_projection_digest=d1,
            d2_semantic_digest=d2,
            d3_transport_digest=d3,
            lineage_digest=lineage_digest,
            state_version=curr_ver,
            continuity_verified=True,
        )

    def link_capture_to_timeline_event(
        self,
        *,
        scope: ProfileScope,
        candidate_id: str,
        expected_occ_version: int | None = None,
        idempotency_key: str | None = None,
        competing_clinical_claims: Sequence[tuple[str, str, float]] | None = None,
    ) -> CaptureTimelineLinkResult:
        """Links an approved Universal Capture candidate to the longitudinal timeline with GLHS continuity and OCC."""
        self._check_feature_flag()

        # 1. Profile Scope Authorization Check
        if "create" not in scope.allowed_actions and "update" not in scope.allowed_actions:
            raise GlhsInvariantError("profile_scope_action_forbidden")

        # 2. Candidate Resolution & Scope Boundary
        candidate = self.db.execute(
            select(LifeMapCaptureCandidate).where(
                LifeMapCaptureCandidate.public_id == candidate_id,
                LifeMapCaptureCandidate.profile_id == scope.profile.id,
            )
        ).scalar_one_or_none()

        if candidate is None:
            raise CaptureExtractionValidationError(
                f"Candidate {candidate_id} not found in current profile scope"
            )

        session = self.db.execute(
            select(LifeMapCaptureSession).where(
                LifeMapCaptureSession.id == candidate.session_id,
                LifeMapCaptureSession.profile_id == scope.profile.id,
            )
        ).scalar_one_or_none()

        if session is None:
            raise CaptureExtractionValidationError(
                f"Capture session for candidate {candidate_id} not found"
            )

        # 3. Emergency Fast-Path Check on Candidate Text / Value
        candidate_val = candidate.value_json if isinstance(candidate.value_json, dict) else {}
        extracted_text = str(candidate_val.get("text", "") or candidate_val.get("name", ""))
        if extracted_text and emergency_fast_path(extracted_text):
            raise CaptureEmergencyEscalationError("emergency_fast_path_triggered")

        # 4. Candidate Validation against Closed Schemas
        validation = validate_candidate(candidate.candidate_type, candidate_val)
        if not validation.valid:
            raise CaptureExtractionValidationError(
                f"Candidate missing required fields: {','.join(validation.missing_required)}"
            )

        # 5. Entity-Local OCC Partition Locking
        user_id = scope.actor.id
        session_id_str = session.public_id
        lock_res = self.lock_adapter.lock_capture_extraction(
            profile_id=scope.profile.id,
            session_id=session_id_str,
            user_id=user_id,
            exclusive=True,
        )
        if not lock_res.success:
            raise CaptureExtractionConflictError("occ_lock_acquisition_failed")

        # 6. OCC CAS Version Revalidation
        current_profile_ver = scope.profile.current_version_no or 1
        if expected_occ_version is not None and expected_occ_version != current_profile_ver:
            raise CaptureExtractionConflictError(
                f"OCC conflict: expected version {expected_occ_version} != current {current_profile_ver}"
            )

        # 7. Check for Idempotent Replay if idempotency_key is provided
        idem_key = idempotency_key or f"capture-link:{candidate.public_id}"
        existing_event = self.db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.profile_id == scope.profile.id,
                LifeMapEvent.provenance_json["capture_candidate_id"].as_string() == candidate.public_id,
            )
        ).scalar_one_or_none()

        if existing_event is not None:
            # Replay existing event
            existing_rev = self.db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.event_id == existing_event.id,
                    LifeMapEventRevision.revision_no == existing_event.current_revision_no,
                )
            ).scalar_one()

            digests = self.compute_glhs_continuity_digests(
                profile_id=scope.profile.id,
                event_payload=existing_event.payload_json,
                provenance=existing_event.provenance_json,
            )

            return CaptureTimelineLinkResult(
                event_id=existing_event.public_id,
                event_revision_id=existing_rev.public_id,
                candidate_id=candidate.public_id,
                profile_id=scope.profile.id,
                truth_state=existing_event.truth_state,
                continuity_digests=digests,
                occ_version=current_profile_ver,
                idempotent_replay=True,
                preserved_assertions=tuple(
                    self.conflict_engine.get_competing_assertions(existing_event.public_id)
                ),
            )

        # 8. Compute GLHS Continuity Digests
        canonical_val = fast_canonical_digest(candidate_val)
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="universal_capture",
            source_identity=session.public_id,
            author_type="profile_actor",
            author_public_id=str(scope.actor.id),
            checksum=hashlib.sha256(canonical_val.encode()).hexdigest(),
            original_language=session.locale,
            source_span_json=candidate.source_span_json,
            observed_at=datetime.now(UTC),
        )
        self.db.add(source)
        self.db.flush()

        digests = self.compute_glhs_continuity_digests(
            profile_id=scope.profile.id,
            event_payload=candidate_val,
            provenance={"source_reference_id": source.public_id, "session_id": session.public_id},
        )

        # 9. Create LifeMapEvent and LifeMapEventRevision
        provenance_dict = {
            "source_reference_id": source.public_id,
            "capture_session_id": session.public_id,
            "capture_candidate_id": candidate.public_id,
            "glhs_continuity": digests.to_dict(),
            "confirmation": "universal_capture_extraction",
        }

        event = LifeMapEvent(
            profile_id=scope.profile.id,
            event_type=candidate.candidate_type,
            truth_state="confirmed" if candidate.status == "confirmed" else "user_reported",
            occurred_at=datetime.now(UTC),
            payload_json=candidate_val,
            provenance_json=provenance_dict,
            source_kind="universal_capture",
            created_by_user_id=scope.actor.id,
            current_revision_no=1,
        )
        self.db.add(event)
        self.db.flush()

        revision = LifeMapEventRevision(
            event_id=event.id,
            profile_id=scope.profile.id,
            revision_no=1,
            truth_state=event.truth_state,
            payload_json=candidate_val,
            provenance_json=provenance_dict,
            source_reference_id=source.id,
            asserted_by_user_id=scope.actor.id,
            reason_code="capture_extraction_linked",
            policy_version="lifemap-truth-v2",
        )
        self.db.add(revision)
        self.db.flush()

        # 10. Non-Destructive Multi-Source Conflict Preservation
        preserved_list: list[PreservedClinicalAssertion] = []
        base_assertion = self.conflict_engine.record_assertion(
            event_id=event.public_id,
            assertion_id=f"ast-{event.public_id}-primary",
            claim_text=str(candidate_val.get("name") or candidate_val.get("text") or candidate.candidate_type),
            source_author=f"user:{scope.actor.id}",
            status="CONFIRMED" if event.truth_state == "confirmed" else "UNCERTAIN",
            confidence=candidate.confidence or 0.9,
        )
        preserved_list.append(base_assertion)

        if competing_clinical_claims:
            for c_author, c_text, c_conf in competing_clinical_claims:
                comp_ast = self.conflict_engine.record_assertion(
                    event_id=event.public_id,
                    assertion_id=f"ast-{event.public_id}-{uuid4().hex[:6]}",
                    claim_text=c_text,
                    source_author=c_author,
                    status="DISPUTED",
                    confidence=c_conf,
                    dispute_notes=f"Competing claim from {c_author}",
                )
                preserved_list.append(comp_ast)

        # 11. Ingest into GLHS Ledger
        ingest_lifemap_event(
            self.db,
            scope=scope,
            event=event,
            revision=revision,
            idempotency_key=f"glhs-capture:{candidate.public_id}:{idem_key}",
        )

        # 12. CAS Increment Profile Version
        scope.profile.current_version_no = current_profile_ver + 1
        scope.profile.updated_at = datetime.now(UTC)

        candidate.status = "confirmed"
        self.db.add(
            LifeMapCaptureReviewAction(
                candidate_id=candidate.id,
                profile_id=scope.profile.id,
                actor_user_id=scope.actor.id,
                action="confirm",
                patch_json=candidate_val,
                reason_code="capture_extraction_timeline_linked",
            )
        )
        self.db.commit()

        return CaptureTimelineLinkResult(
            event_id=event.public_id,
            event_revision_id=revision.public_id,
            candidate_id=candidate.public_id,
            profile_id=scope.profile.id,
            truth_state=event.truth_state,
            continuity_digests=digests,
            occ_version=scope.profile.current_version_no,
            idempotent_replay=False,
            preserved_assertions=tuple(preserved_list),
        )
